"""Average True Range — used to floor stops so they're never tighter than normal noise."""

from __future__ import annotations

from typing import List, Optional

from trading.signals.models import Candle


def true_range(previous_close: float, high: float, low: float) -> float:
    return max(high - low, abs(high - previous_close), abs(low - previous_close))


def latest_atr(candles: List[Candle], period: int = 14) -> float:
    """Simple (unsmoothed) average true range over the trailing `period` candles.

    Uses however many candles are available if fewer than `period` + 1 exist.
    Returns 0.0 if there's nothing to compute from.
    """
    if len(candles) < 2:
        return 0.0
    window = candles[-(period + 1):]
    true_ranges = [true_range(window[i - 1].close, window[i].high, window[i].low) for i in range(1, len(window))]
    return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0
