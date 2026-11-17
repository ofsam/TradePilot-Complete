import math
from dataclasses import dataclass

from app.strategy.engine import MIN_STOP_DISTANCE, TARGET_R
from app.strategy.risk import RISK_FRACTION, SymbolSpec, round_price, size_position

MAGIC = 20261030
DEVIATION_POINTS = 20
MAX_TRADES_PER_DAY = 2
ORDER_FILLING_FOK = 0
ORDER_FILLING_IOC = 1
ORDER_FILLING_RETURN = 2


class ExecutionRefused(Exception):
    pass


@dataclass(frozen=True)
class OrderPlan:
    lots: float
    price: float
    stop: float
    target: float
    cash_risk: float
    capped: bool


def filling_type(filling_mode: int) -> int:
    if filling_mode & 1:
        return ORDER_FILLING_FOK
    if filling_mode & 2:
        return ORDER_FILLING_IOC
    return ORDER_FILLING_RETURN


def plan_demo_order(
    *,
    environment: str,
    trade_allowed: bool,
    direction: str,
    price: float,
    stop: float,
    scanned_entry: float,
    scanned_distance: float,
    equity: float,
    spec: SymbolSpec | None,
    trades_today: int,
    position_open: bool,
    now: float,
    expires_at: float | None,
    risk_fraction: float = RISK_FRACTION,
    reward_multiple: float = TARGET_R,
    max_trades_per_day: int = MAX_TRADES_PER_DAY,
    max_stop_pips: float | None = None,
) -> tuple[OrderPlan | None, str | None]:
    del max_stop_pips  # Enforced at scan time; live send re-checks geometry only.
    if environment not in {"demo", "live"}:
        return None, "Orders are sent only on a demo or live account."
    if not trade_allowed:
        return None, "The terminal is not allowing trading on this account."
    if direction not in {"buy", "sell"}:
        return None, "The direction must be buy or sell."
    if position_open:
        return None, "This symbol already has an open position."
    if trades_today >= max_trades_per_day:
        return None, "The Ghana day already has two sent trades."
    if expires_at is not None and expires_at <= now:
        return None, "This signal has expired. Scan the market again."
    if spec is None or not spec.valid():
        return None, "The terminal did not provide a usable tick value or lot step."
    if not all(math.isfinite(value) for value in (price, stop, scanned_entry, scanned_distance, equity, risk_fraction, reward_multiple)):
        return None, "The quote or the signal prices are not usable."
    if risk_fraction <= 0 or reward_multiple <= 0:
        return None, "Saved risk or reward settings are not usable."
    stop = round_price(stop, spec.digits)
    price = round_price(price, spec.digits)
    if direction == "buy" and not price > stop:
        return None, "The ask is not above the stop, so this buy cannot be sent."
    if direction == "sell" and not price < stop:
        return None, "The bid is not below the stop, so this sell cannot be sent."
    distance = round_price(abs(price - stop), spec.digits)
    if MIN_STOP_DISTANCE > 0 and distance < MIN_STOP_DISTANCE:
        return None, "The stop is closer than 0.50 at the live price."
    drift_limit = max(scanned_distance * 0.5, MIN_STOP_DISTANCE)
    if abs(price - scanned_entry) > drift_limit:
        return None, "The live price has moved too far from the scanned entry. Scan again."
    sized = size_position(equity, distance, spec, require_lots=True, risk_fraction=risk_fraction)
    if sized.error or sized.lots is None or sized.cash_risk is None:
        if sized.error == "below_min_lot":
            return None, "Sizing at the saved risk is below the broker minimum lot."
        return None, "The lot size could not be calculated from the broker contract."
    if sized.cash_risk > equity * risk_fraction + 0.01:
        return None, "The calculated risk is above the saved risk fraction."
    target = round_price(
        price + reward_multiple * distance if direction == "buy" else price - reward_multiple * distance,
        spec.digits,
    )
    return OrderPlan(sized.lots, price, stop, target, round(sized.cash_risk, 2), sized.capped), None
