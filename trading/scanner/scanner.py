"""Orchestrates: universe -> per-symbol data -> filters -> watchlist."""

from __future__ import annotations

from typing import List, Protocol

from trading.config import ScannerConfig
from trading.data.fundamentals import FundamentalsProvider
from trading.scanner.filters import passes_all_filters
from trading.scanner.models import StockSnapshot, WatchlistEntry


class MarketDataSource(Protocol):
    def get_tradable_us_equities(self, exclude_otc: bool) -> List["_AssetLike"]:
        ...

    def get_daily_volume_stats(self, symbol: str, lookback_days: int) -> "_VolumeStatsLike":
        ...

    def get_premarket_volume(self, symbol: str) -> int:
        ...

    def get_latest_price(self, symbol: str) -> float:
        ...


class _AssetLike(Protocol):
    symbol: str
    exchange: str


class _VolumeStatsLike(Protocol):
    avg_daily_volume: float
    previous_close: float


class Scanner:
    def __init__(self, config: ScannerConfig, market_data: MarketDataSource, fundamentals: FundamentalsProvider):
        self._config = config
        self._market_data = market_data
        self._fundamentals = fundamentals

    def build_snapshot(self, symbol: str, exchange: str) -> StockSnapshot | None:
        fundamentals = self._fundamentals.get(symbol)
        if fundamentals is None:
            return None
        volume_stats = self._market_data.get_daily_volume_stats(symbol, self._config.avg_volume_lookback_days)
        if volume_stats.previous_close <= 0:
            return None
        premarket_volume = self._market_data.get_premarket_volume(symbol)
        price = self._market_data.get_latest_price(symbol)
        return StockSnapshot(
            symbol=symbol,
            exchange=exchange,
            price=price,
            previous_close=volume_stats.previous_close,
            premarket_volume=premarket_volume,
            avg_daily_volume=volume_stats.avg_daily_volume,
            fundamentals=fundamentals,
        )

    def run(self) -> List[WatchlistEntry]:
        assets = self._market_data.get_tradable_us_equities(exclude_otc=self._config.exclude_otc)
        watchlist: List[WatchlistEntry] = []
        for asset in assets:
            snapshot = self.build_snapshot(asset.symbol, asset.exchange)
            if snapshot is None:
                continue
            if passes_all_filters(self._config, snapshot):
                watchlist.append(WatchlistEntry(snapshot=snapshot))
        watchlist.sort(key=lambda entry: entry.snapshot.relative_volume, reverse=True)
        return watchlist
