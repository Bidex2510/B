"""Builds a day's DayLevels from real premarket/prior-day candles, instead of
hand-picked test fixtures."""

from __future__ import annotations

from typing import List

from trading.backtest.models import DayLevels
from trading.signals.levels import premarket_high_low, previous_day_high_low
from trading.signals.models import Candle


def build_day_levels(premarket_candles: List[Candle], prior_day_candles: List[Candle]) -> DayLevels:
    """long_sweep_level/short_sweep_level default to the premarket low/high —
    the most immediate liquidity a fresh session would sweep. target_levels
    pools premarket and prior-day high/low as candidate profit targets."""
    premarket = premarket_high_low(premarket_candles)
    prior_day = previous_day_high_low(prior_day_candles)

    long_sweep_level = premarket[1] if premarket else None
    short_sweep_level = premarket[0] if premarket else None

    target_levels = []
    if premarket:
        target_levels.extend(premarket)
    if prior_day:
        target_levels.extend(prior_day)

    return DayLevels(
        long_sweep_level=long_sweep_level,
        short_sweep_level=short_sweep_level,
        target_levels=sorted(set(target_levels)),
    )
