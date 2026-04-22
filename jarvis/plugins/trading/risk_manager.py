"""Risk manager - enforces position limits, stop-losses, and circuit breakers.

Safety limits (all overridable via environment variables):
  MAX_POSITION_PCT   Max % of portfolio allocated to a single position (default 5%)
  STOP_LOSS_PCT      Hard stop: sell if price drops this much from avg cost (default -2%)
  TRAILING_STOP_PCT  Trailing stop: sell if price drops this much from peak (default -3%)
  DAILY_MAX_LOSS_PCT Circuit breaker: freeze bot if portfolio drops by this today (default -2%)
  MAX_DAILY_TRADES   Hard cap on trades per calendar day (default 10)

Kill switch:
  call freeze() to instantly stop new trades
  call unfreeze() to resume
"""

import os
import threading
import logging
from datetime import date

logger = logging.getLogger(__name__)


def _pct(env_key: str, default: float) -> float:
    return float(os.getenv(env_key, default))


class RiskManager:
    def __init__(self):
        self.MAX_POSITION_PCT = _pct("RISK_MAX_POSITION_PCT", 0.05)
        self.STOP_LOSS_PCT = _pct("RISK_STOP_LOSS_PCT", -0.02)
        self.TRAILING_STOP_PCT = _pct("RISK_TRAILING_STOP_PCT", -0.03)
        self.DAILY_MAX_LOSS_PCT = _pct("RISK_DAILY_MAX_LOSS_PCT", -0.02)
        self.MAX_DAILY_TRADES = int(os.getenv("RISK_MAX_DAILY_TRADES", "10"))

        self._frozen = threading.Event()
        self._session_start_value: float = 0.0
        self._position_peaks: dict[str, float] = {}
        self._daily_trades: int = 0
        self._trade_date: date = date.today()

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

        # Reset daily counter on new trading day
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
        """Number of shares to buy respecting the max-position limit."""
        max_spend = portfolio_value * self.MAX_POSITION_PCT
        shares = int(max_spend / price)
        return max(1, shares)

    # ------------------------------------------------------------------
    # Stop-loss / trailing stop
    # ------------------------------------------------------------------

    def should_stop_loss(
        self, symbol: str, current_price: float, avg_buy_price: float
    ) -> bool:
        """Returns True if the position should be exited for risk reasons."""
        # Hard stop-loss from cost basis
        pct_change = (current_price - avg_buy_price) / avg_buy_price
        if pct_change < self.STOP_LOSS_PCT:
            logger.info(
                f"Hard stop-loss triggered for {symbol}: {pct_change:.1%} "
                f"(limit {self.STOP_LOSS_PCT:.1%})"
            )
            return True

        # Trailing stop from highest price since purchase
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
        }
