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

## What it does not do yet

- **Multi-day, multi-symbol orchestration.** This runs one symbol's one day.
  Turning this into a real backtest means fetching historical bars per
  symbol per day from Alpaca (or another historical data source), building
  `DayLevels` for each day (premarket high/low, prior-day high/low, equal
  highs/lows) from real data instead of hand-constructed test fixtures, and
  looping `run_day` across a date range with a `RiskGovernor` that resets at
  each new session.
- **Out-of-sample validation.** Train/validate/test period splits — don't
  trust a result that only holds on the period it was tuned on.
- **Slippage/spread modeling.** Fills currently assume the exact limit
  price. Real small-cap execution is worse than this, especially in thin
  names — see `trading/README.md`'s note on paper vs. live execution.
- **Performance breakdowns** by time-of-day, opening-range window, or
  stock characteristics (price/float/market-cap buckets) — `compute_stats`
  is currently a single aggregate over whatever trade list you pass it;
  slicing trades by attribute before calling it gets you the breakdown.

## Example

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
