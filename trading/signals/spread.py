"""Bid/ask spread filter — small caps can look tradable and be untradeable in practice."""

from __future__ import annotations


def spread_pct(bid: float, ask: float) -> float:
    midpoint = (bid + ask) / 2
    if midpoint <= 0:
        return float("inf")
    return (ask - bid) / midpoint * 100


def passes_spread_filter(bid: float, ask: float, max_spread_pct: float) -> bool:
    return spread_pct(bid, ask) <= max_spread_pct
