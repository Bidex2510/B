"""Day trading strategy.

Intraday only - every position is force-closed before market close.
Uses 5-minute bars and looks for Opening Range Breakouts above VWAP
with volume confirmation.

Typical hold: 30 minutes to a few hours.
Exits: +2% profit, -1% stop, or 15 minutes before market close.

WARNING: Robinhood enforces the Pattern Day Trader (PDT) rule for accounts
under $25,000 - more than 3 day trades in 5 rolling business days will
restrict your account. The RiskManager tracks and blocks these.
"""

import pandas as pd
from ta.momentum import RSIIndicator

from jarvis.plugins.trading.strategies.base import Strategy, TF_5M


class DayStrategy(Strategy):
    name = "day"
    bar_interval = TF_5M
    bar_period = "5d"
    target_hold_days = 0.25
    min_score_to_buy = 0.72
    intraday = True

    def score(self, symbol, df, sentiment, fundamental_score):
        if len(df) < 20:
            return 0.3

        close = df["Close"]
        volume = df["Volume"]
        signals: list[float] = []

        try:
            today_mask = df.index.date == df.index[-1].date()
            session = df[today_mask]
            if len(session) < 3:
                session = df.tail(40)
        except Exception:
            session = df.tail(40)

        try:
            tp = (session["High"] + session["Low"] + session["Close"]) / 3.0
            vwap = (tp * session["Volume"]).cumsum() / session["Volume"].cumsum()
            price = close.iloc[-1]
            vwap_last = vwap.iloc[-1]
            if pd.notna(vwap_last) and vwap_last > 0:
                ratio = price / vwap_last
                if ratio > 1.01:
                    signals.append(1.0)
                elif ratio > 1.0:
                    signals.append(0.75)
                elif ratio > 0.99:
                    signals.append(0.45)
                else:
                    signals.append(0.15)
        except Exception:
            pass

        try:
            if len(session) >= 8:
                or_high = session.iloc[:6]["High"].max()
                price = close.iloc[-1]
                if price > or_high:
                    signals.append(1.0)
                elif price > or_high * 0.998:
                    signals.append(0.6)
                else:
                    signals.append(0.3)
        except Exception:
            pass

        try:
            avg_vol = volume.rolling(20).mean().iloc[-1]
            if pd.notna(avg_vol) and avg_vol > 0:
                vol_ratio = volume.iloc[-1] / avg_vol
                if vol_ratio > 2.0:
                    signals.append(1.0)
                elif vol_ratio > 1.3:
                    signals.append(0.75)
                else:
                    signals.append(0.35)
        except Exception:
            pass

        norm_sent = (sentiment + 1.0) / 2.0
        signals.append(norm_sent)

        return sum(signals) / len(signals) if signals else 0.5

    def should_exit(self, symbol, df, entry_price, age_minutes):
        price = df["Close"].iloc[-1]
        pnl = (price - entry_price) / entry_price

        if pnl >= 0.02:
            return True, f"day: +2% profit target ({pnl:.1%})"
        if pnl <= -0.01:
            return True, f"day: -1% stop triggered ({pnl:.1%})"
        if age_minutes > 300:
            return True, "day: max hold time reached"
        return False, ""
