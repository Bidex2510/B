# Backtester

Single-symbol, single-day simulation of the signal + risk engines against
historical 1-minute bars. No lookahead: at each bar, only candles up to and
including that bar are visible to the signal engine.

## What it does

`trading.backtest.simulator.run_day(symbol, session_candles, config, levels, governor)`
walks bar-by-bar through a day's regular-session candles:

1. Computes the opening range from the first `config.opening_range_minutes` bars.
2. At each subsequent bar (while the risk governor allows a new trade),
   calls `trading.signals.engine.generate_signal` on the candles seen so far.
3. On a signal, resolves a structural+ATR stop, selects a target from
   `levels.target_levels`, and requires it to clear `min_risk_reward` before
   sizing the position and placing a simulated limit order.
4. Simulates the fill (or cancellation after `max_fill_wait_bars`), then
   walks forward checking for a stop or target hit each bar, closing at
   end-of-day if neither is hit.
5. Records each closed trade's P&L into the `RiskGovernor`, so daily loss
   limit / consecutive-loss / trade-cap / cooldown rules apply exactly as
   they would live.

`trading.backtest.stats.compute_stats(trades)` turns a list of `Trade`s into
win rate, average win/loss, expectancy, profit factor, and max drawdown.

## Multi-day / multi-symbol orchestration

`trading.backtest.orchestrator.run_backtest(symbol, trading_days, data_source, config)`
runs `run_day` across a chronological list of dates for one symbol:

- `trading.backtest.data_source.HistoricalDataSource` is the interface
  (`get_premarket_candles`, `get_session_candles`) — `AlpacaHistoricalDataSource`
  implements it via `AlpacaClient.get_minute_bars`, bounding the regular
  session to 9:30-11:00 ET by default (the strategy's opening window, not
  the full trading day). Untested against live Alpaca data in this repo — no
  credentials here; supply your own `HistoricalDataSource` (or a fake) to
  test against.
- `trading.backtest.levels_builder.build_day_levels(premarket, prior_day)`
  builds each day's `DayLevels` from real premarket/prior-day candles
  instead of hand-picked fixtures: sweep levels default to the premarket
  low/high, target levels pool premarket + prior-day high/low.
- Account equity compounds day to day (each day's `BacktestConfig.starting_equity`
  is the prior day's ending equity), but the `RiskGovernor` resets every day —
  a new session's daily loss limit, trade cap, and cooldown start fresh.
- `trading.backtest.period_split.split_trading_days(trading_days, train_pct, validate_pct)`
  splits a chronological day list into train/validate/test — never shuffled,
  since leaking future days into training makes the backtest lie about what
  the strategy would have seen live. `generate_weekdays(start, end)` is a
  bare Mon-Fri generator; it does not exclude market holidays.

To run a real multi-day backtest: build a symbol list (from the scanner, or
your manual watchlist), a trading-day range (`generate_weekdays` or your own
calendar), an `AlpacaHistoricalDataSource`, and loop `run_backtest` per
symbol, aggregating with `compute_stats(result.trades)`.

## Multi-symbol + out-of-sample validation

`trading.backtest.portfolio.run_backtest_many(symbols, trading_days, data_source, config)`
runs `run_backtest` once per symbol and aggregates into a `PortfolioBacktestResult`
(`.trades`, `.total_pnl`, `.results_by_symbol`). **Each symbol gets its own
independent equity curve and risk governor**, as if trading it with
separately allocated capital — this does not model one shared account
risking capital across concurrently-traded symbols. True portfolio-level
simulation (one risk governor and equity curve shared across symbols each
day) needs bar-by-bar interleaving across symbols and isn't built yet.

`trading.backtest.validation.run_out_of_sample_validation(symbols, trading_days, data_source, config, train_pct, validate_pct)`
splits `trading_days` via `split_trading_days` and runs `run_backtest_many`
independently on each of the three buckets, returning a `ValidationReport`
with `PerformanceStats` for train/validate/test. Each split is backtested as
its own fresh run — the first day of a split has no prior-day level from
outside that split (nothing carries over the split boundary), so a real
multi-day strategy naturally trades less on a split's first day than it
would mid-split.

A strategy that looks strong in `train` and falls apart in `validate`/`test`
was curve-fit, not unlucky — don't take that result to paper trading.

## What it does not do yet

- **Slippage/spread modeling.** Fills currently assume the exact limit
  price. Real small-cap execution is worse than this, especially in thin
  names — see `trading/README.md`'s note on paper vs. live execution.
- **Performance breakdowns** by time-of-day, opening-range window, or
  stock characteristics (price/float/market-cap buckets) — `compute_stats`
  is currently a single aggregate over whatever trade list you pass it;
  slicing trades by attribute before calling it gets you the breakdown.
- **Market holiday awareness** — `generate_weekdays` includes holidays as
  "trading days"; they'll just come back with no candles from a real data
  source and contribute nothing, but a real calendar would be cleaner.

## Example: single day

```python
from trading.backtest.models import BacktestConfig, DayLevels
from trading.backtest.simulator import run_day
from trading.backtest.stats import compute_stats
from trading.risk.governor import RiskGovernor
from trading.risk.models import RiskConfig

config = BacktestConfig(risk_config=RiskConfig(), starting_equity=10_000)
governor = RiskGovernor(config.risk_config, account_equity=10_000)
levels = DayLevels(long_sweep_level=premarket_low, target_levels=[premarket_high, prior_day_high])

trades = run_day("ABCD", session_candles, config, levels, governor)
print(compute_stats(trades))
```

## Example: multi-day

```python
from trading.backtest.data_source import AlpacaHistoricalDataSource
from trading.backtest.models import BacktestConfig
from trading.backtest.orchestrator import run_backtest
from trading.backtest.period_split import generate_weekdays, split_trading_days
from trading.backtest.stats import compute_stats
from trading.data.alpaca_client import AlpacaClient
from trading.risk.models import RiskConfig

data_source = AlpacaHistoricalDataSource(AlpacaClient())
config = BacktestConfig(risk_config=RiskConfig(), starting_equity=10_000)

trading_days = generate_weekdays(start_date, end_date)
split = split_trading_days(trading_days, train_pct=0.6, validate_pct=0.2)

train_result = run_backtest("ABCD", split.train, data_source, config)
print(compute_stats(train_result.trades), "final equity:", train_result.final_equity)

# only after the strategy looks reasonable on train, check it hasn't just
# been curve-fit to that period:
validate_result = run_backtest("ABCD", split.validate, data_source, config)
print(compute_stats(validate_result.trades))
```

## Example: multi-symbol + validation report in one call

```python
from trading.backtest.validation import run_out_of_sample_validation

report = run_out_of_sample_validation(
    symbols=["ABCD", "EFGH", "IJKL"],
    trading_days=trading_days,
    data_source=data_source,
    config=config,
)
print("train:", report.train)
print("validate:", report.validate)
print("test:", report.test)
```
