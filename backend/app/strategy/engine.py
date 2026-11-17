import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.strategy.candles import Candle, H1_SECONDS, H4_SECONDS, closed_candles
from app.strategy.risk import (
    MAX_TRADES_PER_DAY,
    REWARD_MULTIPLE,
    RISK_FRACTION,
    SymbolSpec,
    round_price,
    size_position,
)

RULES_SOURCE = "h4_bias_h1_retest"
MIN_STOP_DISTANCE = 0.0
TARGET_R = 5.0
MAX_STOP_PIPS = 100
ACCRA = ZoneInfo("Africa/Accra")
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")

RULES = [
    "An 80% win rate is a research target. This engine does not claim that target. It waits when the H4 bias and H1 retest rules do not confirm a setup.",
    "H4 bias uses two candles. A completed H4 close beyond the prior H4 high or low confirms it. While that next H4 candle is still forming, a completed H1 close confirms it early only if the forming H4 candle has also traded beyond the same level.",
    "An H1 setup needs the hour's close beyond the previous hour's high for a buy, or beyond its low for a sell. The retest level is that high or low. The stop is the opposite wick of the breakout hour. A newer valid breakout replaces the pending level. The setup hour cannot be its own retest.",
    "The setup is saved only while London or New York local time is from 08:00 to 17:00. A later hour must open on the breakout side and trade back to the level. A buy fills at the ask. A sell fills at the bid.",
    "The stop is the breakout hour's opposite wick. A stop of 100 pips or more invalidates that H1 setup. Take-profit is 5 times the stop distance. If one later candle touches the stop and the target, the trade is a loss.",
    "Lot size uses 2% of balance and the broker tick value, floored to the volume step so planned cash risk does not round above 2%. A result below the minimum lot is skipped. A 0.01 lot is never assumed when the symbol spec is missing.",
    "At most two entries are allowed per Ghana calendar day, counted from broker deals with this bot's magic number. A new setup is skipped while this symbol already has an open position.",
    "With Auto on, the selected watchlist market keeps scanning in this API process while the PC is awake, even if the window is closed. Contest and unknown accounts cannot send.",
]


@dataclass(frozen=True)
class Proposal:
    symbol: str
    direction: str
    signal_time: int
    entry: float
    stop_loss: float
    take_profit: float
    stop_distance: float
    lot_size: float | None
    estimated_risk_cash: float | None
    capped: bool
    dedupe_key: str
    expires_at: int

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Evaluation:
    bias: str
    proposal: Proposal | None
    skip_reason: str | None
    signal_time: int | None
    checks: dict = field(default_factory=dict)
    levels: list = field(default_factory=list)


@dataclass
class TradeRecord:
    direction: str
    signal_time: int
    entry_time: int
    exit_time: int | None
    entry: float
    stop_loss: float
    take_profit: float
    exit_price: float | None
    lot_size: float | None
    estimated_risk_cash: float | None
    cash_pnl: float | None
    r_multiple: float | None
    status: str
    exit_reason: str
    shot: dict | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class SkipRecord:
    signal_time: int
    reason: str
    direction: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestReport:
    symbol: str
    source: str
    spread: float
    spread_source: str
    starting_equity: float
    ending_equity: float | None
    from_time: int | None
    to_time: int | None
    bars_h1: int
    bars_h4: int
    rules_source: str
    execution_enabled: bool
    summary: dict
    trades: list[TradeRecord] = field(default_factory=list)
    skipped: list[SkipRecord] = field(default_factory=list)

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["trades"] = [trade.as_dict() for trade in self.trades]
        payload["skipped"] = [skip.as_dict() for skip in self.skipped]
        return payload


def _finite_candle(candle: Candle) -> bool:
    return all(math.isfinite(value) for value in (candle.open, candle.high, candle.low, candle.close))


