# Small-Cap Trading System

Python trading system for small-cap U.S. equities. Currently implements:

- **Scanner** (`trading/scanner/`) — filters the tradable universe down to a watchlist.
- **Signal engine** (`trading/signals/`) — VWAP, opening range, liquidity sweep,
  and FVG confluence, ported from `indicators/sniper_open_complete_signal.pine`.
  Deliberately strict: a signal requires momentum + VWAP alignment + an
  opening-range breakout/breakdown + a liquidity sweep-and-reclaim + an FVG,
  all in the same direction — fewer, higher-quality setups over more signals.
- **Risk engine** (`trading/risk/`) — structural stops with an ATR floor,
  R:R-based target selection, dynamic position sizing from account risk %,
  and a daily risk governor (loss limit, consecutive-loss lockout, max
  trades/day, cooldown between trades).

Not built yet: catalyst filter, market-regime filter, trade-quality scoring,
order manager, broker execution, trade journal, backtester, dashboard — see
the roadmap at the bottom.

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
  signals/
    models.py               # Candle, Direction, FvgZone, LiquiditySweep, OpeningRange, TradeSignal
    vwap.py                 # session VWAP
    levels.py                # premarket high/low, prior-day high/low, opening range
    fvg.py                   # fair value gap detection
    liquidity_sweep.py       # sweep-and-reclaim / sweep-and-reject detection
    spread.py                 # bid/ask spread filter
    engine.py                 # combines the above into a TradeSignal
  risk/
    models.py               # RiskConfig
    stops.py                 # structural stop with ATR floor
    reward.py                 # target selection, R:R computation/threshold
    sizing.py                 # position sizing from account risk %
    governor.py                # daily loss limit, consecutive-loss lockout, trade cap, cooldown
  cli.py                   # prints the watchlist
```

## Roadmap

Scanner, signal engine, and risk engine are built (see above). Planned next
stages, in order:

1. **Backtester** — run the signal + risk engine against historical data
   before any live/paper data is involved. Measure win rate, avg win/loss,
   expectancy, profit factor, max drawdown, R:R, performance by time-of-day
   and by opening-range window, and validate on out-of-sample data before
   trusting any result.
2. **Catalyst / market-regime / quality-scoring layers** — these need a
   news/fundamentals feed and SPY/QQQ/IWM data that aren't wired up yet.
   Only add once the core signal+risk pipeline has backtested edge; don't
   let a scoring system launder a strategy that doesn't otherwise work.
3. **Order manager / execution** — broker-agnostic interface (paper and live
   brokers implement the same interface so switching brokers never touches
   strategy code), fill reconciliation against actual broker state,
   stop/target management. Hard `PAPER_MODE` gate: the program only holds
   paper credentials while `PAPER_MODE=true`; switching to live requires an
   explicit config change to separate live credentials — never developed
   against live credentials. Before any live order reaches the broker, it
   passes signal validity → liquidity → spread → R:R → position size →
   daily loss limit → trade cap → broker-position-matches-internal-state,
   in that order; any failure blocks the order.
4. **Kill switch** — extends the risk governor with data/broker disconnect,
   abnormal spread, and position-mismatch detection (governor already
   covers daily loss limit, consecutive losses, trade cap, cooldown).
5. **Trade database** — log every trade (ticker, entry/exit, setup, RVOL,
   float, VWAP distance, spread, slippage, P/L) to evaluate which
   characteristics actually produce edge.
6. **Dashboard** — live status, watchlist, open positions, kill switch.
7. Paper trading (Alpaca), then a small live account, then scale gradually
   only once live execution data confirms the backtest/paper results.
