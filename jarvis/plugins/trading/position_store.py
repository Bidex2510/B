"""Per-position metadata store.

Robinhood only tracks symbol / quantity / average price - it has no notion
of which strategy opened a position. We persist that ourselves in
~/.jarvis_positions.json so exits use the right rules across bot restarts.

Each record:
  {
    "strategy": "swing",
    "entry_date": "2026-04-22T09:35:12",
    "entry_price": 175.32
  }
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

_STORE_PATH = os.path.expanduser(
    os.getenv("TRADING_POSITIONS_FILE", "~/.jarvis_positions.json")
)


class PositionStore:
    def __init__(self):
        self._data: dict[str, dict] = {}
        self._load()

    def record_entry(self, symbol: str, strategy: str, entry_price: float) -> None:
        self._data[symbol] = {
            "strategy": strategy,
            "entry_date": datetime.now().isoformat(timespec="seconds"),
            "entry_price": float(entry_price),
        }
        self._save()

    def get(self, symbol: str) -> dict | None:
        return self._data.get(symbol)

    def remove(self, symbol: str) -> None:
        if symbol in self._data:
            del self._data[symbol]
            self._save()

    def all(self) -> dict[str, dict]:
        return dict(self._data)

    def age_minutes(self, symbol: str) -> float:
        rec = self._data.get(symbol)
        if not rec:
            return 0.0
        try:
            entry = datetime.fromisoformat(rec["entry_date"])
            return (datetime.now() - entry).total_seconds() / 60.0
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(_STORE_PATH):
            return
        try:
            with open(_STORE_PATH) as f:
                self._data = json.load(f)
        except Exception as exc:
            logger.warning(f"Could not load position store: {exc}")
            self._data = {}

    def _save(self) -> None:
        try:
            with open(_STORE_PATH, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as exc:
            logger.warning(f"Could not save position store: {exc}")
