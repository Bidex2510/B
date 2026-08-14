"""Daily risk governor: kill switch, consecutive-loss lockout, trade cap, cooldown.

Holds state for a single trading day. Call reset_day() at the start of each
new session.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Tuple

from trading.risk.models import RiskConfig


class RiskGovernor:
    def __init__(self, config: RiskConfig, account_equity: float):
        self._config = config
        self._account_equity = account_equity
        self._daily_pnl = 0.0
        self._trades_today = 0
        self._consecutive_losses = 0
        self._last_trade_closed_at: datetime | None = None

    def can_trade(self, now: datetime) -> Tuple[bool, str]:
        daily_loss_limit = self._account_equity * self._config.daily_loss_limit_pct
        if self._daily_pnl <= -daily_loss_limit:
            return False, "daily loss limit reached"
        if self._trades_today >= self._config.max_trades_per_day:
            return False, "max trades per day reached"
        if self._consecutive_losses >= self._config.consecutive_loss_limit:
            return False, "consecutive loss limit reached"
        if self._last_trade_closed_at is not None:
            cooldown_until = self._last_trade_closed_at + timedelta(minutes=self._config.cooldown_minutes)
            if now < cooldown_until:
                return False, "cooldown active"
        return True, ""

    def record_trade(self, pnl: float, closed_at: datetime) -> None:
        self._daily_pnl += pnl
        self._trades_today += 1
        self._last_trade_closed_at = closed_at
        self._consecutive_losses = self._consecutive_losses + 1 if pnl < 0 else 0

    def reset_day(self) -> None:
        self._daily_pnl = 0.0
        self._trades_today = 0
        self._consecutive_losses = 0
        self._last_trade_closed_at = None

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @property
    def trades_today(self) -> int:
        return self._trades_today

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses
