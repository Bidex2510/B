"""Risk manager - enforces position limits, stop-losses, and circuit breakers.

Safety limits (all overridable via environment variables):
  MAX_POSITION_PCT   Max % of portfolio allocated to a single position (default 5%)
  STOP_LOSS_PCT      Hard stop: sell if price drops this much from avg cost (default -2%)
  TRAILING_STOP_PCT  Trailing stop: sell if price drops this much from peak (default -3%)
  DAILY_MAX_LOSS_PCT Circuit breaker: freeze bot if portfolio drops by this today (default -2%)
  MAX_DAILY_TRADES   Hard cap on trades per calendar day (default 10)

Pattern Day Trader (PDT) protection:
  PDT_ACCOUNT_EQUITY  Your Robinhood account equity (default 0 = protection active)
  If equity < $25,000, blocks any 4th+ day trade in a 5-business-day window.

Kill switch:
  freeze() / unfreeze() – instant stop / resume of all new trades
"""

import logging
import os
import threading
from collections import deque
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


def _pct(env_key: str, default: float) -> float:
    return float(os.getenv(env_key, default))


class RiskManager:
    PDT_EQUITY_THRESHOLD = 25_000.0
    PDT_MAX_DAY_TRADES_5D = 3

    def __init__(self):
        self.MAX_POSITION_PCT = _pct("RISK_MAX_POSITION_PCT", 0.05)
        self.STOP_LOSS_PCT = _pct("RISK_STOP_LOSS_PCT", -0.02)
        self.TRAILING_STOP_PCT = _pct("RISK_TRAILING_STOP_PCT", -0.03)
        self.DAILY_MAX_LOSS_PCT = _pct("RISK_DAILY_MAX_LOSS_PCT", -0.02)
        self.MAX_DAILY_TRADES = int(os.getenv("RISK_MAX_DAILY_TRADES", "10"))
        self.ACCOUNT_EQUITY = _pct("PDT_ACCOUNT_EQUITY", 0.0)

        self._frozen = threading.Event()
        self._session_start_value: float = 0.0
        self._position_peaks: dict[str, float] = {}
        self._daily_trades: int = 0
        self._trade_date: date = date.today()
        # timestamps of buy+sell-same-day "day trades" for PDT tracking
        self._day_trade_log: deque[datetime] = deque()

    # ------------------------------------------------------------------
    # Kill switch
    # ------------------------------------------------------------------

    @property
    def is_frozen(self) -> bool:
        return self._frozen.is_set()

    def freeze(self) -> None:
        self._frozen.set()
        logger.warning("RiskManager: bot FROZEN by kill switch.")

    def unfreeze(self) -> None:
        self._frozen.clear()
        logger.info("RiskManager: bot unfrozen.")

    # ------------------------------------------------------------------
    # Session baseline
    # ------------------------------------------------------------------

    def set_session_value(self, portfolio_value: float) -> None:
        self._session_start_value = portfolio_value

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def check_circuit_breaker(self, current_value: float) -> bool:
        """Returns True when trading must halt (frozen or daily loss limit hit)."""
        if self._frozen.is_set():
            return True

        today = date.today()
        if today != self._trade_date:
            self._daily_trades = 0
            self._trade_date = today

        if self._daily_trades >= self.MAX_DAILY_TRADES:
            logger.warning("Max daily trades reached – halting for the day.")
            return True

        if self._session_start_value > 0:
            change = (current_value - self._session_start_value) / self._session_start_value
            if change < self.DAILY_MAX_LOSS_PCT:
                self.freeze()
                logger.error(
                    f"Daily loss circuit breaker: portfolio down {change:.1%} "
                    f"(limit {self.DAILY_MAX_LOSS_PCT:.1%}) – bot FROZEN."
                )
                return True

        return False

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def position_size(self, portfolio_value: float, price: float) -> int:
        max_spend = portfolio_value * self.MAX_POSITION_PCT
        shares = int(max_spend / price)
        return max(1, shares)

    # ------------------------------------------------------------------
    # Stop-loss / trailing stop
    # ------------------------------------------------------------------

    def should_stop_loss(
        self, symbol: str, current_price: float, avg_buy_price: float
    ) -> bool:
        pct_change = (current_price - avg_buy_price) / avg_buy_price
        if pct_change < self.STOP_LOSS_PCT:
            logger.info(
                f"Hard stop-loss triggered for {symbol}: {pct_change:.1%} "
                f"(limit {self.STOP_LOSS_PCT:.1%})"
            )
            return True

        peak = self._position_peaks.get(symbol, avg_buy_price)
        if current_price > peak:
            self._position_peaks[symbol] = current_price
        else:
            trail_pct = (current_price - peak) / peak
            if trail_pct < self.TRAILING_STOP_PCT:
                logger.info(
                    f"Trailing stop triggered for {symbol}: {trail_pct:.1%} off peak "
                    f"(limit {self.TRAILING_STOP_PCT:.1%})"
                )
                return True

        return False

    # ------------------------------------------------------------------
    # Pattern Day Trader (PDT) protection
    # ------------------------------------------------------------------

    def pdt_would_block(self) -> bool:
        """Return True if taking another day trade now would trip PDT rules."""
        if self.ACCOUNT_EQUITY >= self.PDT_EQUITY_THRESHOLD:
            return False
        self._prune_day_trade_log()
        return len(self._day_trade_log) >= self.PDT_MAX_DAY_TRADES_5D

    def record_day_trade(self) -> None:
        """Call this when a buy+sell-same-day cycle closes."""
        self._day_trade_log.append(datetime.now())
        self._prune_day_trade_log()

    def pdt_trades_in_window(self) -> int:
        self._prune_day_trade_log()
        return len(self._day_trade_log)

    def _prune_day_trade_log(self) -> None:
        cutoff = datetime.now() - timedelta(days=5)
        while self._day_trade_log and self._day_trade_log[0] < cutoff:
            self._day_trade_log.popleft()

    # ------------------------------------------------------------------
    # Trade accounting
    # ------------------------------------------------------------------

    def record_trade(self) -> None:
        today = date.today()
        if today != self._trade_date:
            self._daily_trades = 0
            self._trade_date = today
        self._daily_trades += 1

    def clear_position_peak(self, symbol: str) -> None:
        self._position_peaks.pop(symbol, None)

    def get_stats(self) -> dict:
        return {
            "frozen": self.is_frozen,
            "daily_trades": self._daily_trades,
            "max_daily_trades": self.MAX_DAILY_TRADES,
            "session_start_value": self._session_start_value,
            "pdt_trades_5d": self.pdt_trades_in_window(),
            "pdt_active": self.ACCOUNT_EQUITY < self.PDT_EQUITY_THRESHOLD,
        }
