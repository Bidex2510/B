"""Single-symbol, single-day backtest: walks bar-by-bar through the signal and
risk engines exactly as a live bot would see them (no lookahead), simulates
limit-order fills and stop/target exits, and applies the risk governor.

Simplifications, to be removed as the backtester matures:
  - Fills assume the exact limit price with no slippage.
  - If both stop and target fall inside the same bar's range, the stop is
    assumed to hit first (the conservative assumption without tick data).
  - Position sizing uses a fixed starting_equity for the whole day rather
    than compounding after each trade.
"""

from __future__ import annotations

from typing import List, Optional

from trading.backtest.models import BacktestConfig, DayLevels, Trade
from trading.risk.governor import RiskGovernor
from trading.risk.reward import nearest_target_above, nearest_target_below, passes_min_risk_reward
from trading.risk.sizing import calculate_shares
from trading.risk.stops import resolve_stop
from trading.signals.atr import latest_atr
from trading.signals.engine import generate_signal
from trading.signals.levels import opening_range
from trading.signals.models import Candle, Direction


def check_fill(direction: Direction, entry_price: float, candle: Candle) -> bool:
    if direction == Direction.LONG:
        return candle.low <= entry_price
    return candle.high >= entry_price


def check_exit(direction: Direction, stop_price: float, target_price: float, candle: Candle) -> Optional[tuple]:
    if direction == Direction.LONG:
        if candle.low <= stop_price:
            return stop_price, "stop"
        if candle.high >= target_price:
            return target_price, "target"
        return None
    if candle.high >= stop_price:
        return stop_price, "stop"
    if candle.low <= target_price:
        return target_price, "target"
    return None


def run_day(
    symbol: str,
    session_candles: List[Candle],
    config: BacktestConfig,
    levels: DayLevels,
    governor: RiskGovernor,
    max_fill_wait_bars: int = 15,
) -> List[Trade]:
    """session_candles: today's regular-session 1-minute bars, starting at market
    open (9:30 ET), oldest-to-newest. Premarket/prior-day levels belong in `levels`.
    """
    trades: List[Trade] = []
    opening_rng = opening_range(session_candles, config.opening_range_minutes)
    if opening_rng is None:
        return trades

    open_trade = None
    pending_signal = None
    i = config.opening_range_minutes

    while i < len(session_candles):
        current = session_candles[i]

        if open_trade is not None:
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
                open_trade = None
            i += 1
            continue

        if pending_signal is not None:
            if check_fill(pending_signal["direction"], pending_signal["entry_price"], current):
                open_trade = {**pending_signal, "entry_time": current.time}
                pending_signal = None
            elif i - pending_signal["placed_at_index"] >= max_fill_wait_bars:
                pending_signal = None
            i += 1
            continue

        allowed, _ = governor.can_trade(current.time)
        if allowed:
            window = session_candles[: i + 1]
            signal = generate_signal(window, opening_rng, levels.long_sweep_level, levels.short_sweep_level)
            if signal is not None:
                structural_level = levels.long_sweep_level if signal.direction == Direction.LONG else levels.short_sweep_level
                if structural_level is not None:
                    atr = latest_atr(window, config.atr_period)
                    stop_price = resolve_stop(signal.direction, signal.entry, structural_level, atr, config.risk_config.atr_stop_multiplier)
                    target_fn = nearest_target_above if signal.direction == Direction.LONG else nearest_target_below
                    target_price = target_fn(signal.entry, levels.target_levels, config.min_target_distance)
                    if target_price is not None and passes_min_risk_reward(
                        signal.direction, signal.entry, stop_price, target_price, config.risk_config.min_risk_reward
                    ):
                        shares = calculate_shares(
                            config.starting_equity, config.risk_config.risk_pct_per_trade, signal.direction, signal.entry, stop_price
                        )
                        if shares > 0:
                            pending_signal = {
                                "direction": signal.direction,
                                "entry_price": signal.entry,
                                "stop_price": stop_price,
                                "target_price": target_price,
                                "shares": shares,
                                "placed_at_index": i,
                            }
        i += 1

    if open_trade is not None:
        last = session_candles[-1]
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
