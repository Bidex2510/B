"""Scalping strategy.

Very short-term momentum trading on 1-minute bars. Looks for short bursts
of upward momentum with volume confirmation (price above fast EMA,
MACD histogram turning positive).

Typical hold: 2-20 minutes.
Exits: +0.5% profit, -0.3% stop, or 30-minute hold max.

WARNING: The PDT rule applies. Scalping generates many day trades - the
RiskManager's daily-trade counter will throttle it. Also, the bot's scan
interval (default 60s) is much slower than a real scalper's - do not
expect tick-by-tick execution.
"""

import pandas as pd
import pandas_ta as ta

from jarvis.plugins.trading.strategies.base import Strategy, TF_1M


class ScalpStrategy(Strategy):
    name = "scalp"
    bar_interval = TF_1M
    bar_period = "1d"
    target_hold_days = 0.02   # ~30 minutes
    min_score_to_buy = 0.75
    intraday = True

    def score(self, symbol, df, sentiment, fundamental_score):
        if len(df) < 30:
            return 0.3

        close = df["Close"]
        volume = df["Volume"]
        signals: list[float] = []

        # EMA9 vs EMA20 - momentum direction on a fast timeframe
        ema9 = ta.ema(close, length=9)
        ema20 = ta.ema(close, length=20)
        if ema9 is not None and ema20 is not None:
            if ema9.iloc[-1] > ema20.iloc[-1] > ema20.iloc[-2]:
                signals.append(1.0)
            elif ema9.iloc[-1] > ema20.iloc[-1]:
                signals.append(0.7)
            else:
                signals.append(0.15)

        # Price above EMA9 = short-term strength
        if ema9 is not None and pd.notna(ema9.iloc[-1]):
            if close.iloc[-1] > ema9.iloc[-1] * 1.001:
                signals.append(1.0)
            elif close.iloc[-1] > ema9.iloc[-1]:
                signals.append(0.7)
            else:
                signals.append(0.2)

        # MACD histogram turning positive
        macd = ta.macd(close, fast=5, slow=13, signal=3)
        if macd is not None and not macd.empty:
            hist_col = [c for c in macd.columns if c.startswith("MACDh")]
            if hist_col:
                h = macd[hist_col[0]]
                if len(h) > 1 and pd.notna(h.iloc[-1]) and pd.notna(h.iloc[-2]):
                    if h.iloc[-1] > 0 and h.iloc[-1] > h.iloc[-2]:
                        signals.append(1.0)
                    elif h.iloc[-1] > 0:
                        signals.append(0.6)
                    else:
                        signals.append(0.2)

        # Volume spike confirmation
        avg_vol = volume.rolling(20).mean().iloc[-1]
        if pd.notna(avg_vol) and avg_vol > 0:
            ratio = volume.iloc[-1] / avg_vol
            signals.append(min(1.0, ratio / 2.0))

        return sum(signals) / len(signals) if signals else 0.5

    def should_exit(self, symbol, df, entry_price, age_minutes):
        price = df["Close"].iloc[-1]
        pnl = (price - entry_price) / entry_price

        if pnl >= 0.005:
            return True, f"scalp: +0.5% target hit ({pnl:.2%})"
        if pnl <= -0.003:
            return True, f"scalp: -0.3% stop hit ({pnl:.2%})"
        if age_minutes > 30:
            return True, "scalp: 30-minute max hold"
        return False, ""
