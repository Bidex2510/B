"""Fair value gap detection — ported from indicators/sniper_open_complete_signal.pine.

A bullish FVG: the high two candles back is below the current candle's low
(a 3-candle gap the middle candle didn't fill). Bearish is the mirror.
"""

from __future__ import annotations

from typing import List, Optional

from trading.signals.models import Candle, Direction, FvgZone


def detect_fvg(candles: List[Candle]) -> Optional[FvgZone]:
    """candles must be ordered oldest-to-newest; only the last 3 are used."""
    if len(candles) < 3:
        return None
    candle1, current = candles[-3], candles[-1]
    if candle1.high < current.low:
        return FvgZone(direction=Direction.LONG, gap_low=candle1.high, gap_high=current.low)
    if candle1.low > current.high:
        return FvgZone(direction=Direction.SHORT, gap_low=current.high, gap_high=candle1.low)
    return None
