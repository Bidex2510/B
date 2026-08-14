"""Manually curated watchlist — symbols you add yourself, independent of the scanner's filters.

Persisted to trading/data/manual_watchlist.json (gitignored — it's local state,
same treatment as Jarvis's .jarvis_tasks.json).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

DEFAULT_WATCHLIST_PATH = Path(__file__).parent / "data" / "manual_watchlist.json"


class ManualWatchlist:
    def __init__(self, path: Path = DEFAULT_WATCHLIST_PATH):
        self._path = path
        self._symbols: List[str] = self._load()

    def _load(self) -> List[str]:
        if not self._path.exists():
            return []
        with self._path.open() as f:
            return json.load(f)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w") as f:
            json.dump(self._symbols, f, indent=2)

    def add(self, symbol: str) -> bool:
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol must not be empty")
        if symbol in self._symbols:
            return False
        self._symbols.append(symbol)
        self._save()
        return True

    def remove(self, symbol: str) -> bool:
        symbol = symbol.strip().upper()
        if symbol not in self._symbols:
            return False
        self._symbols.remove(symbol)
        self._save()
        return True

    def list(self) -> List[str]:
        return list(self._symbols)
