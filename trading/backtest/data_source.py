"""Historical candle sources for the multi-day backtester."""

from __future__ import annotations

from datetime import date, datetime, time as dt_time
from typing import List, Protocol
from zoneinfo import ZoneInfo

from trading.signals.models import Candle

NY_TZ = ZoneInfo("America/New_York")
DEFAULT_TRADING_WINDOW_END = dt_time(11, 0)


class HistoricalDataSource(Protocol):
    def get_premarket_candles(self, symbol: str, day: date) -> List[Candle]:
        ...

    def get_session_candles(self, symbol: str, day: date, end_time: dt_time = DEFAULT_TRADING_WINDOW_END) -> List[Candle]:
        ...


class AlpacaHistoricalDataSource:
    """Bounds the regular session to 9:30-11:00 ET by default, matching the
    strategy's opening-window focus rather than fetching the full trading day.
    """

    def __init__(self, client):
        self._client = client

    def get_premarket_candles(self, symbol: str, day: date) -> List[Candle]:
        start = datetime.combine(day, dt_time(4, 0), tzinfo=NY_TZ)
        end = datetime.combine(day, dt_time(9, 30), tzinfo=NY_TZ)
        return self._client.get_minute_bars(symbol, start, end)

    def get_session_candles(self, symbol: str, day: date, end_time: dt_time = DEFAULT_TRADING_WINDOW_END) -> List[Candle]:
        start = datetime.combine(day, dt_time(9, 30), tzinfo=NY_TZ)
        end = datetime.combine(day, end_time, tzinfo=NY_TZ)
        return self._client.get_minute_bars(symbol, start, end)
