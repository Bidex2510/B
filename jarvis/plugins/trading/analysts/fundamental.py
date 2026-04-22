"""Fundamental analyst - evaluates company health using yfinance data.

Checks P/E ratio, revenue growth, profit margins, and debt-to-equity.
Returns a score from 0.0 (poor fundamentals) to 1.0 (excellent fundamentals).
"""

import logging

import yfinance as yf

logger = logging.getLogger(__name__)


class FundamentalAnalyst:

    def analyze(self, symbol: str) -> float:
        """Return fundamental score 0.0–1.0 for symbol."""
        try:
            info = yf.Ticker(symbol).info
            return self._compute_score(info)
        except Exception as exc:
            logger.warning(f"Fundamental data fetch failed for {symbol}: {exc}")
            return 0.5

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_score(self, info: dict) -> float:
        signals: list[float] = []

        # P/E ratio: lower is cheaper; negative P/E means the company is losing money
        pe = info.get("trailingPE") or info.get("forwardPE")
        if pe and pe > 0:
            if pe < 15:
                signals.append(1.0)
            elif pe < 25:
                signals.append(0.70)
            elif pe < 40:
                signals.append(0.40)
            else:
                signals.append(0.10)

        # Revenue growth YoY
        rev_growth = info.get("revenueGrowth")
        if rev_growth is not None:
            if rev_growth > 0.20:
                signals.append(1.0)
            elif rev_growth > 0.10:
                signals.append(0.70)
            elif rev_growth > 0:
                signals.append(0.50)
            else:
                signals.append(0.20)

        # Net profit margin
        margin = info.get("profitMargins")
        if margin is not None:
            if margin > 0.20:
                signals.append(1.0)
            elif margin > 0.10:
                signals.append(0.70)
            elif margin > 0:
                signals.append(0.40)
            else:
                signals.append(0.10)

        # Debt-to-equity: lower means less financial risk
        dte = info.get("debtToEquity")
        if dte is not None:
            if dte < 50:         # <0.5 in decimal form
                signals.append(1.0)
            elif dte < 100:
                signals.append(0.70)
            elif dte < 200:
                signals.append(0.40)
            else:
                signals.append(0.10)

        return sum(signals) / len(signals) if signals else 0.5
