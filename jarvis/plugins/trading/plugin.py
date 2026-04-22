"""Jarvis plugin - exposes the Robinhood AI trading bot via natural language.

Recognised commands (case-insensitive):
  "start trading"        – launch the bot (all six strategies active by default)
  "stop trading"         – gracefully stop the bot
  "portfolio status"     – show positions, P&L, buying power, active strategies
  "freeze bot"           – emergency kill switch (no new trades)
  "unfreeze bot"         – resume after freeze
  "list strategies"      – show which strategies are currently active
  "trading help"         – show this command list
"""

import re

from jarvis.core.plugin_base import PluginBase
from jarvis.plugins.trading.bot import TradingBot


class TradingBotPlugin(PluginBase):

    name = "trading_bot"
    description = (
        "Robinhood AI trading bot – six strategies (swing, position, trend, "
        "breakout, day, scalp) trading stocks and ETFs. Paper trading by default."
    )

    TRIGGERS = [
        r"\b(trade|trading|bot|robinhood|stock|etf|invest|portfolio)\b",
        r"\b(buy|sell|position|holding|equity|balance)\b",
        r"\b(freeze|unfreeze|kill switch)\b",
        r"\b(swing|scalp|day trade|breakout|trend|position trade)\b",
        r"\b(strateg(y|ies))\b",
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

        if re.search(r"\b(list|show|active)\b.*\bstrateg", lower) or re.search(r"\bstrateg(y|ies)\b", lower):
            return (
                "Active strategies: " + ", ".join(self._bot.active_strategies) + "\n"
                "Disable any with env var STRATEGY_<NAME>=false "
                "(e.g. STRATEGY_SCALP=false to turn off scalping)."
            )

        if re.search(
            r"\bstatus\b|\bportfolio\b|\bholding\b|\bposition\b|\bbalance\b|\bequity\b",
            lower,
        ):
            return self._bot.get_status()

        return self._help_text()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _help_text(self) -> str:
        mode = (
            "PAPER (safe mode - no real money)"
            if self._bot.is_paper_trading else "LIVE"
        )
        status = "RUNNING" if self._bot.is_running else "STOPPED"
        strategies = ", ".join(self._bot.active_strategies)
        return (
            f"Trading Bot - {status} | Mode: {mode}\n"
            f"Strategies: {strategies}\n\n"
            "Commands:\n"
            "  'start trading'     - Launch the AI bot\n"
            "  'stop trading'      - Shut the bot down\n"
            "  'portfolio status'  - View positions, strategies & P&L\n"
            "  'list strategies'   - Show active strategies\n"
            "  'freeze bot'        - Emergency kill switch\n"
            "  'unfreeze bot'      - Resume after freeze\n\n"
            "Six strategies run together out of the box:\n"
            "  swing    : 3-10 day pullback trades\n"
            "  position : 1-6 month fundamentals plays\n"
            "  trend    : 2-6 week momentum trades\n"
            "  breakout : 1-3 week new-high breakouts\n"
            "  day      : intraday, force-closed before 15:45 ET\n"
            "  scalp    : 1-30 minute 1-min-bar momentum bursts\n\n"
            "Default watchlist covers 20 mega-cap stocks + 25 major ETFs.\n"
            "Set PAPER_TRADING=false in .env to trade real money (use with caution)."
        )