def _exit_on_candle(direction: str, stop: float, take_profit: float, candle: Candle) -> tuple[float, str] | None:
    # One candle has no path. When both prices are touched, assume the stop filled first.
    if direction == "buy":
        hit_stop = candle.low <= stop
        hit_target = candle.high >= take_profit
    else:
        hit_stop = candle.high >= stop
        hit_target = candle.low <= take_profit
    if hit_stop and hit_target:
        return stop, "both_hit_stop_first"
    if hit_stop:
        return stop, "stop_loss"
    if hit_target:
        return take_profit, "take_profit"
    return None


def _cash(price_move: float, spec: SymbolSpec | None, lots: float | None) -> float | None:
    if spec is None or lots is None:
        return None
    return (price_move / spec.trade_tick_size) * spec.trade_tick_value * lots


def _apply_planned_cash(trade: TradeRecord, equity: float, risk_fraction: float) -> TradeRecord:
    """Mark cash from the saved risk fraction times R when the terminal has no lot spec."""
    if trade.cash_pnl is not None or trade.r_multiple is None:
        return trade
    if not math.isfinite(trade.r_multiple) or not math.isfinite(equity) or equity <= 0:
        return trade
    if not math.isfinite(risk_fraction) or risk_fraction <= 0:
        return trade
    risk_cash = trade.estimated_risk_cash
    if risk_cash is None or not math.isfinite(risk_cash) or risk_cash <= 0:
        risk_cash = equity * risk_fraction
    return TradeRecord(
        direction=trade.direction,
        signal_time=trade.signal_time,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        entry=trade.entry,
        stop_loss=trade.stop_loss,
        take_profit=trade.take_profit,
        exit_price=trade.exit_price,
        lot_size=trade.lot_size,
        estimated_risk_cash=round(risk_cash, 2),
        cash_pnl=round(risk_cash * trade.r_multiple, 2),
        r_multiple=trade.r_multiple,
        status=trade.status,
        exit_reason=trade.exit_reason,
        shot=trade.shot,
    )


def _day_key(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, ACCRA).date().isoformat()


def _session_open(close_time: int) -> bool:
    moment = datetime.fromtimestamp(close_time, timezone.utc)
    for zone in (LONDON, NEW_YORK):
        if 8 <= moment.astimezone(zone).hour < 17:
            return True
    return False


def _opened_candles(candles: list[Candle], now: float | None) -> list[Candle]:
    chosen = []
    for candle in candles:
        if not _finite_candle(candle):
            continue
        if now is not None and candle.time > now:
            continue
        chosen.append(candle)
    return chosen


def _bias_at(h4: list[Candle], h1_close_time: int, h1_close: float, forming_high: float | None, forming_low: float | None) -> tuple[int, float, float] | None:
    eligible = [candle for candle in h4 if candle.time <= h1_close_time and _finite_candle(candle)]
    if len(eligible) < 2:
        return None
    first, second = eligible[-2], eligible[-1]
    direction = 0
    if h1_close_time >= second.time + H4_SECONDS:
        if second.close > first.high:
            direction = 1
        elif second.close < first.low:
            direction = -1
    elif forming_high is not None and forming_low is not None:
        if h1_close > first.high and forming_high > first.high:
            direction = 1
        elif h1_close < first.low and forming_low < first.low:
            direction = -1
    return direction, float(first.high), float(first.low)


def _forming_span(h4: list[Candle], h1: list[Candle], bar_open: int) -> tuple[float | None, float | None]:
    active = [candle for candle in h4 if candle.time <= bar_open and _finite_candle(candle)]
    if not active:
        return None, None
    start = active[-1].time
    chosen = [candle for candle in h1 if start <= candle.time <= bar_open and _finite_candle(candle)]
    if not chosen:
        return None, None
    return max(candle.high for candle in chosen), min(candle.low for candle in chosen)


