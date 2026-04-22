"""Trend-following strategy.

Buys established momentum: MACD bullish, price above 50-day SMA, and
ADX > 25 (confirming a strong trend rather than a choppy range).

Typical hold: 2-6 weeks.
Exits on MACD bearish crossover or price falling meaningfully below the SMA.
"""

import pandas as pd
import pandas_ta as ta

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

        macd = ta.macd(close)
        if macd is not None and not macd.empty:
            m = macd["MACD_12_26_9"].iloc[-1]
            s = macd["MACDs_12_26_9"].iloc[-1]
            h = macd["MACDh_12_26_9"].iloc[-1]
            if pd.notna(m) and pd.notna(s):
                if m > s and h > 0:
                    signals.append(1.0)
                elif m > s:
                    signals.append(0.7)
                else:
                    signals.append(0.15)

        sma50 = ta.sma(close, length=50)
        if sma50 is not None and not sma50.dropna().empty:
            price = close.iloc[-1]
            s50 = sma50.iloc[-1]
            if price > s50 * 1.03:
                signals.append(1.0)
            elif price > s50:
                signals.append(0.7)
            else:
                signals.append(0.15)

        adx_df = ta.adx(high, low, close, length=14)
        if adx_df is not None and not adx_df.empty:
            adx = adx_df["ADX_14"].iloc[-1]
            if pd.notna(adx):
                if adx > 30:
                    signals.append(1.0)
                elif adx > 25:
                    signals.append(0.8)
                elif adx > 20:
                    signals.append(0.5)
                else:
                    signals.append(0.2)

        norm_sent = (sentiment + 1.0) / 2.0
        signals.append(0.5 + (norm_sent - 0.5) * 0.6)

        return sum(signals) / len(signals) if signals else 0.5

    def should_exit(self, symbol, df, entry_price, age_minutes):
        close = df["Close"]

        macd = ta.macd(close)
        if macd is not None and not macd.empty:
            m = macd["MACD_12_26_9"].iloc[-1]
            s = macd["MACDs_12_26_9"].iloc[-1]
            if pd.notna(m) and pd.notna(s) and m < s:
                return True, "trend: MACD bearish crossover"

        sma50 = ta.sma(close, length=50)
        if sma50 is not None and not sma50.dropna().empty:
            if close.iloc[-1] < sma50.iloc[-1] * 0.97:
                return True, "trend: price broke below 50-SMA"

        return False, ""
