"""Base Strategy class and shared signal type.

Every strategy returns a score in [0, 1]. The bot buys when any strategy's
score exceeds its min_score_to_buy threshold. Each strategy owns its own
exit rules so a swing-trade position exits differently from a scalp trade.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import pandas as pd


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategySignal:
    symbol: str
    action: Action
    score: float              # 0.0 – 1.0 confidence
    strategy_name: str
    reason: str
    target_hold_days: float   # approximate intended holding period


# ---------------------------------------------------------------------------
# Strategy timeframe codes (yfinance interval strings)
# ---------------------------------------------------------------------------
TF_1M = "1m"
TF_5M = "5m"
TF_15M = "15m"
TF_1H = "1h"
TF_1D = "1d"


class Strategy(ABC):
    """Abstract base for trading strategies."""

    name: str = "base"
    bar_interval: str = TF_1D       # yfinance interval for this strategy
    bar_period: str = "1y"          # yfinance period (how far back to pull)
    target_hold_days: float = 30.0
    min_score_to_buy: float = 0.70
    intraday: bool = False          # True for day/scalp (must exit before close)

    @abstractmethod
    def score(
        self,
        symbol: str,
        df: pd.DataFrame,
        sentiment: float,
        fundamental_score: float,
    ) -> float:
        """Return a 0.0–1.0 buy-confidence score for the symbol."""

    @abstractmethod
    def should_exit(
        self,
        symbol: str,
        df: pd.DataFrame,
        entry_price: float,
        age_minutes: float,
    ) -> tuple[bool, str]:
        """Return (exit_now, reason)."""
