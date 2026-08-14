"""Structural stops with an ATR floor — never a bare fixed-dollar/percent stop.

The stop is placed beyond the structural invalidation point (the swept level,
a swing low/high) unless that's tighter than a minimum ATR-based distance, in
which case the ATR distance wins so the stop isn't sitting inside normal noise.
"""

from __future__ import annotations

from trading.signals.models import Direction


def resolve_stop(direction: Direction, entry: float, structural_stop_price: float, atr: float, atr_multiplier: float) -> float:
    atr_min_distance = atr * atr_multiplier
    if direction == Direction.LONG:
        structural_distance = entry - structural_stop_price
        final_distance = max(structural_distance, atr_min_distance)
        return entry - final_distance
    structural_distance = structural_stop_price - entry
    final_distance = max(structural_distance, atr_min_distance)
    return entry + final_distance


def stop_distance(direction: Direction, entry: float, stop_price: float) -> float:
    return (entry - stop_price) if direction == Direction.LONG else (stop_price - entry)
