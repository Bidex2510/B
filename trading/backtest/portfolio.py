"""Runs the backtester across a watchlist of symbols and aggregates results.

Each symbol gets its own independent equity curve and risk governor, as if
trading it with separately allocated capital. This does NOT model a single
account risking shared capital across concurrently-traded symbols - true
portfolio-level simulation (one risk governor and one equity curve shared
across symbols each day) needs bar-by-bar interleaving across symbols and
isn't built yet. See trading/backtest/README.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List

from trading.backtest.data_source import HistoricalDataSource
from trading.backtest.models import BacktestConfig, Trade
from trading.backtest.orchestrator import BacktestResult, run_backtest


@dataclass
class PortfolioBacktestResult:
    results_by_symbol: Dict[str, BacktestResult]

    @property
    def trades(self) -> List[Trade]:
        return [trade for result in self.results_by_symbol.values() for trade in result.trades]

    @property
    def total_pnl(self) -> float:
        return sum(trade.pnl for trade in self.trades)


def run_backtest_many(
    symbols: List[str], trading_days: List[date], data_source: HistoricalDataSource, config: BacktestConfig
) -> PortfolioBacktestResult:
    results = {symbol: run_backtest(symbol, trading_days, data_source, config) for symbol in symbols}
    return PortfolioBacktestResult(results_by_symbol=results)
