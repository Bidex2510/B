from datetime import datetime

from trading.backtest.models import BacktestConfig, DayLevels
from trading.backtest.simulator import run_day
from trading.risk.governor import RiskGovernor
from trading.risk.models import RiskConfig
from trading.signals.models import Candle, Direction


def candle(o, h, l, c, minute, v=1000):
    return Candle(time=datetime(2026, 8, 14, 9, 30 + minute), open=o, high=h, low=l, close=c, volume=v)


def opening_range_and_setup_candles():
    """5 flat opening-range candles (~4.70-4.76), 3 more flat candles (no
    breakout yet), a sweep candle that dips to 4.55 and recovers, then the
    signal bar that breaks out above the opening range with a bullish FVG
    against the flat candles, followed by a fill candle."""
    return [
        candle(4.70, 4.72, 4.68, 4.71, 0),
        candle(4.71, 4.73, 4.69, 4.72, 1),
        candle(4.72, 4.74, 4.70, 4.73, 2),
        candle(4.73, 4.75, 4.71, 4.74, 3),
        candle(4.74, 4.76, 4.72, 4.75, 4),
        candle(4.75, 4.76, 4.74, 4.75, 5),
        candle(4.75, 4.76, 4.74, 4.75, 6),
        candle(4.75, 4.76, 4.74, 4.75, 7),  # FVG candle1 (high 4.76)
        candle(4.75, 4.76, 4.55, 4.70, 8),  # sweeps below 4.65
        candle(4.95, 5.20, 4.90, 5.15, 9),  # signal bar: low 4.90 > 4.76 -> FVG, breaks out, reclaims 4.65
        candle(5.15, 5.25, 4.85, 5.20, 10),  # fills the limit buy at 4.90
    ]


def make_config(min_target_distance=0.10):
    return BacktestConfig(
        risk_config=RiskConfig(risk_pct_per_trade=0.005, min_risk_reward=2.0, atr_stop_multiplier=1.0),
        starting_equity=10_000,
        opening_range_minutes=5,
        atr_period=14,
        min_target_distance=min_target_distance,
    )


def test_target_hit_produces_winning_trade():
    candles = opening_range_and_setup_candles() + [
        candle(5.20, 5.30, 5.15, 5.25, 11),
        candle(5.25, 5.65, 5.20, 5.60, 12),  # high 5.65 hits target 5.60
    ]
    config = make_config()
    governor = RiskGovernor(config.risk_config, account_equity=10_000)
    levels = DayLevels(long_sweep_level=4.65, target_levels=[5.60])

    trades = run_day("ABCD", candles, config, levels, governor)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.direction == Direction.LONG
    assert trade.entry_price == 4.90
    assert round(trade.stop_price, 6) == 4.65
    assert trade.target_price == 5.60
    assert trade.shares == 200
    assert trade.exit_reason == "target"
    assert round(trade.pnl, 2) == 140.00
    assert round(trade.r_multiple, 4) == 2.80


def test_stop_hit_produces_losing_trade():
    candles = opening_range_and_setup_candles() + [
        candle(5.10, 5.15, 4.60, 4.65, 11),  # low 4.60 hits stop 4.65
    ]
    config = make_config()
    governor = RiskGovernor(config.risk_config, account_equity=10_000)
    levels = DayLevels(long_sweep_level=4.65, target_levels=[5.60])

    trades = run_day("ABCD", candles, config, levels, governor)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "stop"
    assert round(trade.pnl, 2) == -50.00
    assert round(trade.r_multiple, 4) == -1.0


def test_governor_lockout_prevents_any_trade():
    config = make_config()
    governor = RiskGovernor(config.risk_config, account_equity=10_000)
    governor.record_trade(pnl=-500, closed_at=datetime(2026, 8, 14, 8, 0))  # exceeds 1.5% daily loss limit

    candles = opening_range_and_setup_candles() + [
        candle(5.20, 5.30, 5.15, 5.25, 11),
        candle(5.25, 5.65, 5.20, 5.60, 12),
    ]
    levels = DayLevels(long_sweep_level=4.65, target_levels=[5.60])

    trades = run_day("ABCD", candles, config, levels, governor)

    assert trades == []


def test_no_target_level_returns_no_trades():
    config = make_config()
    governor = RiskGovernor(config.risk_config, account_equity=10_000)
    candles = opening_range_and_setup_candles() + [
        candle(5.20, 5.30, 5.15, 5.25, 11),
        candle(5.25, 5.65, 5.20, 5.60, 12),
    ]
    levels = DayLevels(long_sweep_level=4.65, target_levels=[])  # no candidate targets

    trades = run_day("ABCD", candles, config, levels, governor)

    assert trades == []


def test_no_signal_returns_no_trades_when_no_sweep_level():
    config = make_config()
    governor = RiskGovernor(config.risk_config, account_equity=10_000)
    candles = opening_range_and_setup_candles() + [
        candle(5.20, 5.30, 5.15, 5.25, 11),
        candle(5.25, 5.65, 5.20, 5.60, 12),
    ]
    levels = DayLevels(target_levels=[5.60])  # no sweep level -> structural stop unavailable

    trades = run_day("ABCD", candles, config, levels, governor)

    assert trades == []
