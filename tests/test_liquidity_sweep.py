from datetime import datetime

from trading.signals.liquidity_sweep import detect_sweep
from trading.signals.models import Candle, Direction


def candle(o, h, l, c, minute):
    return Candle(time=datetime(2026, 8, 14, 9, 30 + minute), open=o, high=h, low=l, close=c, volume=1000)


def test_long_sweep_detected_when_swept_and_reclaimed():
    candles = [
        candle(5.0, 5.1, 4.95, 5.0, 0),
        candle(5.0, 5.05, 4.80, 4.85, 1),  # sweeps below 4.90 level
        candle(4.85, 5.05, 4.85, 5.0, 2),  # reclaims above 4.90
    ]
    sweep = detect_sweep(candles, level=4.90, direction=Direction.LONG)
    assert sweep is not None
    assert sweep.swept_level == 4.90


def test_long_sweep_none_without_reclaim():
    candles = [
        candle(5.0, 5.1, 4.95, 5.0, 0),
        candle(5.0, 5.05, 4.80, 4.85, 1),  # sweeps below
        candle(4.85, 4.88, 4.80, 4.85, 2),  # never reclaims above 4.90
    ]
    assert detect_sweep(candles, level=4.90, direction=Direction.LONG) is None


def test_long_sweep_none_without_prior_sweep():
    candles = [
        candle(5.0, 5.1, 4.95, 5.0, 0),
        candle(5.0, 5.1, 4.95, 5.0, 1),
        candle(5.0, 5.1, 4.95, 5.05, 2),
    ]
    assert detect_sweep(candles, level=4.90, direction=Direction.LONG) is None


def test_short_sweep_detected_when_swept_and_rejected():
    candles = [
        candle(5.0, 5.05, 4.95, 5.0, 0),
        candle(5.0, 5.20, 4.95, 5.15, 1),  # sweeps above 5.10 level
        candle(5.15, 5.18, 5.00, 5.05, 2),  # rejects back below 5.10
    ]
    sweep = detect_sweep(candles, level=5.10, direction=Direction.SHORT)
    assert sweep is not None
    assert sweep.swept_level == 5.10
