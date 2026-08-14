"""Target selection and risk/reward computation.

A target is only meaningful if it's an actual level (prior high/low, premarket
high/low, equal high/low zone) — not an arbitrary multiple of risk.
"""

from __future__ import annotations

from typing import List, Optional

from trading.signals.models import Direction
from trading.risk.stops import stop_distance


def nearest_target_above(entry: float, levels: List[float], min_distance: float) -> Optional[float]:
    candidates = [level for level in levels if level > entry + min_distance]
    return min(candidates) if candidates else None


def nearest_target_below(entry: float, levels: List[float], min_distance: float) -> Optional[float]:
    candidates = [level for level in levels if level < entry - min_distance]
    return max(candidates) if candidates else None


def compute_r_multiple(direction: Direction, entry: float, stop: float, target: float) -> float:
    risk = stop_distance(direction, entry, stop)
    if risk <= 0:
        return 0.0
    reward = (target - entry) if direction == Direction.LONG else (entry - target)
    return reward / risk


def passes_min_risk_reward(direction: Direction, entry: float, stop: float, target: float, min_risk_reward: float) -> bool:
    return compute_r_multiple(direction, entry, stop, target) >= min_risk_reward
