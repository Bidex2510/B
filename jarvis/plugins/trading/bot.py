"""Main trading bot orchestrator.

Runs a background thread that wakes up every SCAN_INTERVAL_SECONDS during
NYSE market hours (9:30–16:00 ET, Mon–Fri) and executes the full research-
and-trade cycle:

  1. Circuit-breaker check (daily loss limit, kill switch, trade cap)
  2. Review open positions → exit any that hit stop-loss or trailing stop
  3. Scan watchlist → score each stock across sentiment/technical/fundamental
  4. Execute BUY orders for the top-2 highest-scoring candidates

Paper trading is the default (set PAPER_TRADING=false to go live).
"""

import logging
import os
import threading
from datetime import datetime, time as dtime

import pytz

from jarvis.plugins.trading.analysts.fundamental import FundamentalAnalyst
from jarvis.plugins.trading.analysts.sentiment import SentimentAnalyst
from jarvis.plugins.trading.analysts.technical import TechnicalAnalyst
from jarvis.plugins.trading.engine import DecisionEngine
from jarvis.plugins.trading.notifier import Notifier
from jarvis.plugins.trading.risk_manager import RiskManager
from jarvis.plugins.trading.robinhood_client import RobinhoodClient
from jarvis.plugins.trading.scanner import StockScanner

logger = logging.getLogger(__name__)

MARKET_OPEN = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)
ET = pytz.timezone("America/New_York")
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "300"))  # 5 min default
MAX_CANDIDATES_PER_CYCLE = int(os.getenv("MAX_CANDIDATES_PER_CYCLE", "15"))
MAX_BUYS_PER_CYCLE = int(os.getenv("MAX_BUYS_PER_CYCLE", "2"))


