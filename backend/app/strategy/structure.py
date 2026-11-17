"""Closed-candle market structure for XAUUSD H4/H1.

These rules are measurable. They are a research model, not a claim of an 80% win rate.
"""

from datetime import datetime, timezone

from app.strategy.candles import Candle

EMA_PERIOD = 5
ATR_PERIOD = 6
MIN_H4_BARS = 8
ZONE_FRACTION = 0.5
MAX_SPREAD = 0.80
DAILY_LOSS_FRACTION = 0.04


def ema_series(values: list[float], period: int = EMA_PERIOD) -> list[float]:
    if not values or period < 1:
        return []
    weight = 2 / (period + 1)
    series = [values[0]]
    for value in values[1:]:
        series.append(value * weight + series[-1] * (1 - weight))
    return series


def true_ranges(candles: list[Candle]) -> list[float]:
    ranges: list[float] = []
    for index, candle in enumerate(candles):
        span = candle.high - candle.low
        if index == 0:
            ranges.append(span)
            continue
        previous_close = candles[index - 1].close
        ranges.append(max(span, abs(candle.high - previous_close), abs(candle.low - previous_close)))
    return ranges


def atr(candles: list[Candle], period: int = ATR_PERIOD) -> float | None:
    if len(candles) < period:
        return None
    window = true_ranges(candles)[-period:]
    return sum(window) / period


def swing_indexes(candles: list[Candle]) -> tuple[list[int], list[int]]:
    """A swing is confirmed only after the next candle exists, so the last bar is never a swing."""
    highs: list[int] = []
    lows: list[int] = []
    for index in range(1, len(candles) - 1):
        candle = candles[index]
        if candle.high > candles[index - 1].high and candle.high > candles[index + 1].high:
            highs.append(index)
        if candle.low < candles[index - 1].low and candle.low < candles[index + 1].low:
            lows.append(index)
    return highs, lows


def market_bias(candles: list[Candle]) -> tuple[str, dict[str, bool]]:
    enough = len(candles) >= MIN_H4_BARS
    checks = {"enough_h4": enough, "h4_structure": False, "h4_ema": False}
    if not enough:
        return "neutral", checks
    highs, lows = swing_indexes(candles)
    bullish = bearish = False
    if len(highs) >= 2 and len(lows) >= 2:
        higher_highs = candles[highs[-1]].high > candles[highs[-2]].high
        higher_lows = candles[lows[-1]].low > candles[lows[-2]].low
        lower_highs = candles[highs[-1]].high < candles[highs[-2]].high
        lower_lows = candles[lows[-1]].low < candles[lows[-2]].low
        bullish = higher_highs and higher_lows
        bearish = lower_highs and lower_lows
    checks["h4_structure"] = bullish or bearish
    series = ema_series([candle.close for candle in candles])
    ema_up = candles[-1].close > series[-1] and series[-1] > series[-3]
    ema_down = candles[-1].close < series[-1] and series[-1] < series[-3]
    aligned = (bullish and ema_up) or (bearish and ema_down)
    checks["h4_ema"] = aligned
    if bullish and ema_up:
        return "long", checks
    if bearish and ema_down:
        return "short", checks
    return "neutral", checks


def find_order_block(candles: list[Candle], direction: str) -> Candle | None:
    """Last opposing candle before the bias candle.

    The list ends with the closed H1 candle that broke the H4 level. The search
    walks the seven candles before that one. A buy uses the latest bearish
    candle. A sell uses the latest bullish candle. If none appears, the candle
    immediately before the break is the block.
    """
    if len(candles) < 3 or direction not in {"buy", "sell"}:
        return None
    for offset in range(2, 9):
        if offset >= len(candles):
            break
        candle = candles[-offset]
        if direction == "buy" and candle.close < candle.open:
            return candle
        if direction == "sell" and candle.close > candle.open:
            return candle
    return candles[-2]


def in_london_or_new_york(timestamp: int) -> bool:
    """London 07:00–16:00 UTC or New York 12:00–21:00 UTC. The union is 07:00–21:00 UTC."""
    hour = datetime.fromtimestamp(timestamp, timezone.utc).hour
    return 7 <= hour < 21


def confirmed_pullback(candles: list[Candle], previous: Candle, signal: Candle, bias: str) -> tuple[dict[str, bool], float | None]:
    checks = {"zone_touch": False, "confirmation_candle": False, "session": in_london_or_new_york(signal.time)}
    if bias not in {"long", "short"}:
        return checks, None
    highs, lows = swing_indexes(candles)
    volatility = atr(candles)
    if volatility is None or volatility <= 0:
        return checks, None
    if bias == "long" and lows:
        zone_low = candles[lows[-1]].low
        zone_high = zone_low + ZONE_FRACTION * volatility
        checks["zone_touch"] = signal.low <= zone_high and signal.low >= zone_low - 0.25 * volatility
        checks["confirmation_candle"] = signal.bullish and signal.close > zone_high and signal.close > previous.high
        if checks["zone_touch"] and checks["confirmation_candle"]:
            return checks, min(signal.low, zone_low)
    if bias == "short" and highs:
        zone_high = candles[highs[-1]].high
        zone_low = zone_high - ZONE_FRACTION * volatility
        checks["zone_touch"] = signal.high >= zone_low and signal.high <= zone_high + 0.25 * volatility
        checks["confirmation_candle"] = signal.bearish and signal.close < zone_low and signal.close < previous.low
        if checks["zone_touch"] and checks["confirmation_candle"]:
            return checks, max(signal.high, zone_high)
    return checks, None
