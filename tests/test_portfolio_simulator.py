from datetime import datetime

import pytest

from trading.backtest.models import BacktestConfig, DayLevels
from trading.backtest.portfolio_simulator import run_portfolio_day
from trading.backtest.simulator import run_day
from trading.risk.governor import RiskGovernor
from trading.risk.models import RiskConfig
from trading.signals.models import Candle, Direction


def candle(o, h, l, c, minute, v=1000):
    return Candle(time=datetime(2026, 8, 14, 9, 30 + minute), open=o, high=h, low=l, close=c, volume=v)


def opening_range_flat():
    return [
        candle(4.70, 4.72, 4.68, 4.71, 0),
        candle(4.71, 4.73, 4.69, 4.72, 1),
        candle(4.72, 4.74, 4.70, 4.73, 2),
        candle(4.73, 4.75, 4.71, 4.74, 3),
        candle(4.74, 4.76, 4.72, 4.75, 4),
    ]


def setup_shape(start_minute):
    m = start_minute
    return [
        candle(4.75, 4.76, 4.74, 4.75, m + 0),
        candle(4.75, 4.76, 4.74, 4.75, m + 1),
        candle(4.75, 4.76, 4.74, 4.75, m + 2),
        candle(4.75, 4.76, 4.55, 4.70, m + 3),  # sweeps below 4.65
        candle(4.95, 5.20, 4.90, 5.15, m + 4),  # signal bar: entry 4.90
        candle(5.15, 5.25, 4.85, 5.20, m + 5),  # fills at 4.90
        candle(5.20, 5.30, 5.15, 5.25, m + 6),
        candle(5.25, 5.65, 5.20, 5.60, m + 7),  # hits target 5.60
    ]


def flat_shape(start_minute, count):
    return [candle(4.75, 4.76, 4.74, 4.75, start_minute + i) for i in range(count)]


def make_config(max_trades_per_day=5, cooldown_minutes=10):
    return BacktestConfig(
        risk_config=RiskConfig(
            risk_pct_per_trade=0.005,
            min_risk_reward=2.0,
            atr_stop_multiplier=1.0,
            max_trades_per_day=max_trades_per_day,
            cooldown_minutes=cooldown_minutes,
        ),
        starting_equity=10_000,
        opening_range_minutes=5,
        atr_period=14,
        min_target_distance=0.10,
    )


def test_shared_governor_blocks_second_symbol_after_trade_cap():
    # AAAA completes its full round-trip trade well before BBBB's own
    # qualifying setup even forms, so by the time BBBB tries to enter, the
    # SHARED governor has already used up the one available trade slot.
    aaaa = opening_range_flat() + setup_shape(5) + flat_shape(13, 8)
    bbbb = opening_range_flat() + flat_shape(5, 8) + setup_shape(13)
    levels = {
        "AAAA": DayLevels(long_sweep_level=4.65, target_levels=[5.60]),
        "BBBB": DayLevels(long_sweep_level=4.65, target_levels=[5.60]),
    }
    config = make_config(max_trades_per_day=1)
    governor = RiskGovernor(config.risk_config, account_equity=10_000)

    trades = run_portfolio_day({"AAAA": aaaa, "BBBB": bbbb}, config, levels, governor)

    assert len(trades) == 1
    assert trades[0].symbol == "AAAA"
    assert trades[0].direction == Direction.LONG
    assert round(trades[0].pnl, 2) == 140.00


def test_independent_governors_would_have_let_both_trade():
    # Same data and same max_trades_per_day=1, but with a separate governor
    # per symbol (as trading.backtest.orchestrator.run_backtest does today)
    # nothing stops both from trading - proving the shared governor above
    # is doing real work, not coincidentally producing 1 trade.
    aaaa = opening_range_flat() + setup_shape(5) + flat_shape(13, 8)
    bbbb = opening_range_flat() + flat_shape(5, 8) + setup_shape(13)
    levels = {
        "AAAA": DayLevels(long_sweep_level=4.65, target_levels=[5.60]),
        "BBBB": DayLevels(long_sweep_level=4.65, target_levels=[5.60]),
    }
    config = make_config(max_trades_per_day=1)

    trades_a = run_day("AAAA", aaaa, config, levels["AAAA"], RiskGovernor(config.risk_config, account_equity=10_000))
    trades_b = run_day("BBBB", bbbb, config, levels["BBBB"], RiskGovernor(config.risk_config, account_equity=10_000))

    assert len(trades_a) == 1
    assert len(trades_b) == 1


def test_both_symbols_trade_when_trade_cap_allows_it():
    # cooldown disabled to isolate the trade-cap dimension - BBBB's setup
    # forms only 5 minutes after AAAA's trade closes, which the next test
    # shows is enough for the shared cooldown to block it on its own.
    aaaa = opening_range_flat() + setup_shape(5) + flat_shape(13, 8)
    bbbb = opening_range_flat() + flat_shape(5, 8) + setup_shape(13)
    levels = {
        "AAAA": DayLevels(long_sweep_level=4.65, target_levels=[5.60]),
        "BBBB": DayLevels(long_sweep_level=4.65, target_levels=[5.60]),
    }
    config = make_config(max_trades_per_day=5, cooldown_minutes=0)
    governor = RiskGovernor(config.risk_config, account_equity=10_000)

    trades = run_portfolio_day({"AAAA": aaaa, "BBBB": bbbb}, config, levels, governor)

    symbols = {trade.symbol for trade in trades}
    assert symbols == {"AAAA", "BBBB"}


def test_shared_cooldown_blocks_second_symbol_even_with_no_trade_cap():
    # Same setup, high trade cap, but default cooldown (10 min) - AAAA
    # closes at 9:42, BBBB's setup forms at 9:47, still inside the shared
    # cooldown window, so only AAAA trades.
    aaaa = opening_range_flat() + setup_shape(5) + flat_shape(13, 8)
    bbbb = opening_range_flat() + flat_shape(5, 8) + setup_shape(13)
    levels = {
        "AAAA": DayLevels(long_sweep_level=4.65, target_levels=[5.60]),
        "BBBB": DayLevels(long_sweep_level=4.65, target_levels=[5.60]),
    }
    config = make_config(max_trades_per_day=5, cooldown_minutes=10)
    governor = RiskGovernor(config.risk_config, account_equity=10_000)

    trades = run_portfolio_day({"AAAA": aaaa, "BBBB": bbbb}, config, levels, governor)

    assert {trade.symbol for trade in trades} == {"AAAA"}


def test_mismatched_candle_lengths_raise():
    levels = {"AAAA": DayLevels(), "BBBB": DayLevels()}
    config = make_config()
    governor = RiskGovernor(config.risk_config, account_equity=10_000)

    with pytest.raises(ValueError):
        run_portfolio_day(
            {"AAAA": opening_range_flat(), "BBBB": opening_range_flat()[:-1]}, config, levels, governor
        )


def test_no_symbols_returns_no_trades():
    config = make_config()
    governor = RiskGovernor(config.risk_config, account_equity=10_000)
    assert run_portfolio_day({}, config, {}, governor) == []
