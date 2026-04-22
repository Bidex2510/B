"""Decision engine - combines analyst scores into a BUY / SELL / HOLD signal.

Scoring weights:
  Sentiment  30%  (news + social mood)
  Technical  40%  (price action is the most immediate signal)
  Fundamental 30% (long-term health)

Thresholds:
  >= 0.70  → BUY
  <= 0.40  → SELL
  else     → HOLD
"""

from dataclasses import dataclass


@dataclass
class TradeSignal:
    symbol: str
    action: str               # "BUY" | "SELL" | "HOLD"
    total_score: float        # 0.0 – 1.0
    sentiment_score: float    # -1.0 – +1.0 (raw)
    technical_score: float    # 0.0 – 1.0
    fundamental_score: float  # 0.0 – 1.0
    reason: str


class DecisionEngine:
    WEIGHTS = {"sentiment": 0.30, "technical": 0.40, "fundamental": 0.30}
    BUY_THRESHOLD = 0.70
    SELL_THRESHOLD = 0.40

    def decide(
        self,
        symbol: str,
        sentiment: float,   # -1.0 to +1.0
        technical: float,   # 0.0 to 1.0
        fundamental: float, # 0.0 to 1.0
    ) -> TradeSignal:
        # Normalize sentiment from [-1, 1] to [0, 1]
        norm_sentiment = (sentiment + 1.0) / 2.0

        total = (
            norm_sentiment * self.WEIGHTS["sentiment"]
            + technical * self.WEIGHTS["technical"]
            + fundamental * self.WEIGHTS["fundamental"]
        )

        if total >= self.BUY_THRESHOLD:
            action = "BUY"
            reason = (
                f"Strong combined signal {total:.0%} "
                f"(sent={sentiment:+.2f}, tech={technical:.2f}, fund={fundamental:.2f})"
            )
        elif total <= self.SELL_THRESHOLD:
            action = "SELL"
            reason = (
                f"Weak combined signal {total:.0%} "
                f"(sent={sentiment:+.2f}, tech={technical:.2f}, fund={fundamental:.2f})"
            )
        else:
            action = "HOLD"
            reason = f"Neutral signal {total:.0%} – waiting for stronger conviction"

        return TradeSignal(
            symbol=symbol,
            action=action,
            total_score=total,
            sentiment_score=sentiment,
            technical_score=technical,
            fundamental_score=fundamental,
            reason=reason,
        )
