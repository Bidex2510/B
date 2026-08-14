"""Performance metrics. Win rate alone is not the target — see PerformanceStats fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from trading.backtest.models import Trade


@dataclass(frozen=True)
class PerformanceStats:
    total_trades: int
    win_rate: float
    average_win: float
    average_loss: float
    expectancy: float
    profit_factor: float
    max_drawdown: float
    total_pnl: float


def compute_max_drawdown(trades: List[Trade]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for trade in sorted(trades, key=lambda t: t.exit_time):
        equity += trade.pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def compute_stats(trades: List[Trade]) -> PerformanceStats:
    if not trades:
        return PerformanceStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl <= 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float("inf") if gross_profit > 0 else 0.0

    return PerformanceStats(
        total_trades=len(trades),
        win_rate=len(wins) / len(trades),
        average_win=(sum(wins) / len(wins)) if wins else 0.0,
        average_loss=(sum(losses) / len(losses)) if losses else 0.0,
        expectancy=sum(t.pnl for t in trades) / len(trades),
        profit_factor=profit_factor,
        max_drawdown=compute_max_drawdown(trades),
        total_pnl=sum(t.pnl for t in trades),
    )
