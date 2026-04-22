"""Telegram notification bot - sends trade alerts and error messages.

Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env to enable.
If keys are missing the notifier silently does nothing (no crash).

How to get your chat ID:
  1. Message @userinfobot on Telegram
  2. It replies with your numeric chat ID
"""

import os
import logging

import httpx

logger = logging.getLogger(__name__)


class Notifier:

    def __init__(self):
        self._token = os.getenv("TELEGRAM_BOT_TOKEN")
        self._chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self._enabled = bool(self._token and self._chat_id)
        if not self._enabled:
            logger.info("Telegram notifier disabled (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set).")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def trade_alert(
        self,
        action: str,
        symbol: str,
        shares: int,
        price: float,
        score: float,
        paper: bool,
    ) -> None:
        mode = "[PAPER]" if paper else "[LIVE]"
        icon = "BUY" if action == "BUY" else "SELL"
        msg = (
            f"{mode} {icon}\n"
            f"Stock : {symbol}\n"
            f"Action: {action}\n"
            f"Shares: {shares:,}\n"
            f"Price : ${price:,.2f}\n"
            f"Score : {score:.0%}\n"
            f"Value : ${shares * price:,.2f}"
        )
        self.send(msg)

    def circuit_breaker_alert(self) -> None:
        self.send(
            "[ALERT] Circuit breaker triggered!\n"
            "Bot is FROZEN. Log in to Robinhood and review your portfolio."
        )

    def error_alert(self, error: str) -> None:
        self.send(f"[BOT ERROR]\n{error}")

    def info(self, message: str) -> None:
        self.send(message)

    def send(self, message: str) -> None:
        if not self._enabled:
            return
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        try:
            httpx.post(
                url,
                json={"chat_id": self._chat_id, "text": message},
                timeout=5,
            )
        except Exception as exc:
            logger.warning(f"Telegram send failed: {exc}")
