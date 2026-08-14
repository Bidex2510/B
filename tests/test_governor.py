from datetime import datetime, timedelta

from trading.risk.governor import RiskGovernor
from trading.risk.models import RiskConfig

CONFIG = RiskConfig(
    risk_pct_per_trade=0.005,
    min_risk_reward=2.0,
    daily_loss_limit_pct=0.015,  # $150 on a $10k account
    max_trades_per_day=5,
    consecutive_loss_limit=3,
    cooldown_minutes=10,
)

NOW = datetime(2026, 8, 14, 10, 0)


def test_fresh_governor_allows_trading():
    governor = RiskGovernor(CONFIG, account_equity=10_000)
    allowed, reason = governor.can_trade(NOW)
    assert allowed
    assert reason == ""


def test_daily_loss_limit_locks_bot():
    governor = RiskGovernor(CONFIG, account_equity=10_000)
    governor.record_trade(pnl=-150, closed_at=NOW)
    allowed, reason = governor.can_trade(NOW + timedelta(minutes=20))
    assert not allowed
    assert "daily loss limit" in reason


def test_consecutive_losses_lock_bot():
    governor = RiskGovernor(CONFIG, account_equity=10_000)
    for i in range(3):
        governor.record_trade(pnl=-10, closed_at=NOW + timedelta(minutes=20 * i))
    allowed, reason = governor.can_trade(NOW + timedelta(hours=1))
    assert not allowed
    assert "consecutive loss" in reason


def test_win_resets_consecutive_losses():
    governor = RiskGovernor(CONFIG, account_equity=10_000)
    governor.record_trade(pnl=-10, closed_at=NOW)
    governor.record_trade(pnl=-10, closed_at=NOW + timedelta(minutes=20))
    governor.record_trade(pnl=50, closed_at=NOW + timedelta(minutes=40))
    assert governor.consecutive_losses == 0


def test_max_trades_per_day_locks_bot():
    governor = RiskGovernor(CONFIG, account_equity=10_000)
    for i in range(5):
        governor.record_trade(pnl=10, closed_at=NOW + timedelta(minutes=20 * i))
    allowed, reason = governor.can_trade(NOW + timedelta(hours=3))
    assert not allowed
    assert "max trades" in reason


def test_cooldown_blocks_immediate_retrade():
    governor = RiskGovernor(CONFIG, account_equity=10_000)
    governor.record_trade(pnl=10, closed_at=NOW)
    allowed, reason = governor.can_trade(NOW + timedelta(minutes=5))
    assert not allowed
    assert "cooldown" in reason


def test_cooldown_clears_after_window():
    governor = RiskGovernor(CONFIG, account_equity=10_000)
    governor.record_trade(pnl=10, closed_at=NOW)
    allowed, _ = governor.can_trade(NOW + timedelta(minutes=11))
    assert allowed


def test_reset_day_clears_state():
    governor = RiskGovernor(CONFIG, account_equity=10_000)
    governor.record_trade(pnl=-150, closed_at=NOW)
    governor.reset_day()
    allowed, _ = governor.can_trade(NOW)
    assert allowed
