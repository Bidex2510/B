from datetime import datetime

from trading.signals.fvg import detect_fvg
from trading.signals.models import Candle, Direction


def candle(o, h, l, c, minute):
    return Candle(time=datetime(2026, 8, 14, 9, 30 + minute), open=o, high=h, low=l, close=c, volume=1000)


def test_bullish_fvg_detected():
    candles = [
        candle(5.0, 5.1, 4.9, 5.0, 0),
        candle(5.0, 5.2, 4.95, 5.15, 1),
        candle(5.3, 5.5, 5.2, 5.45, 2),  # low (5.2) > candle1 high (5.1)
    ]
    fvg = detect_fvg(candles)
    assert fvg is not None
    assert fvg.direction == Direction.LONG
    assert fvg.gap_low == 5.1
    assert fvg.gap_high == 5.2


def test_bearish_fvg_detected():
    candles = [
        candle(5.5, 5.6, 5.4, 5.45, 0),
        candle(5.4, 5.45, 5.2, 5.25, 1),
        candle(5.1, 5.15, 4.9, 4.95, 2),  # high (5.15) < candle1 low (5.4)
    ]
    fvg = detect_fvg(candles)
    assert fvg is not None
    assert fvg.direction == Direction.SHORT


def test_no_fvg_when_candles_overlap():
    candles = [
        candle(5.0, 5.1, 4.9, 5.0, 0),
        candle(5.0, 5.1, 4.9, 5.0, 1),
        candle(5.0, 5.1, 4.9, 5.0, 2),
    ]
    assert detect_fvg(candles) is None


def test_no_fvg_with_fewer_than_three_candles():
    candles = [candle(5.0, 5.1, 4.9, 5.0, 0)]
    assert detect_fvg(candles) is None
