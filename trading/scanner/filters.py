"""Pure filter functions applied to a StockSnapshot. No I/O here — testable in isolation."""

from __future__ import annotations

from trading.config import ScannerConfig
from trading.scanner.models import StockSnapshot


def passes_price(config: ScannerConfig, snap: StockSnapshot) -> bool:
    return config.price_min <= snap.price <= config.price_max


def passes_market_cap(config: ScannerConfig, snap: StockSnapshot) -> bool:
    market_cap = snap.fundamentals.market_cap
    return market_cap is not None and market_cap <= config.market_cap_max


def passes_float(config: ScannerConfig, snap: StockSnapshot) -> bool:
    float_shares = snap.fundamentals.float_shares
    return float_shares is not None and config.min_float_shares <= float_shares <= config.max_float_shares


def passes_premarket_volume(config: ScannerConfig, snap: StockSnapshot) -> bool:
    return snap.premarket_volume >= config.min_premarket_volume


def passes_avg_daily_volume(config: ScannerConfig, snap: StockSnapshot) -> bool:
    return snap.avg_daily_volume >= config.min_avg_daily_volume


def passes_relative_volume(config: ScannerConfig, snap: StockSnapshot) -> bool:
    return snap.relative_volume >= config.min_relative_volume


def passes_gap(config: ScannerConfig, snap: StockSnapshot) -> bool:
    return snap.gap_pct >= config.min_gap_pct


def passes_otc(config: ScannerConfig, snap: StockSnapshot) -> bool:
    if not config.exclude_otc:
        return True
    return snap.exchange.upper() != "OTC"


ALL_FILTERS = (
    passes_price,
    passes_market_cap,
    passes_float,
    passes_premarket_volume,
    passes_avg_daily_volume,
    passes_relative_volume,
    passes_gap,
    passes_otc,
)


def passes_all_filters(config: ScannerConfig, snap: StockSnapshot) -> bool:
    return all(f(config, snap) for f in ALL_FILTERS)
