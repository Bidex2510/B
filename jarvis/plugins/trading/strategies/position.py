"""Position trading strategy.

Long-term, fundamentals-first. Requires a confirmed golden cross (50-day SMA
above 200-day SMA), solid fundamentals, and non-negative sentiment.

Typical hold: 1-6 months.
Exits only on death cross (50 below 200) or when fundamentals deteriorate.
"""

import pandas as pd
import pandas_ta as ta

from jarvis.plugins.trading.strategies.base import Strategy, TF_1D


class PositionStrategy(Strategy):
    name = "position"
    bar_interval = TF_1D
    bar_period = "2y"
    target_hold_days = 90.0
    min_score_to_buy = 0.70

    def score(self, symbol, df, sentiment, fundamental_score):
        close = df["Close"]
        signals: list[float] = []

        # Fundamentals carry double weight for position trades
        signals.append(fundamental_score)
        signals.append(fundamental_score)

        sma50 = ta.sma(close, length=50)
        long_len = 200 if len(close) >= 200 else 100
        sma_long = ta.sma(close, length=long_len)
        if sma50 is not None and sma_long is not None:
            s50 = sma50.iloc[-1]
            slong = sma_long.iloc[-1]
            if pd.notna(s50) and pd.notna(slong):
                ratio = s50 / slong
                if ratio > 1.05:
                    signals.append(1.0)
                elif ratio > 1.0:
                    signals.append(0.75)
                elif ratio > 0.98:
                    signals.append(0.35)
                else:
                    signals.append(0.10)

        # Sentiment - dampened; we care less about news on multi-month holds
        norm_sent = (sentiment + 1.0) / 2.0
        signals.append(0.5 + (norm_sent - 0.5) * 0.5)

        return sum(signals) / len(signals) if signals else 0.5

    def should_exit(self, symbol, df, entry_price, age_minutes):
        close = df["Close"]

        sma50 = ta.sma(close, length=50)
        long_len = 200 if len(close) >= 200 else 100
        sma_long = ta.sma(close, length=long_len)

        if sma50 is not None and sma_long is not None:
            s50 = sma50.iloc[-1]
            slong = sma_long.iloc[-1]
            if pd.notna(s50) and pd.notna(slong) and s50 < slong * 0.98:
                return True, f"position: death cross (SMA50 below SMA{long_len})"

        return False, ""