def _make_setup(previous: Candle, candle: Candle, bias: int, close_time: int, spec: SymbolSpec | None) -> dict | str | None:
    if bias == 1 and candle.close > previous.high:
        level, stop = float(previous.high), float(candle.low)
    elif bias == -1 and candle.close < previous.low:
        level, stop = float(previous.low), float(candle.high)
    else:
        return None
    if not _session_open(close_time):
        return None
    return {
        "direction": bias,
        "level": level,
        "sl": stop,
        "setup_time": int(candle.time),
        "close_time": close_time,
        "candle2_high": float(candle.high),
        "candle2_low": float(candle.low),
        "last_quote": float(candle.close),
        "logged_wide": False,
        "limited_day": None,
    }


def _forming_open(as_of: int) -> int:
    return as_of - (as_of % H4_SECONDS)


def _span(candles: list[Candle], start: int) -> tuple[float | None, float | None]:
    chosen = [candle for candle in candles if candle.time >= start and _finite_candle(candle)]
    if not chosen:
        return None, None
    return max(candle.high for candle in chosen), min(candle.low for candle in chosen)


def _next_bias(bias: int, closed_h4: list[Candle], closed_h1: list[Candle], as_of: int) -> tuple[int, bool, float | None, float | None]:
    usable = [candle for candle in closed_h4 if _finite_candle(candle)]
    if not usable:
        return bias, False, None, None
    reference = usable[-1]
    confirmed = 0
    if len(usable) >= 2:
        previous = usable[-2]
        if reference.close > previous.high:
            confirmed = 1
        elif reference.close < previous.low:
            confirmed = -1
    if confirmed == 0 and closed_h1:
        last = closed_h1[-1]
        high, low = _span(closed_h1, _forming_open(as_of))
        if _finite_candle(last) and last.time >= _forming_open(as_of) and high is not None and low is not None:
            if high > reference.high and last.close > reference.high:
                confirmed = 1
            elif low < reference.low and last.close < reference.low:
                confirmed = -1
    if confirmed:
        return confirmed, confirmed != bias, reference.high, reference.low
    return bias, False, reference.high, reference.low


def _levels(setup: dict, entry: float, stop: float, target: float) -> list[dict]:
    return [
        {"name": "H4 high", "price": setup["ref_high"]},
        {"name": "H4 low", "price": setup["ref_low"]},
        {"name": "Retest", "price": setup["level"]},
        {"name": "Breakout high", "price": setup["candle2_high"]},
        {"name": "Breakout low", "price": setup["candle2_low"]},
        {"name": "Entry", "price": entry},
        {"name": "Stop", "price": stop},
        {"name": "Target", "price": target},
    ]


def _touch_price(setup: dict, bar: Candle) -> float | None:
    level = setup["level"]
    previous = setup["last_quote"]
    if setup["direction"] == 1:
        if previous is None or not previous > level or bar.low > level:
            setup["last_quote"] = bar.close
            return None
        return level if bar.open > level else bar.open
    if previous is None or not previous < level or bar.high < level:
        setup["last_quote"] = bar.close
        return None
    return level if bar.open < level else bar.open


def _retested(setup: dict, bar: Candle) -> bool:
    level = setup["level"]
    if setup["direction"] == 1:
        return bar.open > level and bar.low <= level
    return bar.open < level and bar.high >= level


