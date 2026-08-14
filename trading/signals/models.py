"""Data structures shared across the signal engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass(frozen=True)
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class FvgZone:
    direction: Direction
    gap_low: float
    gap_high: float

    @property
    def size(self) -> float:
        return self.gap_high - self.gap_low


@dataclass(frozen=True)
class LiquiditySweep:
    direction: Direction
    swept_level: float
    reclaim_price: float


@dataclass(frozen=True)
class OpeningRange:
    high: float
    low: float


@dataclass(frozen=True)
class TradeSignal:
    direction: Direction
    entry: float
    reasons: tuple
