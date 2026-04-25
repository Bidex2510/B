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
from ta.trend import EMAIndicator, MACD

from jarvis.plugins.trading.strategies.base import Strategy, TF_1M


class ScalpStrategy(Strategy):
    name = "scalp"
    bar_interval = TF_1M
    bar_period = "1d"
    target_hold_days = 0.02
    min_score_to_buy = 0.58  # lowered for more frequent entries
    intraday = True

    def score(self, symbol, df, sentiment, fundamental_score):
        if len(df) < 30:
            return 0.3

        close = df["Close"]
        volume = df["Volume"]
        signals: list[float] = []

        try:
            ema9 = EMAIndicator(close=close, window=9).ema_indicator()
            ema20 = EMAIndicator(close=close, window=20).ema_indicator()
            e9 = ema9.iloc[-1]
            e20 = ema20.iloc[-1]
            e20_prev = ema20.iloc[-2]
            if pd.notna(e9) and pd.notna(e20):
                if e9 > e20 and pd.notna(e20_prev) and e20 > e20_prev:
                    signals.append(1.0)
                elif e9 > e20:
                    signals.append(0.7)
                else:
                    signals.append(0.15)

            if pd.notna(e9) and close.iloc[-1] > e9 * 1.001:
                signals.append(1.0)
            elif pd.notna(e9) and close.iloc[-1] > e9:
                signals.append(0.7)
            else:
                signals.append(0.2)
        except Exception:
            pass

        try:
            macd = MACD(close=close, window_slow=13, window_fast=5, window_sign=3)
            h = macd.macd_diff()
            if len(h) > 1 and pd.notna(h.iloc[-1]) and pd.notna(h.iloc[-2]):
                if h.iloc[-1] > 0 and h.iloc[-1] > h.iloc[-2]:
                    signals.append(1.0)
                elif h.iloc[-1] > 0:
                    signals.append(0.6)
                else:
                    signals.append(0.2)
        except Exception:
            pass

        try:
            avg_vol = volume.rolling(20).mean().iloc[-1]
            if pd.notna(avg_vol) and avg_vol > 0:
                ratio = volume.iloc[-1] / avg_vol
                signals.append(min(1.0, ratio / 2.0))
        except Exception:
            pass

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
