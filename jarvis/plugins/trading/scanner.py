"""Stock/ETF scanner - maintains the watchlist and discovers trade candidates.

The bot can trade ANY publicly listed US stock, not just large-caps.
Universe sources (layered, each adds breadth):

  1. Static core list  – 20 mega-cap + 25 ETFs (always present)
  2. Extended mid-cap  – ~120 additional growth/sector/small-cap stocks
  3. S&P 500 components – fetched from Wikipedia, cached 24 h
                          (enabled by default; disable with USE_SP500=false)
  4. Dynamic movers    – yfinance screener: day-gainers, most-actives, …
                          cached 5 min; runs in background each scan cycle

Override everything via TRADING_WATCHLIST env var (comma-separated tickers).
"""

import logging
import os
import random
import threading
import time

import yfinance as yf

logger = logging.getLogger(__name__)

# ── Core static lists ─────────────────────────────────────────────────────────

_DEFAULT_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "NVDA", "TSLA", "JPM", "JNJ", "V",
    "UNH", "HD", "MA", "DIS", "NFLX",
    "PYPL", "ADBE", "CRM", "AMD", "COST",
]

_DEFAULT_ETFS = [
    "SPY", "QQQ", "IWM", "DIA", "VTI",     # Broad market
    "VOO", "VGT", "VUG", "VEA", "VWO",     # Core Vanguard / intl
    "XLK", "XLF", "XLE", "XLV", "XLY",     # Sectors
    "XLP", "XLI", "XLB", "XLU", "XLRE",    # Sectors
    "ARKK", "SMH", "SOXX", "TLT", "GLD",   # Thematic / safe-haven
]

# Extended universe: mid-cap, growth, speculative, and sector leaders
_EXTENDED_STOCKS = [
    # Cloud / SaaS
    "SNOW", "DDOG", "CRWD", "NET", "OKTA", "ZS", "MDB", "FTNT", "PANW",
    "TWLO", "BILL", "HUBS", "TEAM", "ESTC", "CFLT", "GTLB",
    # Fintech / Crypto-adjacent
    "COIN", "HOOD", "SOFI", "AFRM", "UPST", "NU", "LC", "OPEN",
    # E-commerce / Consumer Tech
    "SHOP", "SQ", "ETSY", "CHWY", "W", "WISH", "ABNB", "UBER", "LYFT",
    "DASH", "RBLX", "U", "MTCH", "SNAP", "PINS",
    # Healthcare / Biotech
    "TDOC", "HIMS", "RXRX", "PACB", "EXAS", "MRNA", "BNTX", "NVAX",
    "SGEN", "BMRN", "ALNY", "IONS", "ACAD", "SRPT", "RARE",
    # Energy / Clean-tech / EV
    "RIVN", "LCID", "NIO", "XPEV", "LI", "PLUG", "FCEL", "BLNK", "CHPT",
    "ENPH", "SEDG", "RUN", "NOVA", "ARRY",
    # Semiconductors (beyond NVDA/AMD)
    "MRVL", "MPWR", "WOLF", "OLED", "AMBA", "AEHR", "ACLS", "ONTO",
    "LSCC", "ALGM", "FORM",
    # Retail / Consumer
    "LULU", "CPNG", "SE", "GRAB", "BABA", "JD", "PDD", "MELI",
    # Media / Entertainment
    "ROKU", "SPOT", "WMG", "LYV", "DKNG", "PENN",
    # Real Estate Tech / Proptech
    "EXPI", "RDFN", "COMP",
    # Aerospace / Defense
    "RKLB", "SPCE", "ASTS", "LUNR",
    # Meme / high-retail-interest
    "GME", "AMC", "BBBY", "PLTR", "BB", "NOK", "SNDL", "CLOV",
    # Mid-cap industrials / cyclicals
    "STLA", "F", "GM", "RIVN", "ZEV",
    # Financial services
    "SCHW", "IBKR", "MKTX", "LPLA", "RJF",
    # Healthcare services
    "ACCD", "DOCS", "PHR", "CERT", "ONEM",
]

MIN_AVG_VOLUME = 500_000  # Lowered to allow smaller stocks

# ── Wikipedia S&P 500 cache ───────────────────────────────────────────────────

_sp500_symbols: list[str] = []
_sp500_fetched_at: float = 0.0
_SP500_TTL = 86_400  # 24 h
_sp500_lock = threading.Lock()


def get_sp500_symbols() -> list[str]:
    """Return S&P 500 tickers from Wikipedia, cached for 24 hours."""
    global _sp500_symbols, _sp500_fetched_at
    with _sp500_lock:
        if _sp500_symbols and (time.time() - _sp500_fetched_at) < _SP500_TTL:
            return list(_sp500_symbols)
        try:
            import pandas as pd
            tables = pd.read_html(
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                attrs={"id": "constituents"},
            )
            df = tables[0]
            raw = df["Symbol"].tolist()
            # yfinance uses dashes for dual-class shares (BRK.B → BRK-B)
            symbols = [str(s).replace(".", "-") for s in raw if isinstance(s, str)]
            _sp500_symbols = symbols
            _sp500_fetched_at = time.time()
            logger.info(f"[scanner] Loaded {len(symbols)} S&P 500 symbols from Wikipedia")
        except Exception as exc:
            logger.debug(f"[scanner] S&P 500 Wikipedia fetch failed: {exc}")
        return list(_sp500_symbols)


