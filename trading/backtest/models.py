"""Data structures for a backtest run."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from trading.risk.models import RiskConfig
from trading.risk.stops import stop_distance
from trading.signals.models import Direction


@dataclass(frozen=True)
class DayLevels:
    """The liquidity map a single symbol/day is evaluated against.

    long_sweep_level/short_sweep_level: the key level a sweep-and-reclaim must
    occur against (e.g. premarket low for longs, premarket high for shorts).
    target_levels: candidate levels (premarket high/low, prior-day high/low,
    equal highs/lows) a profit target is selected from.
    """

    long_sweep_level: Optional[float] = None
    short_sweep_level: Optional[float] = None
    target_levels: List[float] = field(default_factory=list)


@dataclass(frozen=True)
class BacktestConfig:
    risk_config: RiskConfig
    starting_equity: float = 10_000.0
    opening_range_minutes: int = 5
    atr_period: int = 14
    min_target_distance: float = 0.10


@dataclass
class Trade:
    symbol: str
    direction: Direction
    entry_time: datetime
    entry_price: float
    stop_price: float
    target_price: float
    shares: int
    exit_time: datetime
    exit_price: float
    exit_reason: str  # "stop" | "target" | "end_of_day"

    @property
    def pnl(self) -> float:
        move = (self.exit_price - self.entry_price) if self.direction == Direction.LONG else (self.entry_price - self.exit_price)
        return move * self.shares

    @property
    def r_multiple(self) -> float:
        risk_per_share = stop_distance(self.direction, self.entry_price, self.stop_price)
        if risk_per_share <= 0:
            return 0.0
        move = (self.exit_price - self.entry_price) if self.direction == Direction.LONG else (self.entry_price - self.exit_price)
        return move / risk_per_share
