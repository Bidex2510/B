"""Shared-capital, multi-symbol backtest: ONE risk governor and ONE equity
value across every symbol traded on a given day, with candles interleaved
bar-by-bar in chronological order across symbols. Contrast with
trading.backtest.portfolio.run_backtest_many, which gives each symbol its
own independently-allocated equity/governor.

Assumes every symbol's candle list for the day is the same length, aligned
to the same time index (e.g. one candle per minute from market open through
the trading window end, for every symbol). Symbols with gaps or missing bars
(halts, thin liquidity) aren't handled here - align your data before calling
this, or filter out symbols with incomplete data for the day.

Same simplifications as trading.backtest.simulator: exact-limit-price fills,
stop-before-target when both fall in the same bar, and starting_equity held
fixed for the whole day rather than compounding after each trade closes.
"""

from __future__ import annotations

from typing import Dict, List

from trading.backtest.models import BacktestConfig, DayLevels, Trade
from trading.backtest.simulator import check_exit, check_fill
from trading.risk.governor import RiskGovernor
from trading.risk.reward import nearest_target_above, nearest_target_below, passes_min_risk_reward
from trading.risk.sizing import calculate_shares
from trading.risk.stops import resolve_stop
from trading.signals.atr import latest_atr
from trading.signals.engine import generate_signal
from trading.signals.levels import opening_range
from trading.signals.models import Candle, Direction


def run_portfolio_day(
    session_candles_by_symbol: Dict[str, List[Candle]],
    config: BacktestConfig,
    levels_by_symbol: Dict[str, DayLevels],
    governor: RiskGovernor,
    max_fill_wait_bars: int = 15,
) -> List[Trade]:
    symbols = sorted(session_candles_by_symbol.keys())
    if not symbols:
        return []

    bar_count = len(session_candles_by_symbol[symbols[0]])
    for symbol in symbols:
        if len(session_candles_by_symbol[symbol]) != bar_count:
            raise ValueError("all symbols must have the same number of aligned candles")

    opening_ranges = {
        symbol: opening_range(session_candles_by_symbol[symbol], config.opening_range_minutes) for symbol in symbols
    }

    trades: List[Trade] = []
    open_trades: Dict[str, dict] = {}
    pending_signals: Dict[str, dict] = {}

    i = config.opening_range_minutes
    while i < bar_count:
        for symbol in symbols:
            opening_rng = opening_ranges[symbol]
            if opening_rng is None:
                continue
            candles = session_candles_by_symbol[symbol]
            current = candles[i]

            if symbol in open_trades:
                open_trade = open_trades[symbol]
                exit_info = check_exit(open_trade["direction"], open_trade["stop_price"], open_trade["target_price"], current)
                if exit_info is not None:
                    exit_price, exit_reason = exit_info
                    trade = Trade(
                        symbol=symbol,
                        direction=open_trade["direction"],
                        entry_time=open_trade["entry_time"],
                        entry_price=open_trade["entry_price"],
                        stop_price=open_trade["stop_price"],
                        target_price=open_trade["target_price"],
                        shares=open_trade["shares"],
                        exit_time=current.time,
                        exit_price=exit_price,
                        exit_reason=exit_reason,
                    )
                    trades.append(trade)
                    governor.record_trade(trade.pnl, current.time)
                    del open_trades[symbol]
                continue

            if symbol in pending_signals:
                pending = pending_signals[symbol]
                if check_fill(pending["direction"], pending["entry_price"], current):
                    open_trades[symbol] = {**pending, "entry_time": current.time}
                    del pending_signals[symbol]
                elif i - pending["placed_at_index"] >= max_fill_wait_bars:
                    del pending_signals[symbol]
                continue

            levels = levels_by_symbol.get(symbol)
            if levels is None:
                continue

            allowed, _ = governor.can_trade(current.time)
            if not allowed:
                continue

            window = candles[: i + 1]
            signal = generate_signal(window, opening_rng, levels.long_sweep_level, levels.short_sweep_level)
            if signal is None:
                continue

            structural_level = levels.long_sweep_level if signal.direction == Direction.LONG else levels.short_sweep_level
            if structural_level is None:
                continue

            atr = latest_atr(window, config.atr_period)
            stop_price = resolve_stop(signal.direction, signal.entry, structural_level, atr, config.risk_config.atr_stop_multiplier)
            target_fn = nearest_target_above if signal.direction == Direction.LONG else nearest_target_below
            target_price = target_fn(signal.entry, levels.target_levels, config.min_target_distance)
            if target_price is None:
                continue
            if not passes_min_risk_reward(signal.direction, signal.entry, stop_price, target_price, config.risk_config.min_risk_reward):
                continue

            shares = calculate_shares(config.starting_equity, config.risk_config.risk_pct_per_trade, signal.direction, signal.entry, stop_price)
            if shares <= 0:
                continue

            pending_signals[symbol] = {
                "direction": signal.direction,
                "entry_price": signal.entry,
                "stop_price": stop_price,
                "target_price": target_price,
                "shares": shares,
                "placed_at_index": i,
            }
        i += 1

    for symbol, open_trade in open_trades.items():
        last = session_candles_by_symbol[symbol][-1]
        trade = Trade(
            symbol=symbol,
            direction=open_trade["direction"],
            entry_time=open_trade["entry_time"],
            entry_price=open_trade["entry_price"],
            stop_price=open_trade["stop_price"],
            target_price=open_trade["target_price"],
            shares=open_trade["shares"],
            exit_time=last.time,
            exit_price=last.close,
            exit_reason="end_of_day",
        )
        trades.append(trade)
        governor.record_trade(trade.pnl, last.time)

    return trades
