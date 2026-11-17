import math
from dataclasses import dataclass

# Fixed by the control-center safety rules. The API does not accept overrides.
RISK_FRACTION = 0.02
REWARD_MULTIPLE = 2.0
MAX_TRADES_PER_DAY = 2


@dataclass(frozen=True)
class SymbolSpec:
    point: float
    trade_tick_size: float
    trade_tick_value: float
    volume_min: float
    volume_max: float
    volume_step: float
    digits: int = 2

    def valid(self) -> bool:
        numbers = (
            self.point,
            self.trade_tick_size,
            self.trade_tick_value,
            self.volume_min,
            self.volume_max,
            self.volume_step,
        )
        return (
            all(math.isfinite(value) and value > 0 for value in numbers)
            and self.volume_min <= self.volume_max
            and self.digits >= 0
        )


@dataclass(frozen=True)
class SizeResult:
    lots: float | None
    cash_risk: float | None
    capped: bool
    error: str | None


def floor_to_step(value: float, step: float) -> float:
    if step <= 0 or not math.isfinite(value):
        raise ValueError("lot step and size must be finite and the step must be positive")
    steps = math.floor((value / step) + 1e-9)
    return round(steps * step, 8)


def size_position(
    equity: float,
    stop_distance: float,
    spec: SymbolSpec | None,
    *,
    require_lots: bool,
    risk_fraction: float = RISK_FRACTION,
) -> SizeResult:
    """Floor lots so estimated cash risk stays at or under the saved fraction. Never round up."""
    if spec is None:
        if require_lots:
            return SizeResult(None, None, False, "invalid_symbol_spec")
        return SizeResult(None, None, False, None)
    if not spec.valid() or not math.isfinite(equity) or equity <= 0 or stop_distance <= 0:
        return SizeResult(None, None, False, "invalid_symbol_spec")
    if not math.isfinite(risk_fraction) or risk_fraction <= 0:
        return SizeResult(None, None, False, "invalid_symbol_spec")
    loss_per_lot = (stop_distance / spec.trade_tick_size) * spec.trade_tick_value
    if not math.isfinite(loss_per_lot) or loss_per_lot <= 0:
        return SizeResult(None, None, False, "invalid_symbol_spec")
    raw_lots = (equity * risk_fraction) / loss_per_lot
    capped = raw_lots > spec.volume_max
    lots = spec.volume_max if capped else floor_to_step(raw_lots, spec.volume_step)
    if lots < spec.volume_min:
        return SizeResult(None, None, False, "below_min_lot")
    cash_risk = loss_per_lot * lots
    return SizeResult(lots, cash_risk, capped, None)


def round_price(value: float, digits: int) -> float:
    return round(value, digits)
