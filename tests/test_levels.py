from datetime import datetime

from trading.signals.levels import opening_range, premarket_high_low, previous_day_high_low
from trading.signals.models import Candle


def candle(o, h, l, c, hour, minute):
    return Candle(time=datetime(2026, 8, 14, hour, minute), open=o, high=h, low=l, close=c, volume=1000)


def test_premarket_high_low():
    candles = [
        candle(4.0, 4.5, 3.9, 4.2, 8, 0),
        candle(4.2, 4.8, 4.1, 4.6, 9, 0),
    ]
    result = premarket_high_low(candles)
    assert result == (4.8, 3.9)


def test_premarket_high_low_empty():
    assert premarket_high_low([]) is None


def test_previous_day_high_low():
    candles = [
        candle(5.0, 5.5, 4.8, 5.2, 9, 30),
        candle(5.2, 5.6, 5.0, 5.4, 15, 0),
    ]
    assert previous_day_high_low(candles) == (5.6, 4.8)


def test_opening_range_uses_only_window_minutes():
    candles = [
        candle(5.0, 5.2, 4.9, 5.1, 9, 30),
        candle(5.1, 5.4, 5.0, 5.3, 9, 33),
        candle(5.3, 5.5, 5.2, 5.4, 9, 40),  # outside 5-minute window
    ]
    result = opening_range(candles, window_minutes=5)
    assert result.high == 5.4
    assert result.low == 4.9


def test_opening_range_empty_returns_none():
    assert opening_range([], window_minutes=5) is None
