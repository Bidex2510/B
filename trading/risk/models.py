"""Risk engine configuration — every threshold below is a backtest starting point, not a guarantee."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConfig:
    risk_pct_per_trade: float = 0.005  # 0.5% of equity
    min_risk_reward: float = 2.0
    atr_stop_multiplier: float = 1.0
    daily_loss_limit_pct: float = 0.015  # 1.5% of equity
    max_trades_per_day: int = 5
    consecutive_loss_limit: int = 3
    cooldown_minutes: int = 10
    max_spread_pct: float = 0.5
