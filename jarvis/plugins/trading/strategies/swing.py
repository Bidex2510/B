"""Swing trading strategy.

Looks for pullbacks inside an established uptrend: RSI oversold
and price near the lower Bollinger Band, but still above the 50-day SMA.

Typical hold: 3-10 trading days.
Exits on RSI > 70 (overbought), 10-day hold limit, or 8% profit target.
"""

import pandas as pd
import pandas_ta as ta

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

        rsi = ta.rsi(close, length=14)
        if rsi is not None and not rsi.empty:
            r = rsi.iloc[-1]
            if r < 30:
                signals.append(1.0)
            elif r < 40:
                signals.append(0.75)
            elif r < 55:
                signals.append(0.45)
            else:
                signals.append(0.15)

        bb = ta.bbands(close, length=20)
        if bb is not None and not bb.empty:
            lower = bb["BBL_20_2.0"].iloc[-1]
            upper = bb["BBU_20_2.0"].iloc[-1]
            price = close.iloc[-1]
            if upper > lower:
                pos = (price - lower) / (upper - lower)
                signals.append(max(0.0, 1.0 - pos))

        sma50 = ta.sma(close, length=50)
        if sma50 is not None and not sma50.dropna().empty:
            signals.append(1.0 if close.iloc[-1] > sma50.iloc[-1] else 0.15)

        norm_sent = (sentiment + 1.0) / 2.0
        signals.append(norm_sent * 0.5 + 0.25)

        return sum(signals) / len(signals) if signals else 0.5

    def should_exit(self, symbol, df, entry_price, age_minutes):
        close = df["Close"]
        price = close.iloc[-1]
        age_days = age_minutes / (60 * 24)

        if (price - entry_price) / entry_price >= 0.08:
            return True, "swing: +8% profit target hit"

        rsi = ta.rsi(close, length=14)
        if rsi is not None and not rsi.empty and rsi.iloc[-1] > 70:
            return True, f"swing: RSI overbought ({rsi.iloc[-1]:.0f})"

        if age_days >= 10:
            return True, f"swing: max hold period reached ({age_days:.1f} days)"

        return False, ""
