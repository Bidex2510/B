"""Main trading bot orchestrator.

On start() the bot immediately runs six strategies in parallel:
  - swing      (3-10 day pullback trades)
  - position   (1-6 month fundamentals-driven)
  - trend      (2-6 week momentum following)
  - breakout   (1-3 week new-high breakouts)
  - day        (intraday, exits before close, 1.25x score bias)
  - scalp      (1-30 min momentum bursts on 1-min bars, 1.25x score bias)

Multi-strategy consensus: when 2+ strategies agree on the same symbol,
share quantity is boosted (+25% per additional strategy) to capitalise
on high-conviction trades.

Paper trading is the default. Set PAPER_TRADING=false to go live.
"""

import logging
import os
import threading
from datetime import datetime, time as dtime

import pytz

from jarvis.plugins.trading.analysts.fundamental import FundamentalAnalyst
from jarvis.plugins.trading.analysts.sentiment import SentimentAnalyst
from jarvis.plugins.trading.notifier import Notifier
from jarvis.plugins.trading.position_store import PositionStore
from jarvis.plugins.trading.risk_manager import RiskManager
from jarvis.plugins.trading.robinhood_client import RobinhoodClient
from jarvis.plugins.trading.scanner import StockScanner
from jarvis.plugins.trading.strategies.manager import StrategyManager
from jarvis.plugins.trading.trade_log import TradeLog

logger = logging.getLogger(__name__)

MARKET_OPEN = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)
EOD_FORCE_CLOSE = dtime(15, 45)
ET = pytz.timezone("America/New_York")

MAX_CANDIDATES_PER_CYCLE = int(os.getenv("MAX_CANDIDATES_PER_CYCLE", "30"))
MAX_BUYS_PER_CYCLE = int(os.getenv("MAX_BUYS_PER_CYCLE", "5"))


