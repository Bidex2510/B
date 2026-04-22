"""Stock/ETF scanner - maintains the watchlist and pre-filters for liquidity.

Default watchlist is a balanced mix of mega-cap stocks and major ETFs
(index, sector, and thematic). ETFs dominate when the bot is used for
longer-term strategies (position/trend) because they give built-in
diversification; individual stocks give the day/scalp strategies enough
movement to work with.

Override via TRADING_WATCHLIST env var (comma-separated tickers).
"""

import logging
import os

import yfinance as yf

logger = logging.getLogger(__name__)

# Liquid mega-cap stocks
_DEFAULT_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "NVDA", "TSLA", "JPM", "JNJ", "V",
    "UNH", "HD", "MA", "DIS", "NFLX",
    "PYPL", "ADBE", "CRM", "AMD", "COST",
]

# Major ETFs: index, sector, and commodity
_DEFAULT_ETFS = [
    "SPY", "QQQ", "IWM", "DIA", "VTI",     # Broad market
    "VOO", "VGT", "VUG", "VEA", "VWO",     # Core Vanguard / intl
    "XLK", "XLF", "XLE", "XLV", "XLY",     # Sectors
    "XLP", "XLI", "XLB", "XLU", "XLRE",    # Sectors
    "ARKK", "SMH", "SOXX", "TLT", "GLD",   # Thematic / safe-haven
]

MIN_AVG_VOLUME = 1_000_000


class StockScanner:

    def get_watchlist(self) -> list[str]:
        env_list = os.getenv("TRADING_WATCHLIST", "")
        if env_list.strip():
            return [s.strip().upper() for s in env_list.split(",") if s.strip()]
        return _DEFAULT_STOCKS + _DEFAULT_ETFS

    def filter_tradeable(self, symbols: list[str]) -> list[str]:
        """Drop symbols with insufficient liquidity."""
        tradeable: list[str] = []
        for symbol in symbols:
            try:
                info = yf.Ticker(symbol).fast_info
                volume = getattr(info, "three_month_average_volume", None)
                if volume is not None and float(volume) < MIN_AVG_VOLUME:
                    logger.debug(
                        f"Skipping {symbol}: avg volume {volume:,.0f} < {MIN_AVG_VOLUME:,}"
                    )
                    continue
                tradeable.append(symbol)
            except Exception as exc:
                logger.debug(f"Volume check failed for {symbol}: {exc}")
                tradeable.append(symbol)
        return tradeable

    def get_company_name(self, symbol: str) -> str:
        try:
            return yf.Ticker(symbol).info.get("shortName", symbol)
        except Exception:
            return symbol
