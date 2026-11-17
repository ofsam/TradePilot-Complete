"""Built-in price path for the H4-bias / H1 level-retest engine. It is not market history."""

from datetime import datetime, timedelta, timezone

from app.strategy.candles import Candle, H1_SECONDS
from app.strategy.engine import run_backtest
from app.strategy.risk import SymbolSpec

BASE = datetime(2024, 1, 2, tzinfo=timezone.utc)
SAMPLE_SPEC = SymbolSpec(
    point=0.01,
    trade_tick_size=0.01,
    trade_tick_value=1,
    volume_min=0.01,
    volume_max=50,
    volume_step=0.01,
    digits=2,
)


def _hour(hour: int, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(int((BASE + timedelta(hours=hour)).timestamp()), open_, high, low, close)


def sample_candles() -> tuple[list[Candle], list[Candle]]:
    # January 2 is UTC+0 in London, so hours 8–16 are inside the London session.
    # The first buy closes above the prior hour high while the H4 is still forming.
    # The second buy loses. A third touch the same Ghana day is skipped.
    higher = [
        _hour(0, 100, 108, 99, 104),
        _hour(4, 104, 110, 103, 108),
        _hour(8, 108, 112.8, 109.2, 112.6),
        _hour(12, 112.6, 113.4, 112.0, 113.0),
        _hour(16, 113.0, 114.0, 112.6, 113.5),
    ]
    lower = [
        _hour(8, 109.4, 110.3, 109.2, 110.0),
        _hour(9, 110.0, 110.8, 109.6, 110.5),
        _hour(10, 110.6, 110.9, 110.1, 110.7),
        _hour(11, 110.7, 112.8, 110.5, 112.6),
        _hour(12, 112.6, 112.9, 112.2, 112.7),
        _hour(13, 112.7, 113.4, 112.5, 113.2),
        _hour(14, 113.0, 113.2, 112.7, 112.9),
        _hour(15, 112.8, 113.1, 112.2, 112.4),
        _hour(16, 112.6, 114.0, 112.8, 113.6),
        _hour(17, 113.5, 113.6, 112.9, 113.0),
    ]
    return higher, lower


def run_sample(starting_equity: float = 10_000):
    higher, lower = sample_candles()
    if len(lower) < 3:
        raise RuntimeError("sample candles are incomplete")
    report = run_backtest(
        higher,
        lower,
        symbol="XAUUSD",
        spec=SAMPLE_SPEC,
        spread=0,
        spread_source="sample",
        starting_equity=starting_equity,
        source="sample",
        now=lower[-1].time + H1_SECONDS,
    )
    payload = report.as_dict()
    payload["order_submitted"] = False
    payload["auto_execution"] = False
    return payload
