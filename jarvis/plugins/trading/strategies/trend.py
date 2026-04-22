"""Trend-following strategy.

Buys established momentum: MACD bullish, price above 50-day SMA, and
ADX > 25 (confirming a strong trend rather than a choppy range).

Typical hold: 2-6 weeks.
Exits on MACD bearish crossover or price falling meaningfully below the SMA.
"""

import pandas as pd
from ta.trend import MACD, ADXIndicator, SMAIndicator

from jarvis.plugins.trading.strategies.base import Strategy, TF_1D


class TrendStrategy(Strategy):
    name = "trend"
    bar_interval = TF_1D
    bar_period = "6mo"
    target_hold_days = 21.0
    min_score_to_buy = 0.70

    def score(self, symbol, df, sentiment, fundamental_score):
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        signals: list[float] = []

        try:
            macd = MACD(close=close)
            m = macd.macd().iloc[-1]
            s = macd.macd_signal().iloc[-1]
            h = macd.macd_diff().iloc[-1]
            if pd.notna(m) and pd.notna(s):
                if m > s and pd.notna(h) and h > 0:
                    signals.append(1.0)
                elif m > s:
                    signals.append(0.7)
                else:
                    signals.append(0.15)
        except Exception:
            pass

        try:
            sma50 = SMAIndicator(close=close, window=50).sma_indicator()
            s50 = sma50.iloc[-1]
            price = close.iloc[-1]
            if pd.notna(s50) and s50 > 0:
                if price > s50 * 1.03:
                    signals.append(1.0)
                elif price > s50:
                    signals.append(0.7)
                else:
                    signals.append(0.15)
        except Exception:
            pass

        try:
            adx = ADXIndicator(high=high, low=low, close=close, window=14).adx()
            adx_val = adx.iloc[-1]
            if pd.notna(adx_val):
                if adx_val > 30:
                    signals.append(1.0)
                elif adx_val > 25:
                    signals.append(0.8)
                elif adx_val > 20:
                    signals.append(0.5)
                else:
                    signals.append(0.2)
        except Exception:
            pass

        norm_sent = (sentiment + 1.0) / 2.0
        signals.append(0.5 + (norm_sent - 0.5) * 0.6)

        return sum(signals) / len(signals) if signals else 0.5

    def should_exit(self, symbol, df, entry_price, age_minutes):
        close = df["Close"]

        try:
            macd = MACD(close=close)
            m = macd.macd().iloc[-1]
            s = macd.macd_signal().iloc[-1]
            if pd.notna(m) and pd.notna(s) and m < s:
                return True, "trend: MACD bearish crossover"
        except Exception:
            pass

        try:
            sma50 = SMAIndicator(close=close, window=50).sma_indicator()
            s50 = sma50.iloc[-1]
            if pd.notna(s50) and close.iloc[-1] < s50 * 0.97:
                return True, "trend: price broke below 50-SMA"
        except Exception:
            pass

        return False, ""
