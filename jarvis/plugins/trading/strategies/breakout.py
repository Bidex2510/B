"""Breakout strategy.

Buys when price breaks through the prior 20-day high with volume confirmation
(>= 1.5x average volume). Captures momentum at the start of new uptrends.

Typical hold: 1-3 weeks.
Exits when price falls back below the breakout level (failed breakout).
"""

import pandas as pd

from jarvis.plugins.trading.strategies.base import Strategy, TF_1D


class BreakoutStrategy(Strategy):
    name = "breakout"
    bar_interval = TF_1D
    bar_period = "6mo"
    target_hold_days = 14.0
    min_score_to_buy = 0.70

    def score(self, symbol, df, sentiment, fundamental_score):
        close = df["Close"]
        volume = df["Volume"]
        if len(close) < 21:
            return 0.3
        signals: list[float] = []

        price = close.iloc[-1]
        prior_high_20 = close.iloc[-21:-1].max()
        high_window = close.rolling(min(252, len(close))).max().iloc[-1]

        if price > prior_high_20 * 1.005:
            signals.append(1.0)
        elif price > prior_high_20:
            signals.append(0.75)
        elif price > prior_high_20 * 0.98:
            signals.append(0.5)
        else:
            signals.append(0.1)

        if high_window > 0:
            proximity = price / high_window
            signals.append(min(1.0, proximity))

        avg_vol = volume.rolling(20).mean().iloc[-1]
        cur_vol = volume.iloc[-1]
        if pd.notna(avg_vol) and avg_vol > 0:
            ratio = cur_vol / avg_vol
            if ratio > 2.0:
                signals.append(1.0)
            elif ratio > 1.5:
                signals.append(0.85)
            elif ratio > 1.0:
                signals.append(0.55)
            else:
                signals.append(0.2)

        norm_sent = (sentiment + 1.0) / 2.0
        signals.append(0.5 + (norm_sent - 0.5) * 0.4)

        return sum(signals) / len(signals) if signals else 0.5

    def should_exit(self, symbol, df, entry_price, age_minutes):
        close = df["Close"]
        price = close.iloc[-1]

        # If price falls back below entry by 3%, the breakout failed
        if (price - entry_price) / entry_price < -0.03:
            return True, "breakout: failed, price retraced 3% below entry"

        # Locks in profit at 10%+
        if (price - entry_price) / entry_price >= 0.10:
            return True, "breakout: +10% profit target reached"

        return False, ""
