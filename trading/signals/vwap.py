"""Session VWAP — a running volume-weighted average price, reset each session."""

from __future__ import annotations

from typing import List

from trading.signals.models import Candle


def compute_session_vwap(candles: List[Candle]) -> List[float]:
    """Returns one VWAP value per candle, computed cumulatively from the first candle.

    Callers must pass only the current session's candles (e.g. from market open) —
    this does not reset internally on a day boundary.
    """
    vwap_values: List[float] = []
    cumulative_pv = 0.0
    cumulative_volume = 0.0
    for candle in candles:
        typical_price = (candle.high + candle.low + candle.close) / 3
        cumulative_pv += typical_price * candle.volume
        cumulative_volume += candle.volume
        vwap_values.append(cumulative_pv / cumulative_volume if cumulative_volume > 0 else candle.close)
    return vwap_values
