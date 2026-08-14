"""Chronological train/validate/test splitting. Never shuffle time-series
data — a split that leaks future days into the training set makes a
backtest lie about how the strategy would have performed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List


@dataclass(frozen=True)
class PeriodSplit:
    train: List[date]
    validate: List[date]
    test: List[date]


def generate_weekdays(start: date, end: date) -> List[date]:
    """Mon-Fri only. Does not exclude market holidays — filter those out
    yourself if you have a real trading calendar; otherwise a handful of
    holiday "trading days" with no real data will just come back empty from
    the data source and contribute no trades."""
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def split_trading_days(trading_days: List[date], train_pct: float = 0.6, validate_pct: float = 0.2) -> PeriodSplit:
    if not (0 < train_pct < 1) or not (0 <= validate_pct < 1) or train_pct + validate_pct >= 1:
        raise ValueError("train_pct + validate_pct must be positive fractions summing to less than 1")
    n = len(trading_days)
    train_end = int(n * train_pct)
    validate_end = train_end + int(n * validate_pct)
    return PeriodSplit(
        train=trading_days[:train_end],
        validate=trading_days[train_end:validate_end],
        test=trading_days[validate_end:],
    )