class TradingBot:
    """Self-contained AI trading bot that runs in a daemon thread."""

    def __init__(self):
        paper = os.getenv("PAPER_TRADING", "true").lower() != "false"
        self._client = RobinhoodClient(paper_trading=paper)
        self._sentiment = SentimentAnalyst()
        self._technical = TechnicalAnalyst()
        self._fundamental = FundamentalAnalyst()
        self._engine = DecisionEngine()
        self._risk = RiskManager()
        self._scanner = StockScanner()
        self._notifier = Notifier()

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Public control interface
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paper_trading(self) -> bool:
        return self._client.paper_trading

    def start(self) -> str:
        if self._running:
            return "Bot is already running."
        self._stop_event.clear()
        try:
            self._client.login()
        except Exception as exc:
            return f"Login failed: {exc}"

        portfolio_value = self._client.get_portfolio_value()
        self._risk.set_session_value(portfolio_value)

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._running = True

        mode = "PAPER" if self._client.paper_trading else "LIVE"
        msg = (
            f"Trading bot started in {mode} mode.\n"
            f"Portfolio: ${portfolio_value:,.2f}\n"
            f"Scan interval: every {SCAN_INTERVAL_SECONDS // 60} minutes during market hours."
        )
        self._notifier.info(f"[BOT STARTED] {mode} mode | Portfolio ${portfolio_value:,.2f}")
        return msg

    def stop(self) -> str:
        if not self._running:
            return "Bot is not running."
        self._stop_event.set()
        self._running = False
        self._client.logout()
        self._notifier.info("[BOT STOPPED]")
        return "Trading bot stopped."

    def freeze(self) -> str:
        self._risk.freeze()
        self._notifier.info("[KILL SWITCH] Bot manually frozen.")
        return "Bot frozen – no new trades will be placed. Say 'unfreeze bot' to resume."

    def unfreeze(self) -> str:
        self._risk.unfreeze()
        self._notifier.info("[KILL SWITCH] Bot unfrozen and resuming.")
        return "Bot unfrozen – resuming normal operation."

    def get_status(self) -> str:
        if not self._running:
            return "Bot is stopped. Say 'start trading' to begin."

        try:
            portfolio_value = self._client.get_portfolio_value()
            buying_power = self._client.get_buying_power()
            positions = self._client.get_positions()
        except Exception as exc:
            return f"Could not fetch status: {exc}"

        mode = "PAPER" if self._client.paper_trading else "LIVE"
        frozen_tag = " [FROZEN]" if self._risk.is_frozen else ""
        stats = self._risk.get_stats()

        lines = [
            f"Status : RUNNING ({mode}){frozen_tag}",
            f"Portfolio : ${portfolio_value:,.2f}",
            f"Buying power: ${buying_power:,.2f}",
            f"Open positions: {len(positions)}",
            f"Trades today: {stats['daily_trades']} / {stats['max_daily_trades']}",
        ]

        for symbol, pos in positions.items():
            current = self._client.get_current_price(symbol) or pos["average_buy_price"]
            pnl_pct = (current - pos["average_buy_price"]) / pos["average_buy_price"] * 100
            sign = "+" if pnl_pct >= 0 else ""
            lines.append(
                f"  {symbol}: {pos['quantity']:.0f} sh @ ${pos['average_buy_price']:.2f}"
                f" | now ${current:.2f} ({sign}{pnl_pct:.1f}%)"
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        logger.info("Trading bot loop started.")
        while not self._stop_event.is_set():
            try:
                if self._is_market_open():
                    self._trading_cycle()
                else:
                    logger.debug("Market is closed – standing by.")
            except Exception as exc:
                logger.error(f"Unhandled error in trading cycle: {exc}", exc_info=True)
                self._notifier.error_alert(str(exc))

            self._stop_event.wait(timeout=SCAN_INTERVAL_SECONDS)

        logger.info("Trading bot loop ended.")

    # ------------------------------------------------------------------
    # Core trading cycle
    # ------------------------------------------------------------------

    def _trading_cycle(self) -> None:
        portfolio_value = self._client.get_portfolio_value()

        if self._risk.check_circuit_breaker(portfolio_value):
            if self._risk.is_frozen:
                self._notifier.circuit_breaker_alert()
            logger.warning("Circuit breaker active – skipping this cycle.")
            return

        self._check_stop_losses()
        self._scan_and_buy(portfolio_value)

    def _check_stop_losses(self) -> None:
        positions = self._client.get_positions()
        for symbol, pos in positions.items():
            price = self._client.get_current_price(symbol)
            if price is None:
                continue

            if self._risk.should_stop_loss(symbol, price, pos["average_buy_price"]):
                shares = int(pos["quantity"])
                # Use a small discount on the limit so the order fills quickly
                limit = round(price * 0.99, 2)
                result = self._client.sell(symbol, shares, limit)

                if "error" not in result:
                    self._risk.record_trade()
                    self._risk.clear_position_peak(symbol)
                    self._notifier.trade_alert(
                        "SELL", symbol, shares, price, 0.0,
                        self._client.paper_trading,
                    )
                    logger.info(f"Stop-loss exit: sold {shares} {symbol} @ ${price:.2f}")
                else:
                    logger.error(f"Stop-loss sell failed for {symbol}: {result.get('error')}")

    def _scan_and_buy(self, portfolio_value: float) -> None:
        watchlist = self._scanner.get_watchlist()
        held_symbols = set(self._client.get_positions().keys())
        candidates = [s for s in watchlist if s not in held_symbols]

        # Analyze up to MAX_CANDIDATES_PER_CYCLE symbols per cycle to preserve API quota
        scored: list[tuple[float, object]] = []

        for symbol in candidates[:MAX_CANDIDATES_PER_CYCLE]:
            try:
                company = self._scanner.get_company_name(symbol)
                sent = self._sentiment.analyze(symbol, company)
                tech = self._technical.analyze(symbol)
                fund = self._fundamental.analyze(symbol)
                signal = self._engine.decide(symbol, sent, tech, fund)
                logger.debug(
                    f"{symbol}: sent={sent:+.2f} tech={tech:.2f} "
                    f"fund={fund:.2f} → {signal.action} ({signal.total_score:.0%})"
                )
                if signal.action == "BUY":
                    scored.append((signal.total_score, signal))
            except Exception as exc:
                logger.warning(f"Analysis failed for {symbol}: {exc}")

        # Take the top N by score
        scored.sort(key=lambda x: x[0], reverse=True)
        for _, signal in scored[:MAX_BUYS_PER_CYCLE]:
            self._execute_buy(signal, portfolio_value)

    def _execute_buy(self, signal, portfolio_value: float) -> None:
        price = self._client.get_current_price(signal.symbol)
        if price is None:
            logger.warning(f"No price for {signal.symbol} – skipping buy.")
            return

        buying_power = self._client.get_buying_power()
        shares = self._risk.position_size(portfolio_value, price)

        if shares * price > buying_power:
            logger.info(
                f"Insufficient buying power for {signal.symbol}: "
                f"need ${shares * price:,.2f}, have ${buying_power:,.2f}"
            )
            return

        # Offer a 0.5% premium above market to improve limit-fill probability
        limit = round(price * 1.005, 2)
        result = self._client.buy(signal.symbol, shares, limit)

        if "error" not in result:
            self._risk.record_trade()
            self._notifier.trade_alert(
                "BUY", signal.symbol, shares, price,
                signal.total_score, self._client.paper_trading,
            )
            logger.info(
                f"Bought {shares} {signal.symbol} @ ${price:.2f} "
                f"(score={signal.total_score:.0%}, {signal.reason})"
            )
        else:
            logger.error(f"Buy order failed for {signal.symbol}: {result.get('error')}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_market_open() -> bool:
        now = datetime.now(ET)
        if now.weekday() >= 5:   # Saturday=5, Sunday=6
            return False
        t = now.time()
        return MARKET_OPEN <= t <= MARKET_CLOSE
