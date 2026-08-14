"""Premarket/prior-day levels and the opening range — the liquidity map for the day."""

from __future__ import annotations

from datetime import time as dt_time
from typing import List, Optional

from trading.signals.models import Candle, OpeningRange

MARKET_OPEN = dt_time(9, 30)


def premarket_high_low(premarket_candles: List[Candle]) -> Optional[tuple]:
    if not premarket_candles:
        return None
    return max(c.high for c in premarket_candles), min(c.low for c in premarket_candles)


def previous_day_high_low(previous_day_candles: List[Candle]) -> Optional[tuple]:
    if not previous_day_candles:
        return None
    return max(c.high for c in previous_day_candles), min(c.low for c in previous_day_candles)


def opening_range(session_candles: List[Candle], window_minutes: int = 5) -> Optional[OpeningRange]:
    """session_candles must start at market open (9:30 ET) and be 1-minute bars."""
    window = [c for c in session_candles if c.time.time() < _add_minutes(MARKET_OPEN, window_minutes)]
    if not window:
        return None
    return OpeningRange(high=max(c.high for c in window), low=min(c.low for c in window))


def _add_minutes(t: dt_time, minutes: int) -> dt_time:
    total = t.hour * 60 + t.minute + minutes
    return dt_time(hour=(total // 60) % 24, minute=total % 60)
