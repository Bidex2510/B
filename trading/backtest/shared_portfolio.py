"""Multi-day version of the shared-capital portfolio simulation: runs
run_portfolio_day across a chronological range of trading days for a fixed
symbol list, with ONE equity curve compounding day to day and a fresh
RiskGovernor each session (daily loss limit/trade cap/cooldown are per-day,
shared across all symbols that day - not per-symbol, and not cumulative
across days).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Dict, List

from trading.backtest.data_source import HistoricalDataSource
from trading.backtest.levels_builder import build_day_levels
from trading.backtest.models import BacktestConfig, Trade
from trading.backtest.portfolio_simulator import run_portfolio_day
from trading.risk.governor import RiskGovernor
from trading.signals.models import Candle


@dataclass
class SharedDayResult:
    day: date
    trades: List[Trade]
    starting_equity: float
    ending_equity: float


@dataclass
class SharedPortfolioResult:
    symbols: List[str]
    starting_equity: float
    day_results: List[SharedDayResult]

    @property
    def trades(self) -> List[Trade]:
        return [trade for day in self.day_results for trade in day.trades]

    @property
    def final_equity(self) -> float:
        return self.day_results[-1].ending_equity if self.day_results else self.starting_equity


def run_shared_portfolio_backtest(
    symbols: List[str], trading_days: List[date], data_source: HistoricalDataSource, config: BacktestConfig
) -> SharedPortfolioResult:
    """A day is skipped entirely if no symbol has session candles for it.
    Symbols that individually have no candles on an otherwise-active day are
    dropped from that day's run (run_portfolio_day requires aligned candle
    counts across whatever symbols it's given)."""
    equity = config.starting_equity
    day_results: List[SharedDayResult] = []
    prior_day_candles: Dict[str, List[Candle]] = {symbol: [] for symbol in symbols}

    for day in trading_days:
        session_by_symbol: Dict[str, List[Candle]] = {}
        levels_by_symbol = {}
        for symbol in symbols:
            premarket = data_source.get_premarket_candles(symbol, day)
            session = data_source.get_session_candles(symbol, day)
            session_by_symbol[symbol] = session
            levels_by_symbol[symbol] = build_day_levels(premarket, prior_day_candles[symbol])

        bar_count = max((len(candles) for candles in session_by_symbol.values()), default=0)
        active = {s: c for s, c in session_by_symbol.items() if len(c) == bar_count and bar_count > 0}

        day_config = replace(config, starting_equity=equity)
        governor = RiskGovernor(day_config.risk_config, account_equity=equity)

        trades = run_portfolio_day(active, day_config, levels_by_symbol, governor) if active else []
        day_pnl = sum(trade.pnl for trade in trades)

        day_results.append(SharedDayResult(day=day, trades=trades, starting_equity=equity, ending_equity=equity + day_pnl))
        equity += day_pnl

        for symbol in symbols:
            prior_day_candles[symbol] = session_by_symbol[symbol]

    return SharedPortfolioResult(symbols=symbols, starting_equity=config.starting_equity, day_results=day_results)
