"""Jarvis plugin that exposes the Robinhood AI trading bot via natural language.

Recognised commands (case-insensitive):
  "start trading"        – launch the bot in background thread
  "stop trading"         – gracefully stop the bot
  "portfolio status"     – show positions, P&L, buying power
  "freeze bot"           – emergency kill switch (no new trades)
  "unfreeze bot"         – resume after freeze
  "trading help"         – show this command list
"""

import re

from jarvis.core.plugin_base import PluginBase
from jarvis.plugins.trading.bot import TradingBot


class TradingBotPlugin(PluginBase):

    name = "trading_bot"
    description = (
        "Robinhood AI trading bot – autonomous research & trade execution "
        "(paper trading by default, real money only when PAPER_TRADING=false)"
    )

    TRIGGERS = [
        r"\b(trade|trading|bot|robinhood|stock|invest|portfolio)\b",
        r"\b(buy|sell|position|holding|equity|balance)\b",
        r"\b(freeze|unfreeze|kill switch)\b",
        r"\bstart\b.*(bot|trading|invest)\b",
        r"\bstop\b.*(bot|trading|invest)\b",
    ]

    def __init__(self):
        super().__init__()
        self._bot = TradingBot()

    def can_handle(self, text: str) -> bool:
        return any(re.search(t, text, re.IGNORECASE) for t in self.TRIGGERS)

    def handle(self, text: str) -> str:
        lower = text.lower()

        if re.search(r"\bstart\b.*(trade|trading|bot|invest)", lower):
            return self._bot.start()

        if re.search(r"\bstop\b.*(trade|trading|bot|invest)", lower):
            return self._bot.stop()

        if re.search(r"\bfreeze\b|\bkill switch\b|\bemergency stop\b", lower):
            return self._bot.freeze()

        if re.search(r"\bunfreeze\b|\bresume bot\b|\bunpause\b", lower):
            return self._bot.unfreeze()

        if re.search(r"\bstatus\b|\bportfolio\b|\bholding\b|\bposition\b|\bbalance\b|\bequity\b", lower):
            return self._bot.get_status()

        return self._help_text()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _help_text(self) -> str:
        mode = "PAPER (safe mode – no real money)" if self._bot.is_paper_trading else "LIVE"
        status = "RUNNING" if self._bot.is_running else "STOPPED"
        return (
            f"Trading Bot – {status} | Mode: {mode}\n\n"
            "Commands:\n"
            "  'start trading'     – Launch the AI bot\n"
            "  'stop trading'      – Shut the bot down\n"
            "  'portfolio status'  – View positions & P&L\n"
            "  'freeze bot'        – Emergency kill switch\n"
            "  'unfreeze bot'      – Resume after freeze\n\n"
            "The bot runs every 5 minutes during NYSE hours (9:30–16:00 ET).\n"
            "Set PAPER_TRADING=false in .env to trade with real money (use with caution)."
        )