def _simulate(
    higher: list[Candle],
    lower: list[Candle],
    *,
    symbol: str,
    spec: SymbolSpec | None,
    spread: float,
    starting_equity: float,
    risk_fraction: float = RISK_FRACTION,
    reward_multiple: float = TARGET_R,
    max_stop_pips: float = MAX_STOP_PIPS,
    max_trades_per_day: int = MAX_TRADES_PER_DAY,
    paper_fills: bool = True,
) -> tuple[list[TradeRecord], list[SkipRecord], dict]:
    del spread, max_stop_pips
    pending: dict | None = None
    bias = 0
    ref_high = None
    ref_low = None
    open_trade: TradeRecord | None = None
    open_levels: list = []
    trades: list[TradeRecord] = []
    skipped: list[SkipRecord] = []
    day_counts: dict[str, int] = {}
    equity = starting_equity
    digits = spec.digits if spec is not None else 2
    noted_wide: set[int] = set()

    for index, bar in enumerate(lower):
        if index < 1 or not _finite_candle(bar) or not _finite_candle(lower[index - 1]):
            continue
        bar_close = bar.time + H1_SECONDS
        if paper_fills and open_trade is not None and bar.time > open_trade.entry_time:
            outcome = _exit_on_candle(open_trade.direction, open_trade.stop_loss, open_trade.take_profit, bar)
            if outcome is not None:
                exit_price, reason = outcome
                closed = _book(open_trade, exit_price, reason, bar.time, spec)
                closed = _apply_planned_cash(closed, equity, risk_fraction)
                closed.shot = _trade_shot(lower, closed, open_levels)
                trades.append(closed)
                if closed.cash_pnl is not None:
                    equity += closed.cash_pnl
                open_trade = None
        if open_trade is None and pending is not None and _retested(pending, bar):
            side = "buy" if pending["direction"] == 1 else "sell"
            # Live scan must not paper-fill: a historical touch would open a fake trade,
            # block later breakouts, and hide the real pending retest from Auto.
            if not paper_fills:
                pending = None
            else:
                day = _day_key(bar_close)
                entry = round_price(float(pending["level"]), digits)
                stop = round_price(float(pending["sl"]), digits)
                risk = entry - stop if pending["direction"] == 1 else stop - entry
                if day_counts.get(day, 0) >= max_trades_per_day:
                    if pending.get("limited_day") != day:
                        skipped.append(SkipRecord(bar.time, "daily_limit", side))
                        pending["limited_day"] = day
                elif risk <= 0 or not math.isfinite(risk):
                    skipped.append(SkipRecord(bar.time, "invalid_geometry", side))
                    pending = None
                else:
                    sized = size_position(equity, risk, spec, require_lots=False, risk_fraction=risk_fraction)
                    if sized.error:
                        skipped.append(SkipRecord(bar.time, sized.error, side))
                        pending = None
                    else:
                        target = round_price(
                            entry + reward_multiple * risk if side == "buy" else entry - reward_multiple * risk,
                            digits,
                        )
                        levels = _levels(pending, entry, stop, target)
                        day_counts[day] = day_counts.get(day, 0) + 1
                        planned = sized.cash_risk
                        if planned is None:
                            planned = equity * risk_fraction
                        open_trade = TradeRecord(
                            direction=side, signal_time=pending["setup_time"], entry_time=bar.time, exit_time=None,
                            entry=entry, stop_loss=stop, take_profit=target, exit_price=None, lot_size=sized.lots,
                            estimated_risk_cash=None if planned is None else round(planned, 2),
                            cash_pnl=None, r_multiple=None, status="open", exit_reason="open",
                        )
                        open_levels = levels
                        pending = None
        forming_high, forming_low = _forming_span(higher, lower[: index + 1], bar.time)
        found = _bias_at(higher, bar_close, float(bar.close), forming_high, forming_low)
        if found is None or open_trade is not None:
            if pending is not None:
                pending["last_quote"] = float(bar.close)
            continue
        direction, ref_high, ref_low = found
        if direction:
            bias = direction
        if direction == 0:
            if pending is not None:
                pending["last_quote"] = float(bar.close)
            continue
        made = _make_setup(lower[index - 1], bar, direction, bar_close, spec)
        if made == "stop_too_wide" and bar.time not in noted_wide:
            skipped.append(SkipRecord(bar.time, "stop_too_wide", "buy" if direction == 1 else "sell"))
            noted_wide.add(bar.time)
        elif made == "invalid_symbol_spec" and bar.time not in noted_wide:
            skipped.append(SkipRecord(bar.time, "invalid_symbol_spec", "buy" if direction == 1 else "sell"))
            noted_wide.add(bar.time)
        elif isinstance(made, dict):
            made["ref_high"] = ref_high
            made["ref_low"] = ref_low
            pending = made

    if open_trade is not None:
        trades.append(TradeRecord(
            direction=open_trade.direction,
            signal_time=open_trade.signal_time,
            entry_time=open_trade.entry_time,
            exit_time=None,
            entry=open_trade.entry,
            stop_loss=open_trade.stop_loss,
            take_profit=open_trade.take_profit,
            exit_price=None,
            lot_size=open_trade.lot_size,
            estimated_risk_cash=open_trade.estimated_risk_cash,
            cash_pnl=None,
            r_multiple=None,
            status="unresolved",
            exit_reason="unresolved",
            shot=_trade_shot(lower, open_trade, open_levels),
        ))
    return trades, skipped, {
        "bias": bias,
        "pending": pending,
        "ref_high": ref_high,
        "ref_low": ref_low,
        "symbol": symbol,
    }


