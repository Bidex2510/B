# Small-Cap Trading System

Python trading system for small-cap U.S. equities. Currently implements
**stage 1 of the build: the premarket scanner**. Everything downstream
(signal engine, risk engine, order manager, live execution) is not built yet
— see the roadmap at the bottom.

## Setup

```bash
pip install -r trading/requirements.txt
```

Add to your `.env` (never commit real keys):

```
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=true
```

Optional overrides for the default scan criteria (see `trading/config.py` for
defaults):

```
SCANNER_PRICE_MIN=2.0
SCANNER_PRICE_MAX=20.0
SCANNER_MARKET_CAP_MAX=1000000000
SCANNER_MIN_PREMARKET_VOLUME=500000
SCANNER_MIN_AVG_DAILY_VOLUME=1000000
SCANNER_MIN_RVOL=5.0
SCANNER_MIN_GAP_PCT=10.0
SCANNER_MIN_FLOAT=1000000
SCANNER_MAX_FLOAT=20000000
SCANNER_EXCLUDE_OTC=true
SCANNER_AVG_VOLUME_LOOKBACK_DAYS=20
```

### Fundamentals gap (read this before running)

Alpaca's Trading API and Market Data API do **not** provide market cap or
share float. The scanner reads them from `trading/data/fundamentals.csv`
(`symbol,market_cap,float_shares`), which ships empty. You must populate it
yourself — export it from a fundamentals data vendor, or write a different
`FundamentalsProvider` (see `trading/data/fundamentals.py`) against an API
that has this data. Any symbol missing from the CSV is skipped by the
scanner rather than assumed to pass.

## Run

```bash
python -m trading.cli
```

Prints the current watchlist:

```
Ticker    Price   Gap %    RVOL  Status
--------------------------------------------
ABCD       4.82   38.0%     8.4x  WATCH
```

## Tests

No live API calls — filters and the scanner pipeline are tested against
fakes/stubs.

```bash
pytest tests/
```

## Architecture

```
trading/
  config.py               # ScannerConfig: the tunable scan criteria
  data/
    alpaca_client.py       # Alpaca market/trading data wrapper
    fundamentals.py        # market cap / float provider (CSV-backed)
    fundamentals.csv        # populate this yourself
  scanner/
    models.py              # StockSnapshot, WatchlistEntry
    filters.py              # one pure function per criterion
    scanner.py              # universe -> snapshot -> filter -> watchlist
  cli.py                   # prints the watchlist
```

## Roadmap

This scanner is stage 1 only. Planned next stages, in order:

1. **Signal engine** — opening-range breakout/reclaim, VWAP alignment,
   FVG/order-block confluence (ports the logic from
   `indicators/sniper_open_complete_signal.pine`), liquidity filter
   (min dollar volume, max spread), market-regime filter (SPY/QQQ),
   time-of-day filter, trade-quality scoring (only trade setups above a
   score threshold).
2. **Risk engine** — volatility/structure-based stops (not a fixed $ or %),
   dynamic position sizing from risk-per-trade, daily loss limit, max
   concurrent positions/exposure.
3. **Backtester** — run the signal + risk engine against historical data
   before any live data is involved.
4. **Order manager / execution** — Alpaca order submission, fill
   reconciliation against actual broker state, stop/target management.
5. **Kill switch** — daily loss limit, consecutive-loss limit, data/broker
   disconnect, abnormal spread, position-mismatch detection.
6. **Trade database** — log every trade (ticker, entry/exit, setup, RVOL,
   float, VWAP distance, spread, slippage, P/L) to evaluate which
   characteristics actually produce edge.
7. **Dashboard** — live status, watchlist, open positions, kill switch.
8. Paper trading, then a small live account, then scale gradually.
