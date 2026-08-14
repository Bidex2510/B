from datetime import datetime, timedelta

from trading.backtest.models import Trade
from trading.backtest.stats import compute_max_drawdown, compute_stats
from trading.signals.models import Direction

BASE_TIME = datetime(2026, 8, 14, 9, 30)


def make_trade(pnl, minute, direction=Direction.LONG):
    entry = 5.00
    stop = 4.80
    exit_price = entry + (pnl / 250) if direction == Direction.LONG else entry - (pnl / 250)
    return Trade(
        symbol="ABCD",
        direction=direction,
        entry_time=BASE_TIME + timedelta(minutes=minute),
        entry_price=entry,
        stop_price=stop,
        target_price=entry + 0.60,
        shares=250,
        exit_time=BASE_TIME + timedelta(minutes=minute + 10),
        exit_price=exit_price,
        exit_reason="target" if pnl > 0 else "stop",
    )


def test_compute_stats_empty():
    stats = compute_stats([])
    assert stats.total_trades == 0
    assert stats.win_rate == 0.0
    assert stats.profit_factor == 0.0


def test_compute_stats_mixed_trades():
    trades = [make_trade(100, 0), make_trade(-50, 10), make_trade(150, 20)]
    stats = compute_stats(trades)

    assert stats.total_trades == 3
    assert round(stats.win_rate, 4) == round(2 / 3, 4)
    assert round(stats.average_win, 2) == 125.0
    assert round(stats.average_loss, 2) == -50.0
    assert round(stats.expectancy, 2) == round((100 - 50 + 150) / 3, 2)
    assert round(stats.profit_factor, 4) == round(250 / 50, 4)
    assert round(stats.total_pnl, 2) == 200.0


def test_compute_stats_all_losses_profit_factor_zero():
    trades = [make_trade(-50, 0), make_trade(-25, 10)]
    stats = compute_stats(trades)
    assert stats.profit_factor == 0.0


def test_max_drawdown_tracks_peak_to_trough():
    trades = [make_trade(100, 0), make_trade(-150, 10), make_trade(50, 20)]
    # equity curve: 100 -> -50 -> 0 ; peak 100, trough -50 -> drawdown 150
    assert round(compute_max_drawdown(trades), 2) == 150.0


def test_max_drawdown_zero_when_always_winning():
    trades = [make_trade(50, 0), make_trade(75, 10)]
    assert compute_max_drawdown(trades) == 0.0
