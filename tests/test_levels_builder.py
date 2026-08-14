from datetime import datetime

from trading.backtest.levels_builder import build_day_levels
from trading.signals.models import Candle


def candle(o, h, l, c, hour, minute):
    return Candle(time=datetime(2026, 8, 14, hour, minute), open=o, high=h, low=l, close=c, volume=1000)


def test_sweep_levels_come_from_premarket_high_low():
    premarket = [candle(4.70, 4.75, 4.60, 4.72, 8, 0)]
    levels = build_day_levels(premarket, prior_day_candles=[])
    assert levels.long_sweep_level == 4.60
    assert levels.short_sweep_level == 4.75


def test_target_levels_pool_premarket_and_prior_day():
    premarket = [candle(4.70, 4.75, 4.60, 4.72, 8, 0)]
    prior_day = [candle(5.00, 5.50, 4.90, 5.20, 9, 30)]
    levels = build_day_levels(premarket, prior_day)
    assert levels.target_levels == [4.60, 4.75, 4.90, 5.50]


def test_no_premarket_data_leaves_sweep_levels_none():
    levels = build_day_levels([], prior_day_candles=[])
    assert levels.long_sweep_level is None
    assert levels.short_sweep_level is None
    assert levels.target_levels == []
