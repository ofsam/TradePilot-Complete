from dataclasses import dataclass

H1_SECONDS = 60 * 60
H4_SECONDS = 4 * 60 * 60


@dataclass(frozen=True)
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open


def closed_candles(candles: list[Candle], period_seconds: int, now: float | None) -> list[Candle]:
    """Drop the forming bar when `now` is known. Historical fixtures pass now=None."""
    if now is None:
        return list(candles)
    return [candle for candle in candles if candle.time + period_seconds <= now]


def visible_h4(candles: list[Candle], as_of: float) -> list[Candle]:
    return [candle for candle in candles if candle.time + H4_SECONDS <= as_of]
