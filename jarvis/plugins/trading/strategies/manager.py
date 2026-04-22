"""StrategyManager - orchestrates all active strategies.

On startup, reads STRATEGY_* env flags and activates matching strategies.
By default all six are on (swing, position, trend, breakout, day, scalp).

For each scan the manager:
  1. Fetches OHLCV at the bar-interval each strategy needs (cached per cycle)
  2. Asks every strategy to score the symbol
  3. Returns the highest-scoring BUY signal that clears its threshold
  4. Routes exit checks to the strategy that opened the position
"""

import logging
import os
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from jarvis.plugins.trading.strategies.base import Action, Strategy, StrategySignal
from jarvis.plugins.trading.strategies.breakout import BreakoutStrategy
from jarvis.plugins.trading.strategies.day import DayStrategy
from jarvis.plugins.trading.strategies.position import PositionStrategy
from jarvis.plugins.trading.strategies.scalp import ScalpStrategy
from jarvis.plugins.trading.strategies.swing import SwingStrategy
from jarvis.plugins.trading.strategies.trend import TrendStrategy

logger = logging.getLogger(__name__)


_ALL_STRATEGIES: list[type[Strategy]] = [
    SwingStrategy,
    PositionStrategy,
    TrendStrategy,
    BreakoutStrategy,
    DayStrategy,
    ScalpStrategy,
]


def _flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(f"STRATEGY_{name.upper()}", "true" if default else "false").lower()
    return raw in ("1", "true", "yes", "on")


@dataclass
class _BarKey:
    interval: str
    period: str

    def __hash__(self):
        return hash((self.interval, self.period))


class StrategyManager:
    def __init__(self):
        self.strategies: list[Strategy] = []
        for cls in _ALL_STRATEGIES:
            if _flag(cls.name, default=True):
                self.strategies.append(cls())
                logger.info(f"Strategy enabled: {cls.name}")
            else:
                logger.info(f"Strategy disabled: {cls.name}")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def active_names(self) -> list[str]:
        return [s.name for s in self.strategies]

    @property
    def has_intraday(self) -> bool:
        return any(s.intraday for s in self.strategies)

    def get(self, name: str) -> Strategy | None:
        for s in self.strategies:
            if s.name == name:
                return s
        return None

    # ------------------------------------------------------------------
    # Entry evaluation
    # ------------------------------------------------------------------

    def evaluate_entry(
        self,
        symbol: str,
        sentiment: float,
        fundamental_score: float,
    ) -> StrategySignal | None:
        """Run every active strategy on the symbol. Return the strongest BUY."""
        bar_cache: dict[_BarKey, pd.DataFrame] = {}
        best: StrategySignal | None = None

        for strat in self.strategies:
            key = _BarKey(strat.bar_interval, strat.bar_period)
            df = bar_cache.get(key)
            if df is None:
                df = self._fetch_bars(symbol, strat.bar_interval, strat.bar_period)
                if df is not None:
                    bar_cache[key] = df
            if df is None or df.empty:
                continue

            try:
                score = strat.score(symbol, df, sentiment, fundamental_score)
            except Exception as exc:
                logger.warning(f"{strat.name} scoring failed for {symbol}: {exc}")
                continue

            logger.debug(f"{symbol} | {strat.name}: {score:.2f}")
            if score >= strat.min_score_to_buy:
                signal = StrategySignal(
                    symbol=symbol,
                    action=Action.BUY,
                    score=score,
                    strategy_name=strat.name,
                    reason=f"{strat.name} score {score:.0%}",
                    target_hold_days=strat.target_hold_days,
                )
                if best is None or score > best.score:
                    best = signal

        return best

    # ------------------------------------------------------------------
    # Exit evaluation
    # ------------------------------------------------------------------

    def check_exit(
        self,
        symbol: str,
        strategy_name: str,
        entry_price: float,
        age_minutes: float,
    ) -> tuple[bool, str]:
        strat = self.get(strategy_name)
        if strat is None:
            return False, ""

        df = self._fetch_bars(symbol, strat.bar_interval, strat.bar_period)
        if df is None or df.empty:
            return False, ""

        try:
            return strat.should_exit(symbol, df, entry_price, age_minutes)
        except Exception as exc:
            logger.warning(f"{strategy_name} exit check failed for {symbol}: {exc}")
            return False, ""

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_bars(symbol: str, interval: str, period: str) -> pd.DataFrame | None:
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
            return df if not df.empty else None
        except Exception as exc:
            logger.debug(f"Bar fetch failed for {symbol} [{interval}/{period}]: {exc}")
            return None
