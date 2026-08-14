"""Runs a strategy config through chronological train/validate/test splits
and reports stats for each, so a result can be checked for whether it
generalizes or was curve-fit to the training period.

This is comparison support, not a verdict: a strategy that looks strong in
train and falls apart in validate/test hasn't been "unlucky" - it wasn't
robust. Don't proceed to paper trading on train-period results alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from trading.backtest.data_source import HistoricalDataSource
from trading.backtest.models import BacktestConfig
from trading.backtest.period_split import split_trading_days
from trading.backtest.portfolio import run_backtest_many
from trading.backtest.stats import PerformanceStats, compute_stats


@dataclass(frozen=True)
class ValidationReport:
    train: PerformanceStats
    validate: PerformanceStats
    test: PerformanceStats


def run_out_of_sample_validation(
    symbols: List[str],
    trading_days: List[date],
    data_source: HistoricalDataSource,
    config: BacktestConfig,
    train_pct: float = 0.6,
    validate_pct: float = 0.2,
) -> ValidationReport:
    split = split_trading_days(trading_days, train_pct=train_pct, validate_pct=validate_pct)

    train_trades = run_backtest_many(symbols, split.train, data_source, config).trades
    validate_trades = run_backtest_many(symbols, split.validate, data_source, config).trades
    test_trades = run_backtest_many(symbols, split.test, data_source, config).trades

    return ValidationReport(
        train=compute_stats(train_trades),
        validate=compute_stats(validate_trades),
        test=compute_stats(test_trades),
    )