# ── Dynamic mover discovery ───────────────────────────────────────────────────

_mover_cache: list[str] = []
_mover_fetched_at: float = 0.0
_MOVER_TTL = 300  # 5 min
_mover_lock = threading.Lock()

_YF_SCREENS = [
    "day_gainers",
    "most_actives",
    "day_losers",
    "small_cap_gainers",
    "aggressive_small_caps",
    "undervalued_growth_stocks",
]


def discover_movers(max_symbols: int = 100, force: bool = False) -> list[str]:
    """Discover today's top movers via yfinance screener (cached 5 min)."""
    global _mover_cache, _mover_fetched_at
    with _mover_lock:
        if not force and _mover_cache and (time.time() - _mover_fetched_at) < _MOVER_TTL:
            return list(_mover_cache)

        found: set[str] = set()

        # --- yfinance Screener (v0.2.37+) ---
        for screen in _YF_SCREENS:
            try:
                screener = yf.Screener()
                screener.set_predefined_body(screen)
                resp = screener.response
                for item in resp.get("quotes", []):
                    sym = item.get("symbol", "")
                    if sym and sym.isalpha() and 1 <= len(sym) <= 5:
                        found.add(sym)
                if found:
                    logger.debug(f"[scanner] Screen '{screen}' added symbols; total so far: {len(found)}")
            except Exception as exc:
                logger.debug(f"[scanner] yf screener '{screen}' failed: {exc}")

        # --- Fallback: Yahoo Finance query API ---
        if not found:
            try:
                import urllib.request, json
                screens_fb = ["day_gainers", "most_actives", "small_cap_gainers"]
                for scr in screens_fb:
                    url = (
                        "https://query1.finance.yahoo.com/v1/finance/screener/"
                        f"predefined/saved?formatted=false&scrIds={scr}&count=25"
                    )
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        data = json.loads(resp.read())
                    quotes = (
                        data.get("finance", {})
                            .get("result", [{}])[0]
                            .get("quotes", [])
                    )
                    for q in quotes:
                        sym = q.get("symbol", "")
                        if sym and sym.isalpha() and 1 <= len(sym) <= 5:
                            found.add(sym)
            except Exception as exc:
                logger.debug(f"[scanner] Yahoo Finance fallback failed: {exc}")

        symbols = list(found)[:max_symbols]
        if symbols:
            _mover_cache = symbols
            _mover_fetched_at = time.time()
            logger.info(f"[scanner] Discovered {len(symbols)} movers today")

        return list(_mover_cache)


def get_discovered_movers() -> list[str]:
    """Return the cached mover list (non-blocking, no fetch)."""
    return list(_mover_cache)


# ── Universe assembly ─────────────────────────────────────────────────────────

def get_watchlist() -> list[str]:
    """Return the configured or default watchlist (static only)."""
    env_list = os.getenv("TRADING_WATCHLIST", "")
    if env_list.strip():
        return [s.strip().upper() for s in env_list.split(",") if s.strip()]
    return _DEFAULT_STOCKS + _DEFAULT_ETFS


def get_universe(include_sp500: bool | None = None, include_movers: bool = True) -> list[str]:
    """Return the full trading universe the bot may consider.

    Priority order:
      1. Env-override watchlist (if set, use ONLY those)
      2. Core static list (45 symbols)
      3. Extended mid/small-cap list (~100 more)
      4. S&P 500 components (opt-out with USE_SP500=false)
      5. Dynamic movers from screener (opt-out with DYNAMIC_SCAN=false)
    """
    env_list = os.getenv("TRADING_WATCHLIST", "")
    if env_list.strip():
        return [s.strip().upper() for s in env_list.split(",") if s.strip()]

    seen: set[str] = set()
    result: list[str] = []

    def _add(syms: list[str]) -> None:
        for s in syms:
            if s not in seen:
                seen.add(s)
                result.append(s)

    _add(_DEFAULT_STOCKS + _DEFAULT_ETFS)
    _add(_EXTENDED_STOCKS)

    # S&P 500 (Wikipedia, cached)
    use_sp500 = include_sp500
    if use_sp500 is None:
        use_sp500 = os.getenv("USE_SP500", "true").lower() not in ("false", "0", "no", "off")
    if use_sp500:
        _add(get_sp500_symbols())

    # Dynamic movers
    use_dynamic = include_movers and os.getenv("DYNAMIC_SCAN", "true").lower() not in ("false", "0", "no", "off")
    if use_dynamic:
        _add(get_discovered_movers())  # Use cache only (non-blocking)

    return result


# ── Scanner class ─────────────────────────────────────────────────────────────

class StockScanner:

    def get_watchlist(self) -> list[str]:
        """Return the full trading universe (shuffled so all stocks rotate)."""
        universe = get_universe()
        # Shuffle so that over successive cycles all symbols get evaluated
        random.shuffle(universe)
        return universe

    def filter_tradeable(self, symbols: list[str]) -> list[str]:
        """Drop symbols with insufficient average daily volume."""
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

    # Convenience wrappers so callers can use the class for everything
    @staticmethod
    def discover_movers(**kwargs) -> list[str]:
        return discover_movers(**kwargs)

    @staticmethod
    def get_universe(**kwargs) -> list[str]:
        return get_universe(**kwargs)
