"""Technical analyst - computes RSI, MACD, SMA crossover, and Bollinger Bands.

Returns a score from 0.0 (strong sell) to 1.0 (strong buy).
Uses yfinance for price history and pandas_ta for indicator math.
"""

import logging

import pandas as pd
import pandas_ta as ta
import yfinance as yf

logger = logging.getLogger(__name__)

# Suppress yfinance noise
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


class TechnicalAnalyst:

    def analyze(self, symbol: str) -> float:
        """Return technical score 0.0–1.0 for symbol."""
        df = self._get_ohlcv(symbol)
        if df is None or len(df) < 50:
            logger.debug(f"Not enough price history for {symbol} – using neutral score.")
            return 0.5
        return self._compute_score(df)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_ohlcv(self, symbol: str) -> pd.DataFrame | None:
        try:
            df = yf.Ticker(symbol).history(period="3mo", interval="1d")
            return df if not df.empty else None
        except Exception as exc:
            logger.warning(f"Price history fetch failed for {symbol}: {exc}")
            return None

    def _compute_score(self, df: pd.DataFrame) -> float:
        close = df["Close"]
        signals: list[float] = []

        # RSI (14-period): oversold < 30 is bullish, overbought > 70 is bearish
        rsi_series = ta.rsi(close, length=14)
        if rsi_series is not None and not rsi_series.empty:
            rsi = rsi_series.iloc[-1]
            if rsi < 30:
                signals.append(1.0)
            elif rsi < 50:
                signals.append(0.65)
            elif rsi < 70:
                signals.append(0.35)
            else:
                signals.append(0.0)

        # MACD crossover: MACD line above signal line is bullish
        macd_df = ta.macd(close)
        if macd_df is not None and not macd_df.empty:
            macd_val = macd_df["MACD_12_26_9"].iloc[-1]
            signal_val = macd_df["MACDs_12_26_9"].iloc[-1]
            signals.append(1.0 if macd_val > signal_val else 0.0)

        # SMA crossover: 20-day above 50-day is golden-cross territory
        sma20 = ta.sma(close, length=20)
        sma50 = ta.sma(close, length=50)
        if sma20 is not None and sma50 is not None:
            signals.append(0.8 if sma20.iloc[-1] > sma50.iloc[-1] else 0.2)

        # Bollinger Bands: price near lower band signals a potential bounce
        bbands = ta.bbands(close, length=20)
        if bbands is not None and not bbands.empty:
            lower = bbands["BBL_20_2.0"].iloc[-1]
            upper = bbands["BBU_20_2.0"].iloc[-1]
            price = close.iloc[-1]
            band_range = upper - lower
            if band_range > 0:
                # 0 = at upper band (overbought), 1 = at lower band (oversold)
                position = (price - lower) / band_range
                signals.append(1.0 - position)

        return sum(signals) / len(signals) if signals else 0.5