class TradingBot:
    """Self-contained multi-strategy AI trading bot running in a daemon thread."""

    def __init__(self):
        paper = os.getenv("PAPER_TRADING", "true").lower() != "false"
        self._client = RobinhoodClient(paper_trading=paper)
        self._sentiment = SentimentAnalyst()
        self._fundamental = FundamentalAnalyst()
        self._strategies = StrategyManager()
        self._risk = RiskManager()
        self._scanner = StockScanner()
        self._notifier = Notifier()
        self._positions = PositionStore()
        self._trade_log = TradeLog()

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_scan_symbols: list[str] = []
        self._session_start_iso: str = ""
        self._daily_goal: float = float(os.getenv("DAILY_GOAL", "0"))

        default_interval = 60 if self._strategies.has_intraday else 300
        self._scan_interval = int(os.getenv("SCAN_INTERVAL_SECONDS", default_interval))

    # ------------------------------------------------------------------
    # Public control interface
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paper_trading(self) -> bool:
        return self._client.paper_trading

    @property
    def active_strategies(self) -> list[str]:
        return self._strategies.active_names

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
        self._trade_log.record_portfolio_value(portfolio_value)
        self._session_start_iso = datetime.now().isoformat(timespec="seconds")

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._running = True

        mode = "PAPER" if self._client.paper_trading else "LIVE"
        strategies = ", ".join(self._strategies.active_names)
        trades_limit = "unlimited" if self._risk.MAX_DAILY_TRADES == 0 else str(self._risk.MAX_DAILY_TRADES)
        msg = (
            f"Trading bot started in {mode} mode.\n"
            f"Portfolio: ${portfolio_value:,.2f}\n"
            f"Active strategies: {strategies}\n"
            f"Daily trades: {trades_limit} | Scan interval: {self._scan_interval}s"
        )
        self._notifier.info(f"[BOT STARTED] {mode} | ${portfolio_value:,.2f} | {strategies}")
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
        return "Bot frozen – no new trades. Say 'unfreeze bot' to resume."

    def unfreeze(self) -> str:
        self._risk.unfreeze()
        self._notifier.info("[KILL SWITCH] Bot unfrozen.")
        return "Bot unfrozen – resuming normal operation."

    def close_all(self) -> str:
        """Emergency close of every open position at market price."""
        positions = self._client.get_positions()
        if not positions:
            return "No open positions to close."
        count = 0
        for symbol, pos in positions.items():
            price = self._client.get_current_price(symbol) or pos["average_buy_price"]
            self._execute_sell(symbol, int(pos["quantity"]), price, "panic: close all")
            count += 1
        return f"Closing {count} position(s). Orders submitted."

    def get_status(self) -> str:
        if not self._running:
            return (
                "Bot is stopped. Say 'start trading' to begin.\n"
                f"Configured strategies: {', '.join(self._strategies.active_names)}"
            )

        try:
            portfolio_value = self._client.get_portfolio_value()
            buying_power = self._client.get_buying_power()
            positions = self._client.get_positions()
        except Exception as exc:
            return f"Could not fetch status: {exc}"

        mode = "PAPER" if self._client.paper_trading else "LIVE"
        frozen_tag = " [FROZEN]" if self._risk.is_frozen else ""
        stats = self._risk.get_stats()
        trade_stats = self._trade_log.stats()

        lines = [
            f"Status : RUNNING ({mode}){frozen_tag}",
            f"Strategies: {', '.join(self._strategies.active_names)}",
            f"Portfolio: ${portfolio_value:,.2f}",
            f"Buying power: ${buying_power:,.2f}",
            f"Open positions: {len(positions)}",
            f"Trades today: {stats['daily_trades']} ({'unlimited' if stats['unlimited_trades'] else stats['max_daily_trades']})",
            f"Win rate: {trade_stats['win_rate']}% | Profit factor: {trade_stats['profit_factor']} | Total P&L: ${trade_stats['total_pnl']:+,.2f}",
        ]

        for symbol, pos in positions.items():
            price = self._client.get_current_price(symbol) or pos["average_buy_price"]
            pnl_pct = (price - pos["average_buy_price"]) / pos["average_buy_price"] * 100
            sign = "+" if pnl_pct >= 0 else ""
            meta = self._positions.get(symbol)
            strat_tag = f" [{meta['strategy']}]" if meta else ""
            stop = self._risk.stop_loss_price(pos["average_buy_price"])
            lines.append(
                f"  {symbol}{strat_tag}: {pos['quantity']:.0f} sh @ ${pos['average_buy_price']:.2f}"
                f" | now ${price:.2f} ({sign}{pnl_pct:.1f}%) | stop ${stop:.2f}"
            )

        return "\n".join(lines)

    def get_trade_stats(self) -> dict:
        return {
            "stats": self._trade_log.stats(),
            "by_strategy": self._trade_log.by_strategy(),
            "best_strategy": self._trade_log.best_strategy(),
            "equity_history": self._trade_log.equity_history(),
            "recent_trades": self._trade_log.recent_trades(20),
        }

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
                    logger.debug("Market closed – standing by.")
            except Exception as exc:
                logger.error(f"Unhandled error in trading cycle: {exc}", exc_info=True)
                self._notifier.error_alert(str(exc))

            self._stop_event.wait(timeout=self._scan_interval)

        logger.info("Trading bot loop ended.")

    # ------------------------------------------------------------------
    # Core trading cycle
    # ------------------------------------------------------------------

    def _trading_cycle(self) -> None:
        portfolio_value = self._client.get_portfolio_value()
        self._trade_log.record_portfolio_value(portfolio_value)

        if self._risk.check_circuit_breaker(portfolio_value):
            if self._risk.is_frozen:
                self._notifier.circuit_breaker_alert()
            logger.warning("Circuit breaker active – skipping this cycle.")
            return

        self._manage_open_positions()
        self._scan_and_buy(portfolio_value)

    # ------------------------------------------------------------------
    # Exit management
    # ------------------------------------------------------------------

    def _manage_open_positions(self) -> None:
        positions = self._client.get_positions()
        near_close = self._is_near_market_close()

        for symbol, pos in positions.items():
            price = self._client.get_current_price(symbol)
            if price is None:
                continue

            meta = self._positions.get(symbol)
            strategy_name = meta["strategy"] if meta else None
            entry_price = meta["entry_price"] if meta else pos["average_buy_price"]
            age_minutes = self._positions.age_minutes(symbol)

            exit_reason: str | None = None

            if self._risk.should_stop_loss(symbol, price, pos["average_buy_price"]):
                exit_reason = "risk: global stop-loss hit"

            if exit_reason is None and strategy_name:
                exit_now, reason = self._strategies.check_exit(
                    symbol, strategy_name, entry_price, age_minutes
                )
                if exit_now:
                    exit_reason = reason

            if exit_reason is None and near_close and strategy_name:
                strat = self._strategies.get(strategy_name)
                if strat and strat.intraday:
                    exit_reason = f"{strategy_name}: EOD force-close"

            if exit_reason:
                self._execute_sell(symbol, int(pos["quantity"]), price, exit_reason)

    # ------------------------------------------------------------------
    # Entry scan - multi-strategy consensus
    # ------------------------------------------------------------------

    def _scan_and_buy(self, portfolio_value: float) -> None:
        watchlist = self._scanner.get_watchlist()
        held = set(self._client.get_positions().keys())
        candidates = [s for s in watchlist if s not in held]

        # Collect all signals per symbol (multi-strategy)
        symbol_signals: list[tuple] = []  # (symbol, best_signal, consensus_count)
        self._last_scan_symbols = candidates[:MAX_CANDIDATES_PER_CYCLE]

        for symbol in candidates[:MAX_CANDIDATES_PER_CYCLE]:
            try:
                company = self._scanner.get_company_name(symbol)
                sent = self._sentiment.analyze(symbol, company)
                fund = self._fundamental.analyze(symbol)
                signals = self._strategies.evaluate_all(symbol, sent, fund)
                if signals:
                    best = max(signals, key=lambda s: s.score)
                    symbol_signals.append((symbol, best, len(signals)))
            except Exception as exc:
                logger.warning(f"Analysis failed for {symbol}: {exc}")

        # Sort by consensus-boosted score (more strategies agreeing = higher priority)
        symbol_signals.sort(
            key=lambda x: x[1].score * (1 + (x[2] - 1) * 0.2),
            reverse=True
        )

        for symbol, signal, consensus in symbol_signals[:MAX_BUYS_PER_CYCLE]:
            # Shares boost: +25% per additional strategy that agrees
            share_boost = 1.0 + (consensus - 1) * 0.25
            self._execute_buy(signal, portfolio_value, share_boost=share_boost)

    # ------------------------------------------------------------------
    # Order execution
    # ------------------------------------------------------------------

    def _execute_buy(self, signal, portfolio_value: float, share_boost: float = 1.0) -> None:
        strat = self._strategies.get(signal.strategy_name)
        if strat and strat.intraday and self._risk.pdt_would_block():
            logger.info(f"Skipping {signal.strategy_name} buy on {signal.symbol}: PDT limit")
            return

        price = self._client.get_current_price(signal.symbol)
        if price is None:
            return

        buying_power = self._client.get_buying_power()
        base_shares = self._risk.position_size(portfolio_value, price)
        shares = max(1, int(base_shares * share_boost))

        if shares * price > buying_power:
            # Try fewer shares if full amount unavailable
            shares = int(buying_power / price)
            if shares < 1:
                return

        limit = round(price * 1.005, 2)
        result = self._client.buy(signal.symbol, shares, limit)

        if "error" not in result:
            self._risk.record_trade()
            self._positions.record_entry(signal.symbol, signal.strategy_name, price)
            consensus_tag = f" (x{share_boost:.1f} consensus)" if share_boost > 1.0 else ""
            self._notifier.trade_alert(
                "BUY", signal.symbol, shares, price,
                signal.score, self._client.paper_trading,
            )
            logger.info(
                f"[{signal.strategy_name}] Bought {shares} {signal.symbol} "
                f"@ ${price:.2f} (score={signal.score:.0%}){consensus_tag}"
            )
        else:
            logger.error(f"Buy order failed for {signal.symbol}: {result.get('error')}")

    def _execute_sell(self, symbol: str, shares: int, price: float, reason: str) -> None:
        limit = round(price * 0.99, 2)
        result = self._client.sell(symbol, shares, limit)

        if "error" not in result:
            self._risk.record_trade()
            self._risk.clear_position_peak(symbol)

            meta = self._positions.get(symbol)
            if meta:
                try:
                    entry = datetime.fromisoformat(meta["entry_date"])
                    # Record the completed trade in the log
                    self._trade_log.record_close(
                        symbol=symbol,
                        strategy=meta.get("strategy", "unknown"),
                        entry_price=meta["entry_price"],
                        exit_price=price,
                        shares=shares,
                        entry_date=meta["entry_date"],
                        reason=reason,
                    )
                    if entry.date() == datetime.now().date():
                        self._risk.record_day_trade()
                except Exception:
                    pass

            self._positions.remove(symbol)
            self._notifier.trade_alert(
                "SELL", symbol, shares, price, 0.0, self._client.paper_trading,
            )
            logger.info(f"Sold {shares} {symbol} @ ${price:.2f} ({reason})")
        else:
            logger.error(f"Sell order failed for {symbol}: {result.get('error')}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_market_open() -> bool:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return False
        return MARKET_OPEN <= now.time() <= MARKET_CLOSE

    @staticmethod
    def _is_near_market_close() -> bool:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return False
        return EOD_FORCE_CLOSE <= now.time() <= MARKET_CLOSE
