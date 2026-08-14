"""Market cap and float data.

Alpaca's Trading and Market Data APIs do not expose fundamentals (market cap,
shares float), so this is intentionally a separate, pluggable source. Ship a
CSV-backed provider for now; swap in a real fundamentals API by implementing
the same interface.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Optional, Protocol

from trading.scanner.models import Fundamentals


class FundamentalsProvider(Protocol):
    def get(self, symbol: str) -> Optional[Fundamentals]:
        ...


class CsvFundamentalsProvider:
    """Reads symbol,market_cap,float_shares rows from a CSV file.

    Populate this file yourself from a fundamentals source (e.g. an export
    from your data vendor) — Alpaca does not provide this data.
    """

    def __init__(self, csv_path: Path):
        self._data: Dict[str, Fundamentals] = {}
        if csv_path.exists():
            with csv_path.open(newline="") as f:
                for row in csv.DictReader(f):
                    symbol = row["symbol"].strip().upper()
                    market_cap = float(row["market_cap"]) if row.get("market_cap") else None
                    float_shares = int(row["float_shares"]) if row.get("float_shares") else None
                    self._data[symbol] = Fundamentals(market_cap=market_cap, float_shares=float_shares)

    def get(self, symbol: str) -> Optional[Fundamentals]:
        return self._data.get(symbol.upper())
