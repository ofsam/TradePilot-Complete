import sys
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any
from app.config import settings
from app.market import crypto
from app.mt5.execution import MAGIC, ExecutionRefused, filling_type, plan_demo_order
from app.strategy.risk import SymbolSpec, round_price

class MT5Unavailable(RuntimeError):
    pass


def _accra_midnight() -> int:
    now = datetime.now(ZoneInfo("Africa/Accra"))
    return int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

class ReadOnlyMT5Adapter:
    # Quotes, history, and positions are read here. The only order call is send_demo_order,
    # and that method returns before sending unless the logged-in account is demo or live.
    # symbol_select is used so history and quotes can be read. It adds the symbol to Market Watch.
    # BTCUSD/ETHUSD fall back to Coinbase public candles when this terminal does not list them
    # (same feed the TradingView chart uses).
    def __init__(self):
        self._mt5 = None
        self._initialized = False
        self._lock = threading.RLock()
        self._listed: set[str] = set()

    def _module(self):
        if sys.platform != "win32":
            raise MT5Unavailable("Run the MT5 adapter on Windows with MT5 desktop installed.")
        if self._mt5 is None:
            try:
                import MetaTrader5 as mt5
            except ImportError as exc:
                raise MT5Unavailable("Install the MetaTrader5 Python package on Windows.") from exc
            self._mt5 = mt5
        return self._mt5

    def connect(self) -> dict[str, Any]:
        mt5 = self._module()
        path = settings.mt5_terminal_path.strip()
        with self._lock:
            ok = mt5.initialize(path=path) if path else mt5.initialize()
            if not ok:
                self._initialized = False
                raise MT5Unavailable(f"MT5 initialize failed: {mt5.last_error()}")
            terminal, account = mt5.terminal_info(), mt5.account_info()
            if terminal is None or account is None:
                mt5.shutdown()
                self._initialized = False
                raise MT5Unavailable(f"Terminal/account unavailable: {mt5.last_error()}")
            self._initialized = True
            self._listed.clear()
            return self._payload(mt5, terminal, account)

    def disconnect(self):
        with self._lock:
            if self._mt5 is not None and self._initialized:
                self._mt5.shutdown()
            self._initialized = False
            return {"connected": False, "adapter_mode": "read_only"}

    def status(self):
        with self._lock:
            mt5 = self._require()
            terminal, account = mt5.terminal_info(), mt5.account_info()
            if terminal is None or account is None:
                self._initialized = False
                raise MT5Unavailable("MT5 terminal disconnected or account unavailable.")
            return self._payload(mt5, terminal, account)

    def symbols(self, names: list[str]):
        with self._lock:
            mt5 = self._require()
            result = []
            for name in names:
                broker = self._resolve_symbol(mt5, name)
                info = mt5.symbol_info(broker) if broker else None
                if info is None and self._uses_public(mt5, name):
                    # Research contract for Coinbase BTC/ETH: $1 per point per lot so
                    # the same 2% risk / 5R rules size and mark cash without an MT5 spec.
                    pip = float(crypto.PIP)
                    result.append({
                        "symbol": name,
                        "available": True,
                        "visible": True,
                        "public_candles": True,
                        "digits": 2,
                        "point": pip,
                        "trade_contract_size": 1.0,
                        "volume_min": 0.01,
                        "volume_max": 1000.0,
                        "volume_step": 0.01,
                        "trade_tick_size": pip,
                        "trade_tick_value": 1.0,
                        "filling_mode": 0,
                    })
                elif info is None:
                    result.append({"symbol": name, "available": False})
                else:
                    row = {
                        "symbol": name, "available": True, "visible": bool(info.visible),
                        "digits": int(info.digits), "point": float(info.point),
                        "trade_contract_size": float(info.trade_contract_size),
                        "volume_min": float(info.volume_min), "volume_max": float(info.volume_max),
                        "volume_step": float(info.volume_step), "trade_tick_size": float(info.trade_tick_size),
                        "trade_tick_value": float(info.trade_tick_value),
                        "filling_mode": int(getattr(info, "filling_mode", 0)),
                    }
                    if broker != name:
                        row["broker_symbol"] = broker
                    result.append(row)
            return result

    def _resolve_symbol(self, mt5, symbol: str) -> str | None:
        """Map watchlist names (EURUSD) to broker names (EURUSDm on Exness)."""
        raw = (symbol or "").strip()
        if not raw:
            return None
        if mt5.symbol_info(raw) is not None:
            return raw
        upper = raw.upper()
        candidates: list[str] = []
        for suf in ("m", ".m", "_m", "pro", ".pro"):
            candidates.append(raw + suf)
            candidates.append(upper + suf)
        for name in candidates:
            if mt5.symbol_info(name) is not None:
                return name
        listed = mt5.symbols_get()
        if listed:
            by_upper = {str(item.name).upper(): item.name for item in listed}
            if upper in by_upper:
                return by_upper[upper]
            for suf in ("M", ".M", "_M", "PRO", ".PRO"):
                hit = by_upper.get(upper + suf)
                if hit:
                    return hit
        return None

    def _ensure_selected(self, mt5, symbol: str) -> str:
        broker = self._resolve_symbol(mt5, symbol)
        if broker is None:
            raise MT5Unavailable(
                f"{symbol} is not listed on this terminal. Pick a Market Watch symbol this broker provides."
            )
        info = mt5.symbol_info(broker)
        if info is None:
            raise MT5Unavailable(
                f"{symbol} is not listed on this terminal. Pick a Market Watch symbol this broker provides."
            )
        if info.visible:
            return broker
        if not mt5.symbol_select(broker, True):
            raise MT5Unavailable(
                f"{broker} could not be added to Market Watch: {mt5.last_error()}"
            )
        return broker

    def tick(self, symbol: str):
        with self._lock:
            mt5 = self._require()
            if self._uses_public(mt5, symbol):
                return self._from_public(lambda: crypto.ticker(symbol))
            broker = self._ensure_selected(mt5, symbol)
            tick = mt5.symbol_info_tick(broker)
            if tick is None:
                raise MT5Unavailable(f"No tick for {symbol}: {mt5.last_error()}")
            return {"symbol": symbol, "broker_symbol": broker, "time": int(tick.time), "bid": float(tick.bid),
                    "ask": float(tick.ask), "last": float(tick.last), "volume": int(tick.volume)}

    def positions(self):
        with self._lock:
            mt5 = self._require()
            positions = mt5.positions_get()
            if positions is None:
                raise MT5Unavailable(f"Could not read positions: {mt5.last_error()}")
            return [{"ticket": int(p.ticket), "symbol": p.symbol, "type": int(p.type),
                     "volume": float(p.volume), "price_open": float(p.price_open),
                     "price_current": float(p.price_current), "sl": float(p.sl), "tp": float(p.tp),
                     "profit": float(p.profit), "swap": float(p.swap), "magic": int(p.magic),
                     "comment": p.comment} for p in positions]

    def rates(self, symbol: str, timeframe: str, count: int) -> list[dict[str, Any]]:
        if timeframe not in {"H1", "H4"}:
            raise MT5Unavailable("Only H1 and H4 history are available in this build.")
        if count < 10 or count > 5000:
            raise MT5Unavailable("History count must be between 10 and 5000 bars.")
        fallback = 16385 if timeframe == "H1" else 16388
        with self._lock:
            mt5 = self._require()
            if self._uses_public(mt5, symbol):
                return self._from_public(lambda: crypto.recent(symbol, timeframe, count))
            broker = self._ensure_selected(mt5, symbol)
            raw = mt5.copy_rates_from_pos(broker, getattr(mt5, f"TIMEFRAME_{timeframe}", fallback), 0, count)
            if raw is None or len(raw) == 0:
                raise MT5Unavailable(f"No {timeframe} rates for {symbol}: {mt5.last_error()}")
            return [{
                "time": int(bar["time"]), "open": float(bar["open"]), "high": float(bar["high"]),
                "low": float(bar["low"]), "close": float(bar["close"]),
            } for bar in raw]

    def rates_range(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        if timeframe not in {"H1", "H4"}:
            raise MT5Unavailable("Only H1 and H4 history are available in this build.")
        if end < start:
            raise MT5Unavailable("The end date is before the start date.")
        if (end - start).days > 405:
            raise MT5Unavailable("Choose a range of 365 days or less.")
        fallback = 16385 if timeframe == "H1" else 16388
        start_utc = start.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc = end.astimezone(timezone.utc).replace(tzinfo=None)
        with self._lock:
            mt5 = self._require()
            if self._uses_public(mt5, symbol):
                return self._from_public(lambda: crypto.range_bars(symbol, timeframe, start, end))
            broker = self._ensure_selected(mt5, symbol)
            raw = mt5.copy_rates_range(broker, getattr(mt5, f"TIMEFRAME_{timeframe}", fallback), start_utc, end_utc)
            if raw is None or len(raw) == 0:
                raise MT5Unavailable(f"No {timeframe} candles for {symbol} in that date range: {mt5.last_error()}")
            return [{
                "time": int(bar["time"]), "open": float(bar["open"]), "high": float(bar["high"]),
                "low": float(bar["low"]), "close": float(bar["close"]),
            } for bar in raw]

    def deals(self, days: int = 30) -> list[dict[str, Any]]:
        days = min(max(days, 1), 365)
        with self._lock:
            mt5 = self._require()
            now = datetime.now()
            raw = mt5.history_deals_get(now - timedelta(days=days), now)
            if raw is None:
                raise MT5Unavailable(f"Could not read deal history: {mt5.last_error()}")
            return [{
                "ticket": int(deal.ticket), "symbol": deal.symbol, "type": int(deal.type),
                "entry": int(deal.entry), "volume": float(deal.volume), "price": float(deal.price),
                "profit": float(deal.profit), "swap": float(deal.swap), "commission": float(deal.commission),
                "magic": int(deal.magic), "time": int(deal.time),
            } for deal in raw]

    def portfolio(self, days: int = 30) -> dict[str, Any]:
        with self._lock:
            account = self.status()
            positions = self.positions()
            try:
                deals = self.deals(days)
                history_error = None
            except MT5Unavailable as exc:
                deals = []
                history_error = str(exc)
        specs: dict[str, SymbolSpec | None] = {}
        stop_risk = 0.0
        risk_known = True
        unprotected = 0
        for position in positions:
            name = position["symbol"]
            if name not in specs:
                info = self.symbols([name])[0]
                specs[name] = _spec(info)
            spec = specs[name]
            sl = float(position["sl"])
            if sl <= 0 or spec is None:
                unprotected += 1
                risk_known = False
                continue
            distance = position["price_current"] - sl if position["type"] == 0 else sl - position["price_current"]
            if distance <= 0:
                continue
            stop_risk += (distance / spec.trade_tick_size) * spec.trade_tick_value * float(position["volume"])
        floating = sum(float(position["profit"]) + float(position["swap"]) for position in positions)
        margin = float(account.get("margin") or 0)
        equity = float(account.get("equity") or 0)
        closed = [deal for deal in deals if deal["type"] in (0, 1) and deal["entry"] in (1, 2, 3)]
        opened = _accra_midnight()
        entries_today = [
            deal for deal in deals
            if deal["magic"] == MAGIC and deal["entry"] == 0 and deal["time"] >= opened
        ]
        return {
            "account": account,
            "positions": positions,
            "floating_pnl": round(floating, 2),
            "margin_level": None if margin <= 0 else round(equity / margin * 100, 2),
            "stop_risk_cash": None if not risk_known else round(stop_risk, 2),
            "unprotected_positions": unprotected,
            "open_positions": len(positions),
            "history_days": days,
            "history_error": history_error,
            "closed_trades": len(closed),
            "wins": sum(1 for deal in closed if deal["profit"] > 0),
            "losses": sum(1 for deal in closed if deal["profit"] < 0),
            "net_profit": round(sum(deal["profit"] + deal["swap"] + deal["commission"] for deal in closed), 2),
            "our_entries_today": len(entries_today),
            "max_trades_per_day": 2,
            "execution": "confirm" if account.get("environment") in {"demo", "live"} else "blocked",
            "order_submitted": False,
        }

    def send_demo_order(
        self,
        *,
        symbol: str,
        direction: str,
        stop: float,
        scanned_entry: float,
        scanned_distance: float,
        expires_at: float | None,
        risk_fraction: float | None = None,
        reward_multiple: float | None = None,
        max_trades_per_day: int | None = None,
        max_stop_pips: float | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            mt5 = self._require()
            terminal, account_info = mt5.terminal_info(), mt5.account_info()
            if terminal is None or account_info is None:
                raise MT5Unavailable("MT5 terminal disconnected or account unavailable.")
            account = self._payload(mt5, terminal, account_info)
            if account.get("environment") not in {"demo", "live"}:
                raise ExecutionRefused("Orders are sent only on a demo or live account.")
            broker = self._resolve_symbol(mt5, symbol)
            info = mt5.symbol_info(broker) if broker else None
            tick = mt5.symbol_info_tick(broker) if broker else None
            if broker is None or info is None or tick is None:
                raise ExecutionRefused(f"{symbol} has no live quote on this terminal.")
            if not info.visible and not mt5.symbol_select(broker, True):
                raise ExecutionRefused(f"{broker} could not be added to Market Watch: {mt5.last_error()}")
            positions = mt5.positions_get(symbol=broker)
            if positions is None:
                raise ExecutionRefused(f"Could not read open positions: {mt5.last_error()}")
            price = float(tick.ask if direction == "buy" else tick.bid)
            plan_kwargs: dict[str, Any] = {
                "environment": account["environment"],
                "trade_allowed": bool(account["trade_allowed"]),
                "direction": direction,
                "price": price,
                "stop": stop,
                "scanned_entry": scanned_entry,
                "scanned_distance": scanned_distance,
                "equity": float(account.get("equity") if account.get("equity") is not None else account.get("balance") or 0),
                "spec": _spec({
                    "point": info.point, "trade_tick_size": info.trade_tick_size,
                    "trade_tick_value": info.trade_tick_value, "volume_min": info.volume_min,
                    "volume_max": info.volume_max, "volume_step": info.volume_step, "digits": info.digits,
                }),
                "trades_today": self._entries_today_locked(mt5, broker),
                "position_open": len(positions) > 0,
                "now": datetime.now(timezone.utc).timestamp(),
                "expires_at": expires_at,
            }
            if risk_fraction is not None:
                plan_kwargs["risk_fraction"] = float(risk_fraction)
            if reward_multiple is not None:
                plan_kwargs["reward_multiple"] = float(reward_multiple)
            if max_trades_per_day is not None:
                plan_kwargs["max_trades_per_day"] = int(max_trades_per_day)
            if max_stop_pips is not None:
                plan_kwargs["max_stop_pips"] = float(max_stop_pips)
            plan, reason = plan_demo_order(**plan_kwargs)
            if plan is None:
                raise ExecutionRefused(reason or "The order was not sent.")
            request = {
                "action": getattr(mt5, "TRADE_ACTION_DEAL", 1),
                "symbol": broker,
                "volume": float(plan.lots),
                "type": getattr(mt5, "ORDER_TYPE_BUY", 0) if direction == "buy" else getattr(mt5, "ORDER_TYPE_SELL", 1),
                "price": float(plan.price),
                "sl": float(plan.stop),
                "tp": float(plan.target),
                "deviation": 30,
                "magic": MAGIC,
                "comment": "H4H1_RR5",
                "type_time": getattr(mt5, "ORDER_TIME_GTC", 0),
                "type_filling": filling_type(int(getattr(info, "filling_mode", 0))),
            }
            result = mt5.order_send(request)
            done = {getattr(mt5, "TRADE_RETCODE_DONE", 10009), getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010)}
            if result is None or int(getattr(result, "retcode", -1)) not in done:
                comment = getattr(result, "comment", None) if result is not None else None
                raise ExecutionRefused(comment or f"MT5 rejected the order: {mt5.last_error()}")
            return {
                "order_submitted": True,
                "ticket": int(getattr(result, "order", 0) or getattr(result, "deal", 0) or 0),
                "deal": int(getattr(result, "deal", 0) or 0),
                "symbol": symbol,
                "broker_symbol": broker,
                "direction": direction,
                "volume": float(getattr(result, "volume", plan.lots) or plan.lots),
                "price": float(getattr(result, "price", plan.price) or plan.price),
                "stop_loss": plan.stop,
                "take_profit": plan.target,
                "estimated_risk": plan.cash_risk,
                "retcode": int(result.retcode),
                "comment": getattr(result, "comment", ""),
                "auto_execution": False,
            }

    def entries_today(self, symbol: str) -> int:
        with self._lock:
            mt5 = self._require()
            broker = self._resolve_symbol(mt5, symbol) or symbol
            return self._entries_today_locked(mt5, broker)

    def _entries_today_locked(self, mt5, symbol: str) -> int:
        opened = _accra_midnight()
        raw = mt5.history_deals_get(datetime.fromtimestamp(opened - 86400), datetime.now())
        if raw is None:
            raise ExecutionRefused(f"Could not verify today's trade count: {mt5.last_error()}")
        want = symbol.upper()
        bare = want[:-1] if want.endswith("M") and len(want) > 1 else want
        return sum(
            1 for deal in raw
            if str(deal.symbol).upper() in {want, bare, bare + "M"}
            and int(deal.magic) == MAGIC
            and int(deal.entry) == 0
            and int(deal.time) >= opened
        )

    def snapshot(self, symbol: str, h1_count: int, h4_count: int) -> dict[str, Any]:
        with self._lock:
            return {
                "account": self.status(),
                "symbol": self.symbols([symbol])[0],
                "tick": self.tick(symbol),
                "positions": self.positions(),
                "h1": self.rates(symbol, "H1", h1_count),
                "h4": self.rates(symbol, "H4", h4_count),
            }

    def uses_public_candles(self, symbol: str) -> bool:
        with self._lock:
            return self._uses_public(self._require(), symbol)

    def _uses_public(self, mt5, symbol: str) -> bool:
        key = symbol.upper()
        if crypto.product(key) is None:
            return False
        if key in self._listed:
            return False
        if self._resolve_symbol(mt5, symbol) is not None:
            self._listed.add(key)
            return False
        return True

    def _from_public(self, load):
        try:
            return load()
        except crypto.MarketDataError as exc:
            raise MT5Unavailable(str(exc)) from exc

    def _payload(self, mt5, terminal, account) -> dict[str, Any]:
        mode = getattr(account, "trade_mode", None)
        if mode == getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0):
            environment = "demo"
        elif mode == getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", 2):
            environment = "live"
        elif mode == getattr(mt5, "ACCOUNT_TRADE_MODE_CONTEST", 1):
            environment = "contest"
        else:
            environment = "unknown"
        from app.execution_gate import is_execution_enabled

        return {
            "connected": True,
            "adapter_mode": "execute" if is_execution_enabled() else "read_only",
            "environment": environment,
            "terminal_connected": bool(getattr(terminal, "connected", False)),
            "terminal_name": getattr(terminal, "name", None),
            "broker_server": getattr(account, "server", None),
            "login": str(getattr(account, "login", "")),
            "account_company": getattr(account, "company", None),
            "currency": getattr(account, "currency", None),
            # Both flags must be on: account trading + Algo Trading in the terminal.
            "trade_allowed": bool(getattr(account, "trade_allowed", False))
            and bool(getattr(terminal, "trade_allowed", False)),
            "balance": float(getattr(account, "balance", 0.0)),
            "equity": float(getattr(account, "equity", 0.0)),
            "margin": float(getattr(account, "margin", 0.0)),
            "free_margin": float(getattr(account, "margin_free", 0.0)),
        }

    def _require(self):
        if not self._initialized:
            raise MT5Unavailable("MT5 is not connected. Call POST /api/v1/mt5/connect first.")
        mt5 = self._module()
        if mt5.terminal_info() is None or mt5.account_info() is None:
            self._initialized = False
            raise MT5Unavailable("MT5 connection lost.")
        return mt5

def _spec(info: dict) -> SymbolSpec | None:
    try:
        spec = SymbolSpec(
            point=float(info["point"]), trade_tick_size=float(info["trade_tick_size"]),
            trade_tick_value=float(info["trade_tick_value"]), volume_min=float(info["volume_min"]),
            volume_max=float(info["volume_max"]), volume_step=float(info["volume_step"]),
            digits=int(info["digits"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    return spec if spec.valid() else None

mt5_adapter = ReadOnlyMT5Adapter()
