"""Liquidity sweep + reclaim/reject detection.

Long: price dips below a key level (premarket low, prior day low, opening-range
low) then the current candle closes back above it — a swept-then-reclaimed low.
Short is the mirror: a swept-then-rejected high.
"""

from __future__ import annotations

from typing import List, Optional

from trading.signals.models import Candle, Direction, LiquiditySweep


def detect_sweep(candles: List[Candle], level: float, direction: Direction, lookback: int = 5) -> Optional[LiquiditySweep]:
    if len(candles) < 2:
        return None
    window, current = candles[-lookback:-1], candles[-1]
    if direction == Direction.LONG:
        swept = any(c.low < level for c in window)
        reclaimed = current.close > level
        if swept and reclaimed:
            return LiquiditySweep(direction=Direction.LONG, swept_level=level, reclaim_price=current.close)
        return None
    swept = any(c.high > level for c in window)
    rejected = current.close < level
    if swept and rejected:
        return LiquiditySweep(direction=Direction.SHORT, swept_level=level, reclaim_price=current.close)
    return None
