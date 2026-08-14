from datetime import datetime

from trading.signals.engine import generate_signal
from trading.signals.models import Candle, Direction, OpeningRange


def candle(o, h, l, c, v, minute):
    return Candle(time=datetime(2026, 8, 14, 9, 30 + minute), open=o, high=h, low=l, close=c, volume=v)


def long_setup_candles():
    return [
        candle(4.90, 4.98, 4.95, 4.92, 1000, 0),
        candle(4.92, 4.95, 4.80, 4.85, 1000, 1),  # sweeps below 4.90
        candle(4.85, 5.00, 4.83, 4.95, 1000, 2),  # candle1 for FVG (high 5.00)
        candle(4.95, 5.10, 4.90, 5.05, 1000, 3),
        candle(5.10, 5.45, 5.05, 5.40, 2000, 4),  # current: low 5.05 > 5.00 -> FVG
    ]


def short_setup_candles():
    return [
        candle(5.10, 5.15, 5.05, 5.08, 1000, 0),
        candle(5.08, 5.35, 5.05, 5.30, 1000, 1),  # sweeps above 5.30
        candle(5.30, 5.32, 5.00, 5.05, 1000, 2),  # candle1 for FVG (low 5.00)
        candle(5.05, 5.10, 4.95, 5.00, 1000, 3),
        candle(4.95, 4.98, 4.60, 4.65, 2000, 4),  # current: high 4.98 < 5.00 -> FVG
    ]


def test_long_confluence_produces_signal():
    signal = generate_signal(
        long_setup_candles(),
        opening_range=OpeningRange(high=5.30, low=4.80),
        long_sweep_level=4.90,
    )
    assert signal is not None
    assert signal.direction == Direction.LONG
    assert signal.entry == 5.05


def test_short_confluence_produces_signal():
    signal = generate_signal(
        short_setup_candles(),
        opening_range=OpeningRange(high=5.40, low=4.90),
        short_sweep_level=5.30,
    )
    assert signal is not None
    assert signal.direction == Direction.SHORT
    assert signal.entry == 4.98


def test_no_signal_without_sweep_level():
    signal = generate_signal(
        long_setup_candles(),
        opening_range=OpeningRange(high=5.30, low=4.80),
    )
    assert signal is None


def test_no_signal_with_too_few_candles():
    signal = generate_signal(
        long_setup_candles()[-2:],
        opening_range=OpeningRange(high=5.30, low=4.80),
        long_sweep_level=4.90,
    )
    assert signal is None
