"""Swing trading strategy.

Looks for pullbacks inside an established uptrend: RSI oversold
and price near the lower Bollinger Band, but still above the 50-day SMA.

Typical hold: 3-10 trading days.
Exits on RSI > 70 (overbought), 10-day hold limit, or 8% profit target.
"""

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from ta.volatility import BollingerBands

from jarvis.plugins.trading.strategies.base import Strategy, TF_1D


class SwingStrategy(Strategy):
    name = "swing"
    bar_interval = TF_1D
    bar_period = "6mo"
    target_hold_days = 7.0
    min_score_to_buy = 0.70

    def score(self, symbol, df, sentiment, fundamental_score):
        close = df["Close"]
        signals: list[float] = []

        try:
            rsi = RSIIndicator(close=close, window=14).rsi()
            r = rsi.iloc[-1]
            if pd.notna(r):
                if r < 30:
                    signals.append(1.0)
                elif r < 40:
                    signals.append(0.75)
                elif r < 55:
                    signals.append(0.45)
                else:
                    signals.append(0.15)
        except Exception:
            pass

        try:
            bb = BollingerBands(close=close, window=20, window_dev=2)
            lower = bb.bollinger_lband().iloc[-1]
            upper = bb.bollinger_hband().iloc[-1]
            price = close.iloc[-1]
            if pd.notna(lower) and pd.notna(upper) and upper > lower:
                pos = (price - lower) / (upper - lower)
                signals.append(max(0.0, 1.0 - pos))
        except Exception:
            pass

        try:
            sma50 = SMAIndicator(close=close, window=50).sma_indicator()
            if pd.notna(sma50.iloc[-1]):
                signals.append(1.0 if close.iloc[-1] > sma50.iloc[-1] else 0.15)
        except Exception:
            pass

        norm_sent = (sentiment + 1.0) / 2.0
        signals.append(norm_sent * 0.5 + 0.25)

        return sum(signals) / len(signals) if signals else 0.5

    def should_exit(self, symbol, df, entry_price, age_minutes):
        close = df["Close"]
        price = close.iloc[-1]
        age_days = age_minutes / (60 * 24)

        if (price - entry_price) / entry_price >= 0.08:
            return True, "swing: +8% profit target hit"

        try:
            rsi = RSIIndicator(close=close, window=14).rsi().iloc[-1]
            if pd.notna(rsi) and rsi > 70:
                return True, f"swing: RSI overbought ({rsi:.0f})"
        except Exception:
            pass

        if age_days >= 10:
            return True, f"swing: max hold period reached ({age_days:.1f} days)"

        return False, ""
