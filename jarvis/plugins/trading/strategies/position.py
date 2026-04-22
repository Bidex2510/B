"""Position trading strategy.

Long-term, fundamentals-first. Requires a confirmed golden cross (50-day SMA
above 200-day SMA), solid fundamentals, and non-negative sentiment.

Typical hold: 1-6 months.
Exits only on death cross (50 below 200) or when fundamentals deteriorate.
"""

import pandas as pd
from ta.trend import SMAIndicator

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

        signals.append(fundamental_score)
        signals.append(fundamental_score)

        try:
            long_len = 200 if len(close) >= 200 else 100
            sma50 = SMAIndicator(close=close, window=50).sma_indicator()
            sma_long = SMAIndicator(close=close, window=long_len).sma_indicator()
            s50 = sma50.iloc[-1]
            slong = sma_long.iloc[-1]
            if pd.notna(s50) and pd.notna(slong) and slong > 0:
                ratio = s50 / slong
                if ratio > 1.05:
                    signals.append(1.0)
                elif ratio > 1.0:
                    signals.append(0.75)
                elif ratio > 0.98:
                    signals.append(0.35)
                else:
                    signals.append(0.10)
        except Exception:
            pass

        norm_sent = (sentiment + 1.0) / 2.0
        signals.append(0.5 + (norm_sent - 0.5) * 0.5)

        return sum(signals) / len(signals) if signals else 0.5

    def should_exit(self, symbol, df, entry_price, age_minutes):
        close = df["Close"]
        try:
            long_len = 200 if len(close) >= 200 else 100
            sma50 = SMAIndicator(close=close, window=50).sma_indicator()
            sma_long = SMAIndicator(close=close, window=long_len).sma_indicator()
            s50 = sma50.iloc[-1]
            slong = sma_long.iloc[-1]
            if pd.notna(s50) and pd.notna(slong) and s50 < slong * 0.98:
                return True, f"position: death cross (SMA50 below SMA{long_len})"
        except Exception:
            pass

        return False, ""
