"""Data structures shared across the scanner pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Fundamentals:
    """Reference data Alpaca's market/trading APIs do not provide.

    Must come from a separate fundamentals source (see trading/data/fundamentals.py).
    """

    market_cap: Optional[float]
    float_shares: Optional[int]


@dataclass
class StockSnapshot:
    symbol: str
    exchange: str
    price: float
    previous_close: float
    premarket_volume: int
    avg_daily_volume: float
    fundamentals: Fundamentals

    @property
    def gap_pct(self) -> float:
        if self.previous_close <= 0:
            return 0.0
        return (self.price - self.previous_close) / self.previous_close * 100

    @property
    def relative_volume(self) -> float:
        # Simplified RVOL: premarket volume vs. the stock's average *full-day*
        # volume, not a same-time-of-day comparison. Flags unusually heavy
        # premarket interest even though it slightly understates true RVOL.
        if self.avg_daily_volume <= 0:
            return 0.0
        return self.premarket_volume / self.avg_daily_volume


@dataclass
class WatchlistEntry:
    snapshot: StockSnapshot
    status: str = "WATCH"

    @property
    def symbol(self) -> str:
        return self.snapshot.symbol
