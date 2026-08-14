"""Combines VWAP, liquidity sweep, opening range, and FVG confluence into a trade signal.

Requires ALL of: momentum, VWAP alignment, opening-range breakout/breakdown,
a liquidity sweep+reclaim of a key level, and an FVG in the same direction.
This is deliberately strict — the point is fewer, higher-quality setups, not
more signals.
"""

from __future__ import annotations

from typing import List, Optional

from trading.signals.fvg import detect_fvg
from trading.signals.liquidity_sweep import detect_sweep
from trading.signals.models import Candle, Direction, OpeningRange, TradeSignal
from trading.signals.vwap import compute_session_vwap


def generate_signal(
    session_candles: List[Candle],
    opening_range: OpeningRange,
    long_sweep_level: Optional[float] = None,
    short_sweep_level: Optional[float] = None,
) -> Optional[TradeSignal]:
    """session_candles: today's 1-minute bars from market open through now, oldest-to-newest.

    long_sweep_level/short_sweep_level: the key support/resistance level a long/short
    setup should show a sweep-and-reclaim of (e.g. premarket low, prior day low/high).
    """
    if len(session_candles) < 3:
        return None

    current = session_candles[-1]
    vwap = compute_session_vwap(session_candles)[-1]
    fvg = detect_fvg(session_candles)

    if (
        current.is_bullish
        and current.close > vwap
        and current.close > opening_range.high
        and long_sweep_level is not None
        and detect_sweep(session_candles, long_sweep_level, Direction.LONG) is not None
        and fvg is not None
        and fvg.direction == Direction.LONG
    ):
        return TradeSignal(
            direction=Direction.LONG,
            entry=current.low,
            reasons=("momentum", "vwap_above", "opening_range_breakout", "liquidity_sweep", "fvg"),
        )

    if (
        current.is_bearish
        and current.close < vwap
        and current.close < opening_range.low
        and short_sweep_level is not None
        and detect_sweep(session_candles, short_sweep_level, Direction.SHORT) is not None
        and fvg is not None
        and fvg.direction == Direction.SHORT
    ):
        return TradeSignal(
            direction=Direction.SHORT,
            entry=current.high,
            reasons=("momentum", "vwap_below", "opening_range_breakdown", "liquidity_sweep", "fvg"),
        )

    return None
