"""Trade log - records every completed trade and portfolio snapshots.

Persists to ~/.jarvis_trade_log.json so history survives restarts.
Provides win rate, profit factor, avg win/loss, and per-strategy breakdown.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

_LOG_PATH = os.path.expanduser(
    os.getenv("TRADING_LOG_FILE", "~/.jarvis_trade_log.json")
)
_MAX_EQUITY_POINTS = 200


class TradeLog:
    def __init__(self):
        self._trades: list[dict] = []
        self._equity_history: list[dict] = []
        self._load()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_close(
        self,
        symbol: str,
        strategy: str,
        entry_price: float,
        exit_price: float,
        shares: float,
        entry_date: str,
        reason: str = "",
    ) -> None:
        pnl = round((exit_price - entry_price) * shares, 2)
        pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2) if entry_price else 0.0
        self._trades.append({
            "symbol": symbol,
            "strategy": strategy,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "shares": shares,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "entry_date": entry_date,
            "exit_date": datetime.now().isoformat(timespec="seconds"),
            "reason": reason,
        })
        self._save()

    def record_portfolio_value(self, value: float) -> None:
        self._equity_history.append({
            "t": datetime.now().isoformat(timespec="seconds"),
            "v": round(value, 2),
        })
        if len(self._equity_history) > _MAX_EQUITY_POINTS:
            self._equity_history = self._equity_history[-_MAX_EQUITY_POINTS:]

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        if not self._trades:
            return {
                "total": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "profit_factor": 0.0,
                "avg_win": 0.0, "avg_loss": 0.0, "total_pnl": 0.0,
            }
        wins = [t for t in self._trades if t["pnl"] > 0]
        losses = [t for t in self._trades if t["pnl"] <= 0]
        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        return {
            "total": len(self._trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(self._trades) * 100, 1),
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 999.0,
            "avg_win": round(gross_profit / len(wins), 2) if wins else 0.0,
            "avg_loss": round(gross_loss / len(losses), 2) if losses else 0.0,
            "total_pnl": round(sum(t["pnl"] for t in self._trades), 2),
        }

    def by_strategy(self) -> dict:
        result: dict[str, dict] = {}
        for t in self._trades:
            s = t.get("strategy") or "unknown"
            if s not in result:
                result[s] = {"trades": 0, "pnl": 0.0, "wins": 0}
            result[s]["trades"] += 1
            result[s]["pnl"] = round(result[s]["pnl"] + t["pnl"], 2)
            if t["pnl"] > 0:
                result[s]["wins"] += 1
        return result

    def best_strategy(self) -> str | None:
        by_strat = self.by_strategy()
        if not by_strat:
            return None
        return max(by_strat, key=lambda k: by_strat[k]["pnl"])

    def equity_history(self) -> list[dict]:
        return list(self._equity_history)

    def recent_trades(self, n: int = 20) -> list[dict]:
        return list(reversed(self._trades[-n:]))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(_LOG_PATH):
            return
        try:
            with open(_LOG_PATH) as f:
                data = json.load(f)
                self._trades = data.get("trades", [])
                self._equity_history = data.get("equity_history", [])
        except Exception as exc:
            logger.warning(f"Could not load trade log: {exc}")

    def _save(self) -> None:
        try:
            with open(_LOG_PATH, "w") as f:
                json.dump({"trades": self._trades, "equity_history": self._equity_history}, f, indent=2)
        except Exception as exc:
            logger.warning(f"Could not save trade log: {exc}")