def _book(trade: TradeRecord, exit_price: float, reason: str, exit_time: int, spec: SymbolSpec | None) -> TradeRecord:
    move = exit_price - trade.entry if trade.direction == "buy" else trade.entry - exit_price
    distance = abs(trade.entry - trade.stop_loss)
    multiple = move / distance if distance else None
    status = "win" if multiple is not None and multiple > 0 else "loss"
    return TradeRecord(
        direction=trade.direction,
        signal_time=trade.signal_time,
        entry_time=trade.entry_time,
        exit_time=exit_time,
        entry=trade.entry,
        stop_loss=trade.stop_loss,
        take_profit=trade.take_profit,
        exit_price=exit_price,
        lot_size=trade.lot_size,
        estimated_risk_cash=trade.estimated_risk_cash,
        cash_pnl=None if multiple is None else _cash(move, spec, trade.lot_size),
        r_multiple=None if multiple is None else round(multiple, 8),
        status=status,
        exit_reason=reason,
    )


def _trade_shot(candles: list[Candle], trade: TradeRecord, levels: list) -> dict:
    named = [dict(level) for level in levels]
    have = {item.get("name") for item in named}
    for name, price in (("Entry", trade.entry), ("Stop", trade.stop_loss), ("Target", trade.take_profit)):
        if name not in have and isinstance(price, (int, float)) and math.isfinite(price):
            named.append({"name": name, "price": price})
    start = trade.signal_time - (6 * H1_SECONDS)
    end_time = trade.exit_time if trade.exit_time is not None else trade.entry_time
    end = max(end_time, trade.entry_time) + (2 * H1_SECONDS)
    window = [candle for candle in candles if start <= candle.time <= end]
    if len(window) > 20:
        window = window[-20:]
    return {
        "candles": [
            {"time": candle.time, "open": candle.open, "high": candle.high, "low": candle.low, "close": candle.close}
            for candle in window
        ],
        "levels": named,
        "mark_time": trade.signal_time,
    }


def summarize(trades: list[TradeRecord], skipped: list[SkipRecord], reward_multiple: float = REWARD_MULTIPLE) -> dict:
    resolved = [trade for trade in trades if trade.r_multiple is not None]
    wins = [trade for trade in resolved if trade.status == "win"]
    losses = [trade for trade in resolved if trade.status == "loss"]
    net_r = round(sum(trade.r_multiple or 0 for trade in resolved), 8)
    gross_loss = abs(sum(trade.r_multiple or 0 for trade in losses))
    gross_win = sum(trade.r_multiple or 0 for trade in wins)
    streak = worst = 0
    for trade in trades:
        if trade.status == "loss":
            streak += 1
            worst = max(worst, streak)
        elif trade.status == "win":
            streak = 0
    return {
        "trades": len(trades),
        "resolved_trades": len(resolved),
        "wins": len(wins),
        "losses": len(losses),
        "unresolved": sum(1 for trade in trades if trade.status == "unresolved"),
        "net_r": net_r,
        "profit_factor_r": None if gross_loss == 0 else round(gross_win / gross_loss, 4),
        "max_consecutive_losses": worst,
        "skipped": len(skipped),
        "win_rate": None if not resolved else round(len(wins) / len(resolved), 4),
        "expectancy_r": None if not resolved else round(net_r / len(resolved), 8),
        "average_win_r": None if not wins else round(sum(trade.r_multiple or 0 for trade in wins) / len(wins), 8),
        "average_loss_r": None if not losses else round(sum(trade.r_multiple or 0 for trade in losses) / len(losses), 8),
        "risk_fraction": RISK_FRACTION,
        "reward_multiple": reward_multiple,
        "max_trades_per_day": MAX_TRADES_PER_DAY,
    }


