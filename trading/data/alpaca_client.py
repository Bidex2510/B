"""Thin wrapper around alpaca-py for the data the scanner needs.

Credentials come from environment variables — never hardcode them:
  ALPACA_API_KEY
  ALPACA_SECRET_KEY
  ALPACA_PAPER=true|false  (defaults to true / paper trading)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo

from trading.signals.models import Candle

NY_TZ = ZoneInfo("America/New_York")


@dataclass
class AssetInfo:
    symbol: str
    exchange: str
    tradable: bool


@dataclass
class DailyVolumeStats:
    avg_daily_volume: float
    previous_close: float


class AlpacaClient:
    """Wraps alpaca.trading.client.TradingClient and
    alpaca.data.historical.stock.StockHistoricalDataClient.

    Constructed lazily so importing this module doesn't require alpaca-py
    to be installed unless you actually instantiate a client.
    """

    def __init__(self, api_key: str | None = None, secret_key: str | None = None, paper: bool | None = None):
        api_key = api_key or os.environ["ALPACA_API_KEY"]
        secret_key = secret_key or os.environ["ALPACA_SECRET_KEY"]
        if paper is None:
            paper = os.environ.get("ALPACA_PAPER", "true").strip().lower() != "false"

        from alpaca.trading.client import TradingClient
        from alpaca.data.historical.stock import StockHistoricalDataClient

        self._trading = TradingClient(api_key, secret_key, paper=paper)
        self._data = StockHistoricalDataClient(api_key, secret_key)

    def get_tradable_us_equities(self, exclude_otc: bool = True) -> List[AssetInfo]:
        from alpaca.trading.requests import GetAssetsRequest
        from alpaca.trading.enums import AssetClass, AssetStatus, AssetExchange

        assets = self._trading.get_all_assets(
            GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
        )
        result = []
        for asset in assets:
            if not asset.tradable:
                continue
            if exclude_otc and asset.exchange == AssetExchange.OTC:
                continue
            result.append(AssetInfo(symbol=asset.symbol, exchange=str(asset.exchange), tradable=asset.tradable))
        return result

    def get_daily_volume_stats(self, symbol: str, lookback_days: int) -> DailyVolumeStats:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        end = datetime.now(NY_TZ)
        start = end - timedelta(days=lookback_days * 2)  # buffer for weekends/holidays
        bars = self._data.get_stock_bars(
            StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start, end=end)
        )
        symbol_bars = list(bars.data.get(symbol, []))[-lookback_days:]
        if len(symbol_bars) < 2:
            return DailyVolumeStats(avg_daily_volume=0.0, previous_close=0.0)
        avg_volume = sum(b.volume for b in symbol_bars) / len(symbol_bars)
        previous_close = symbol_bars[-1].close
        return DailyVolumeStats(avg_daily_volume=avg_volume, previous_close=previous_close)

    def get_premarket_volume(self, symbol: str) -> int:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        now_ny = datetime.now(NY_TZ)
        premarket_start = now_ny.replace(hour=4, minute=0, second=0, microsecond=0)
        market_open = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)
        window_end = min(now_ny, market_open)
        if window_end <= premarket_start:
            return 0
        bars = self._data.get_stock_bars(
            StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute,
                start=premarket_start,
                end=window_end,
            )
        )
        return sum(b.volume for b in bars.data.get(symbol, []))

    def get_latest_price(self, symbol: str) -> float:
        from alpaca.data.requests import StockLatestTradeRequest

        trades = self._data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
        return float(trades[symbol].price)

    def get_minute_bars(self, symbol: str, start: datetime, end: datetime) -> List[Candle]:
        """Historical 1-minute bars for an arbitrary window, used by the backtester."""
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        bars = self._data.get_stock_bars(StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Minute, start=start, end=end))
        return [
            Candle(time=bar.timestamp.astimezone(NY_TZ), open=bar.open, high=bar.high, low=bar.low, close=bar.close, volume=bar.volume)
            for bar in bars.data.get(symbol, [])
        ]
