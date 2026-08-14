from datetime import datetime

from trading.signals.atr import latest_atr, true_range
from trading.signals.models import Candle


def candle(o, h, l, c, minute):
    return Candle(time=datetime(2026, 8, 14, 9, 30 + minute), open=o, high=h, low=l, close=c, volume=1000)


def test_true_range_picks_largest_component():
    assert round(true_range(previous_close=5.0, high=5.3, low=5.1), 6) == 0.3  # high-low
    assert round(true_range(previous_close=5.0, high=5.5, low=5.4), 6) == 0.5  # high-prev_close
    assert round(true_range(previous_close=5.0, high=4.9, low=4.6), 6) == 0.4  # prev_close-low


def test_latest_atr_averages_true_ranges():
    candles = [
        candle(5.0, 5.1, 4.9, 5.0, 0),  # TR n/a (no prior close)
        candle(5.0, 5.2, 4.9, 5.1, 1),  # TR = max(0.3, 0.2, 0.1) = 0.3
        candle(5.1, 5.4, 5.0, 5.3, 2),  # TR = max(0.4, 0.3, 0.1) = 0.4
    ]
    assert round(latest_atr(candles, period=14), 6) == round((0.3 + 0.4) / 2, 6)


def test_latest_atr_with_insufficient_candles():
    assert latest_atr([candle(5.0, 5.1, 4.9, 5.0, 0)], period=14) == 0.0


def test_latest_atr_empty():
    assert latest_atr([], period=14) == 0.0