def run_backtest(
    h4: list[Candle],
    h1: list[Candle],
    *,
    symbol: str,
    spec: SymbolSpec | None,
    spread: float,
    spread_source: str,
    starting_equity: float,
    source: str,
    now: float | None = None,
    evaluate: Callable[..., Evaluation] | None = None,
    rules_source: str = RULES_SOURCE,
    limits: dict | None = None,
) -> BacktestReport:
    saved = limits or {}
    risk_fraction = float(saved.get("risk_fraction", RISK_FRACTION))
    reward_multiple = float(saved.get("reward_multiple", TARGET_R))
    max_stop_pips = float(saved.get("max_stop_pips", MAX_STOP_PIPS))
    max_trades_per_day = int(saved.get("max_trades_per_day", MAX_TRADES_PER_DAY))
    higher = closed_candles(h4, 4 * H1_SECONDS, now)
    opened = _opened_candles(h4, now)
    lower = closed_candles(h1, H1_SECONDS, now)
    if evaluate is None:
        trades, skipped, _state = _simulate(
            opened, lower, symbol=symbol, spec=spec, spread=spread, starting_equity=starting_equity,
            risk_fraction=risk_fraction, reward_multiple=reward_multiple,
            max_stop_pips=max_stop_pips, max_trades_per_day=max_trades_per_day,
        )
        resolved_cash = [trade.cash_pnl for trade in trades if trade.status in {"win", "loss"}]
        ending = None if any(value is None for value in resolved_cash) else starting_equity + sum(resolved_cash)
        return BacktestReport(
            symbol=symbol, source=source, spread=spread, spread_source=spread_source,
            starting_equity=starting_equity, ending_equity=None if ending is None else round(ending, 2),
            from_time=lower[0].time if lower else None, to_time=lower[-1].time if lower else None,
            bars_h1=len(lower), bars_h4=len(opened), rules_source=rules_source, execution_enabled=False,
            summary=summarize(trades, skipped, reward_multiple), trades=trades, skipped=skipped,
        )
    equity = starting_equity
    open_trade: TradeRecord | None = None
    open_levels: list = []
    trades: list[TradeRecord] = []
    skipped: list[SkipRecord] = []
    day_counts: dict[str, int] = {}
    digits = spec.digits if spec is not None else 2
    recorded_reasons = {
        "daily_limit",
        "position_open",
        "below_min_lot",
        "stop_too_small",
        "invalid_geometry",
        "invalid_symbol_spec",
        "invalid_prices",
        "stop_too_wide",
    }

    for index in range(2, len(lower)):
        candle = lower[index]
        if open_trade is not None:
            outcome = _exit_on_candle(open_trade.direction, open_trade.stop_loss, open_trade.take_profit, candle)
            if outcome is not None:
                exit_price, reason = outcome
                closed = _book(open_trade, exit_price, reason, candle.time, spec)
                closed = _apply_planned_cash(closed, equity, risk_fraction)
                closed.shot = _trade_shot(lower, closed, open_levels)
                trades.append(closed)
                if closed.cash_pnl is not None:
                    equity += closed.cash_pnl
                open_trade = None
                open_levels = []
            continue

        signal = lower[index - 1]
        previous = lower[index - 2]
        day = datetime.fromtimestamp(signal.time, timezone.utc).date().isoformat()
        evaluation = (evaluate or evaluate_setup)(
            symbol=symbol,
            h4=higher,
            h1=lower[:index],
            previous=previous,
            signal=signal,
            bid=candle.open,
            ask=candle.open,
            spread=spread,
            equity=equity,
            spec=spec,
            trades_today=day_counts.get(day, 0),
            position_open=False,
            require_lots=False,
            bar_low=candle.low,
            bar_high=candle.high,
        )
        if evaluation.proposal is None:
            if evaluation.skip_reason in recorded_reasons and evaluation.signal_time is not None:
                direction = "buy" if evaluation.bias == "long" else "sell" if evaluation.bias == "short" else None
                skipped.append(SkipRecord(evaluation.signal_time, evaluation.skip_reason, direction))
            continue

        proposal = evaluation.proposal
        day_counts[day] = day_counts.get(day, 0) + 1
        planned = proposal.estimated_risk_cash
        if planned is None:
            planned = equity * risk_fraction
        opened = TradeRecord(
            direction=proposal.direction,
            signal_time=proposal.signal_time,
            entry_time=candle.time,
            exit_time=None,
            entry=proposal.entry,
            stop_loss=proposal.stop_loss,
            take_profit=proposal.take_profit,
            exit_price=None,
            lot_size=proposal.lot_size,
            estimated_risk_cash=None if planned is None else round(planned, 2),
            cash_pnl=None,
            r_multiple=None,
            status="open",
            exit_reason="open",
        )
        outcome = _exit_on_candle(opened.direction, opened.stop_loss, opened.take_profit, candle)
        if outcome is None:
            open_trade = opened
            open_levels = list(evaluation.levels)
            continue
        exit_price, reason = outcome
        closed = _book(opened, exit_price, reason, candle.time, spec)
        closed = _apply_planned_cash(closed, equity, risk_fraction)
        closed.shot = _trade_shot(lower, closed, evaluation.levels)
        trades.append(closed)
        if closed.cash_pnl is not None:
            equity += closed.cash_pnl

    if open_trade is not None:
        trades.append(
            TradeRecord(
                direction=open_trade.direction,
                signal_time=open_trade.signal_time,
                entry_time=open_trade.entry_time,
                exit_time=None,
                entry=open_trade.entry,
                stop_loss=open_trade.stop_loss,
                take_profit=open_trade.take_profit,
                exit_price=None,
                lot_size=open_trade.lot_size,
                estimated_risk_cash=open_trade.estimated_risk_cash,
                cash_pnl=None,
                r_multiple=None,
                status="unresolved",
                exit_reason="unresolved",
                shot=_trade_shot(lower, open_trade, open_levels),
            )
        )

    resolved_cash = [trade.cash_pnl for trade in trades if trade.status in {"win", "loss"}]
    ending = None if any(value is None for value in resolved_cash) else starting_equity + sum(resolved_cash)
    return BacktestReport(
        symbol=symbol,
        source=source,
        spread=spread,
        spread_source=spread_source,
        starting_equity=starting_equity,
        ending_equity=None if ending is None else round(ending, 2),
        from_time=lower[0].time if lower else None,
        to_time=lower[-1].time if lower else None,
        bars_h1=len(lower),
        bars_h4=len(higher),
        rules_source=rules_source,
        execution_enabled=False,
        summary=summarize(trades, skipped),
        trades=trades,
        skipped=skipped,
    )


