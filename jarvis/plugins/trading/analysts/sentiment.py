"""Sentiment analyst - uses NewsAPI for headlines and Claude to score them.

Returns a score from -1.0 (very bearish) to +1.0 (very bullish).
Falls back to 0.0 (neutral) when API keys are missing or calls fail.
"""

import os
import json
import logging

import httpx
import anthropic

logger = logging.getLogger(__name__)


class SentimentAnalyst:
    NEWS_URL = "https://newsapi.org/v2/everything"

    def __init__(self):
        self._news_key = os.getenv("NEWS_API_KEY")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self._claude = anthropic.Anthropic(api_key=api_key) if api_key else None

    def analyze(self, symbol: str, company_name: str = "") -> float:
        """Score market sentiment for a symbol. Range: -1.0 to +1.0."""
        headlines = self._fetch_headlines(symbol, company_name)
        if not headlines or not self._claude:
            return 0.0
        return self._score_with_claude(symbol, headlines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_headlines(self, symbol: str, company_name: str) -> list[str]:
        if not self._news_key:
            logger.debug("NEWS_API_KEY not set – skipping sentiment fetch.")
            return []

        query = company_name if company_name else symbol
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": self._news_key,
        }
        try:
            resp = httpx.get(self.NEWS_URL, params=params, timeout=10)
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            return [a["title"] for a in articles if a.get("title")]
        except Exception as exc:
            logger.warning(f"News fetch failed for {symbol}: {exc}")
            return []

    def _score_with_claude(self, symbol: str, headlines: list[str]) -> float:
        headlines_text = "\n".join(f"- {h}" for h in headlines[:10])
        prompt = (
            f"Analyze these recent news headlines about the stock {symbol}.\n"
            f"Return ONLY a JSON object with one key 'score': a float from -1.0 "
            f"(very negative for the stock price) to +1.0 (very positive).\n"
            f"No explanation, just the JSON.\n\n{headlines_text}"
        )
        try:
            message = self._claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=64,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            data = json.loads(raw)
            return max(-1.0, min(1.0, float(data["score"])))
        except Exception as exc:
            logger.warning(f"Claude sentiment scoring failed for {symbol}: {exc}")
            return 0.0
