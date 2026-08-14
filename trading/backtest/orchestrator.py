"""Runs the single-day backtester across a chronological range of trading
days, compounding account equity from each day's result into the next.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import List

from trading.backtest.data_source import HistoricalDataSource
from trading.backtest.levels_builder import build_day_levels
from trading.backtest.models import BacktestConfig, Trade
from trading.backtest.simulator import run_day
from trading.risk.governor import RiskGovernor


@dataclass
class DayResult:
    day: date
    trades: List[Trade]
    starting_equity: float
    ending_equity: float


@dataclass
class BacktestResult:
    symbol: str
    starting_equity: float
    day_results: List[DayResult]

    @property
    def trades(self) -> List[Trade]:
        return [trade for day in self.day_results for trade in day.trades]

    @property
    def final_equity(self) -> float:
        return self.day_results[-1].ending_equity if self.day_results else self.starting_equity


def run_backtest(symbol: str, trading_days: List[date], data_source: HistoricalDataSource, config: BacktestConfig) -> BacktestResult:
    """trading_days must be chronologically ordered. The risk governor resets
    each day (a new session's daily loss limit/trade cap/cooldown start
    fresh) but account equity carries forward, compounding position sizing
    day to day. The first day has no prior-day level to target from — only
    premarket levels are available for it.
    """
    equity = config.starting_equity
    day_results: List[DayResult] = []
    prior_day_candles: List = []

    for day in trading_days:
        premarket_candles = data_source.get_premarket_candles(symbol, day)
        session_candles = data_source.get_session_candles(symbol, day)

        levels = build_day_levels(premarket_candles, prior_day_candles)
        day_config = replace(config, starting_equity=equity)
        governor = RiskGovernor(day_config.risk_config, account_equity=equity)

        trades = run_day(symbol, session_candles, day_config, levels, governor) if session_candles else []
        day_pnl = sum(trade.pnl for trade in trades)

        day_results.append(DayResult(day=day, trades=trades, starting_equity=equity, ending_equity=equity + day_pnl))
        equity += day_pnl
        prior_day_candles = session_candles

    return BacktestResult(symbol=symbol, starting_equity=config.starting_equity, day_results=day_results)