def scan_latest(
    *,
    symbol: str,
    h4: list[Candle],
    h1: list[Candle],
    bid: float,
    ask: float,
    equity: float,
    spec: SymbolSpec | None,
    trades_today: int,
    position_open: bool,
    now: float,
    risk_fraction: float = RISK_FRACTION,
    reward_multiple: float = TARGET_R,
    max_stop_pips: float = MAX_STOP_PIPS,
    max_trades_per_day: int = MAX_TRADES_PER_DAY,
) -> Evaluation:
    higher = _opened_candles(h4, now)
    lower = closed_candles(h1, H1_SECONDS, now)
    _trades, skipped, state = _simulate(
        higher,
        lower,
        symbol=symbol,
        spec=spec,
        spread=0.0,
        starting_equity=equity,
        risk_fraction=risk_fraction,
        reward_multiple=reward_multiple,
        max_stop_pips=max_stop_pips,
        max_trades_per_day=max_trades_per_day,
        paper_fills=False,
    )
    pending = state["pending"]
    bias_name = "long" if state["bias"] == 1 else "short" if state["bias"] == -1 else "neutral"
    checks = {
        "enough_h4": state["ref_high"] is not None,
        "h4_bias": state["bias"] != 0,
        "h1_setup": pending is not None,
        "retest": False,
        "stop_cap": False,
    }
    if len(lower) < 2 or state["ref_high"] is None:
        return Evaluation("neutral", None, "not_enough_candles", lower[-1].time if lower else None, checks)
    if pending is None:
        recent = [item for item in skipped if item.signal_time == lower[-1].time]
        reason = recent[-1].reason if recent else "neutral_bias" if state["bias"] == 0 else "no_setup"
        return Evaluation(bias_name, None, reason, lower[-1].time, checks)
    if position_open:
        return Evaluation(bias_name, None, "position_open", pending["setup_time"], checks)
    level = float(pending["level"])
    previous = pending.get("last_quote")
    if pending["direction"] == 1:
        touched = previous is not None and previous > level and bid <= level
        entry, stop, side = ask, float(pending["sl"]), "buy"
    else:
        touched = previous is not None and previous < level and ask >= level
        entry, stop, side = bid, float(pending["sl"]), "sell"
    if not touched:
        return Evaluation(bias_name, None, "waiting_retest", pending["setup_time"], checks)
    checks["retest"] = True
    digits = spec.digits if spec is not None else 2
    entry, stop = round_price(entry, digits), round_price(stop, digits)
    risk = entry - stop if side == "buy" else stop - entry
    if risk <= 0 or not math.isfinite(entry):
        return Evaluation(bias_name, None, "invalid_geometry", pending["setup_time"], checks)
    checks["stop_cap"] = True
    if trades_today >= max_trades_per_day:
        return Evaluation(bias_name, None, "daily_limit", pending["setup_time"], checks)
    sized = size_position(equity, risk, spec, require_lots=True, risk_fraction=risk_fraction)
    if sized.error:
        return Evaluation(bias_name, None, sized.error, pending["setup_time"], checks)
    target = round_price(
        entry + reward_multiple * risk if side == "buy" else entry - reward_multiple * risk,
        digits,
    )
    day = _day_key(int(now))
    proposal = Proposal(
        symbol=symbol, direction=side, signal_time=pending["setup_time"], entry=entry, stop_loss=stop,
        take_profit=target, stop_distance=round_price(risk, digits), lot_size=sized.lots,
        estimated_risk_cash=None if sized.cash_risk is None else round(sized.cash_risk, 2),
        capped=sized.capped, dedupe_key=f"{symbol}:{side}:{pending['setup_time']}:{day}",
        expires_at=int(now) + 6 * H1_SECONDS,
    )
    return Evaluation(bias_name, proposal, None, pending["setup_time"], checks, _levels(pending, entry, stop, target))


KEEP_SKIP_REASONS = {
    "daily_limit",
    "position_open",
    "below_min_lot",
    "stop_too_small",
    "invalid_geometry",
    "invalid_symbol_spec",
    "invalid_prices",
    "not_enough_candles",
    "stop_too_wide",
}
