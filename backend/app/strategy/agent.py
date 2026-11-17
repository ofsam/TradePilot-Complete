"""Research backtest. This is not the live H4-bias / H1-retest bot and it does not send orders.

H4 direction comes from a 20-period EMA. An H1 entry must sweep the previous
hour and close back through it. The stop sits beyond that sweep.
"""

from app.strategy.candles import H1_SECONDS, visible_h4
from app.strategy.engine import Evaluation, Proposal
from app.strategy.risk import REWARD_MULTIPLE, SizeResult, round_price, size_position
from app.strategy.structure import ema_series

AGENT_RULES_SOURCE = "h4_ema_h1_reclaim"
EMA_PERIOD = 20
SLOPE_BARS = 3
MIN_STOP_DISTANCE = 0.5
MAX_STOP_DISTANCE = 15.0


def evaluate_agent(
    *,
    symbol: str,
    h4,
    h1,
    previous,
    signal,
    bid: float,
    ask: float,
    spread: float,
    equity: float,
    spec,
    trades_today: int,
    position_open: bool,
    require_lots: bool,
    bar_low: float | None = None,
    bar_high: float | None = None,
) -> Evaluation:
    del h1, bar_low, bar_high
    checks = {"enough_h4": False, "h4_trend": False, "sweep": False, "reclaim": False, "stop_size": False}
    visible = visible_h4(h4, signal.time + H1_SECONDS)
    if len(visible) < EMA_PERIOD + SLOPE_BARS:
        return Evaluation("neutral", None, "not_enough_candles", signal.time, checks)
    checks["enough_h4"] = True
    series = ema_series([candle.close for candle in visible], EMA_PERIOD)
    last_close = visible[-1].close
    rising = series[-1] > series[-1 - SLOPE_BARS]
    falling = series[-1] < series[-1 - SLOPE_BARS]
    if last_close > series[-1] and rising:
        bias = "long"
    elif last_close < series[-1] and falling:
        bias = "short"
    else:
        return Evaluation("neutral", None, "neutral_bias", signal.time, checks)
    checks["h4_trend"] = True

    if bias == "long":
        swept = signal.low < previous.low
        reclaimed = signal.close > signal.open and signal.close > previous.high
        stop = min(signal.low, previous.low)
        entry = bid + spread
        direction = "buy"
    else:
        swept = signal.high > previous.high
        reclaimed = signal.close < signal.open and signal.close < previous.low
        stop = max(signal.high, previous.high)
        entry = ask - spread
        direction = "sell"
    checks["sweep"] = swept
    checks["reclaim"] = reclaimed
    if not swept or not reclaimed:
        return Evaluation(bias, None, "no_setup", signal.time, checks)

    digits = spec.digits if spec is not None else 2
    entry = round_price(entry, digits)
    stop = round_price(stop, digits)
    distance = round_price(abs(entry - stop), digits)
    geometry_ok = (direction == "buy" and entry > stop) or (direction == "sell" and entry < stop)
    if not geometry_ok or distance <= 0:
        return Evaluation(bias, None, "invalid_geometry", signal.time, checks)
    if distance < MIN_STOP_DISTANCE:
        return Evaluation(bias, None, "stop_too_small", signal.time, checks)
    if distance > MAX_STOP_DISTANCE:
        return Evaluation(bias, None, "stop_too_wide", signal.time, checks)
    checks["stop_size"] = True
    if position_open:
        return Evaluation(bias, None, "position_open", signal.time, checks)
    if trades_today >= 2:
        return Evaluation(bias, None, "daily_limit", signal.time, checks)
    sized: SizeResult = size_position(equity, distance, spec, require_lots=require_lots)
    if sized.error:
        return Evaluation(bias, None, sized.error, signal.time, checks)
    take_profit = round_price(
        entry + REWARD_MULTIPLE * distance if direction == "buy" else entry - REWARD_MULTIPLE * distance,
        digits,
    )
    proposal = Proposal(
        symbol=symbol,
        direction=direction,
        signal_time=signal.time,
        entry=entry,
        stop_loss=stop,
        take_profit=take_profit,
        stop_distance=distance,
        lot_size=sized.lots,
        estimated_risk_cash=None if sized.cash_risk is None else round(sized.cash_risk, 2),
        capped=sized.capped,
        dedupe_key=f"{symbol}:{direction}:{signal.time}",
        expires_at=signal.time + (2 * H1_SECONDS),
    )
    return Evaluation(bias, proposal, None, signal.time, checks, [
        {"name": "H4 EMA", "price": round(series[-1], 2)},
        {"name": "Entry", "price": entry},
        {"name": "Stop", "price": stop},
        {"name": "Target", "price": take_profit},
    ])
