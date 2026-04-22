"""Stock scanner - maintains the watchlist and pre-filters tradeable symbols.

Filters out stocks with < 1M average daily volume to ensure liquidity.
The default watchlist is S&P 500 blue chips (low volatility, high liquidity).
You can override the watchlist via the TRADING_WATCHLIST env var
(comma-separated ticker symbols, e.g. "AAPL,MSFT,TSLA").
"""

import os
import logging

import yfinance as yf

logger = logging.getLogger(__name__)

_DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "NVDA", "TSLA", "JPM", "JNJ", "V",
    "PG",   "UNH",  "HD",   "MA",  "DIS",
    "NFLX", "PYPL", "ADBE", "CRM", "INTC",
]

MIN_AVG_VOLUME = 1_000_000


class StockScanner:

    def get_watchlist(self) -> list[str]:
        env_list = os.getenv("TRADING_WATCHLIST", "")
        if env_list.strip():
            return [s.strip().upper() for s in env_list.split(",") if s.strip()]
        return list(_DEFAULT_WATCHLIST)

    def filter_tradeable(self, symbols: list[str]) -> list[str]:
        """Drop symbols with insufficient liquidity."""
        tradeable: list[str] = []
        for symbol in symbols:
            try:
                info = yf.Ticker(symbol).fast_info
                volume = getattr(info, "three_month_average_volume", None)
                if volume is not None and float(volume) < MIN_AVG_VOLUME:
                    logger.debug(f"Skipping {symbol}: avg volume {volume:,.0f} < {MIN_AVG_VOLUME:,}")
                    continue
                tradeable.append(symbol)
            except Exception as exc:
                logger.debug(f"Volume check failed for {symbol}: {exc}")
                tradeable.append(symbol)  # include on error rather than silently drop
        return tradeable

    def get_company_name(self, symbol: str) -> str:
        try:
            return yf.Ticker(symbol).info.get("shortName", symbol)
        except Exception:
            return symbol
