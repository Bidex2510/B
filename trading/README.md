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
- **Backtester** (`trading/backtest/`) — bar-by-bar simulation of the signal +
  risk engines against historical candles (no lookahead), with simulated
  limit-order fills, stop/target exits, and performance stats (win rate, avg
  win/loss, expectancy, profit factor, max drawdown). Runs across a
  chronological range of days for one symbol, compounding account equity day
  to day while resetting the risk governor each session, with real
  `DayLevels` built from premarket/prior-day candles and chronological
  train/validate/test splitting. See `trading/backtest/README.md` —
  multi-symbol looping and an out-of-sample validation runner aren't built
  yet (the pieces are there; wiring them together per-symbol is on you for
  now).
- **Manual watchlist** (`trading/watchlist.py`) — add/remove tickers you want
  tracked regardless of whether they pass the scanner's filters.

Not built yet: catalyst filter, market-regime filter, trade-quality scoring,
order manager, broker execution, trade journal, dashboard — see the roadmap
at the bottom.

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
python -m trading.cli scan               # scanner watchlist + your manual watchlist
python -m trading.cli watch add ABCD     # add a ticker to your manual watchlist
python -m trading.cli watch remove ABCD
python -m trading.cli watch list
```

`scan` prints the scanner's output followed by your manually-watched tickers
(with live prices, if Alpaca credentials are configured):

```
SCANNER WATCHLIST
Ticker    Price   Gap %    RVOL  Status
--------------------------------------------
ABCD       4.82   38.0%     8.4x  WATCH

MANUALLY WATCHED
Ticker    Price
----------------
XYZ         7.31
```

The manual watchlist is stored locally in `trading/data/manual_watchlist.json`
(gitignored — it's your personal state, not shared through the repo).

## Tests

No live API calls anywhere — everything is tested against fakes/stubs/fixtures.

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
  backtest/
    models.py                # DayLevels, BacktestConfig, Trade
    simulator.py               # bar-by-bar single-symbol/day simulation, no lookahead
    stats.py                   # win rate, avg win/loss, expectancy, profit factor, max drawdown
    data_source.py              # HistoricalDataSource + AlpacaHistoricalDataSource
    levels_builder.py            # DayLevels from real premarket/prior-day candles
    orchestrator.py               # run_day across a date range, compounding equity
    period_split.py                # chronological train/validate/test splitting
  watchlist.py             # manually curated tickers (add/remove/list), local JSON state
  cli.py                   # scan + watch add/remove/list
```

## Roadmap

Scanner, signal engine, risk engine, a multi-day backtester (single symbol
per run), and a manual watchlist are built (see above). Planned next stages,
in order:

1. **Multi-symbol backtest loop + out-of-sample validation runner** — loop
   `run_backtest` across a watchlist and aggregate results; actually run the
   train/validate/test split through the backtester and compare results
   instead of eyeballing it manually. See `trading/backtest/README.md`.
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
