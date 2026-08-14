"""Run the scanner and print the watchlist.

Usage:
    python -m trading.cli
"""

from __future__ import annotations

from pathlib import Path

from trading.config import ScannerConfig
from trading.data.alpaca_client import AlpacaClient
from trading.data.fundamentals import CsvFundamentalsProvider
from trading.scanner.scanner import Scanner

DEFAULT_FUNDAMENTALS_CSV = Path(__file__).parent / "data" / "fundamentals.csv"


def print_watchlist(entries) -> None:
    if not entries:
        print("No symbols matched the scan criteria.")
        return
    print(f"{'Ticker':<8}{'Price':>8}{'Gap %':>8}{'RVOL':>8}  Status")
    print("-" * 44)
    for entry in entries:
        snap = entry.snapshot
        print(
            f"{snap.symbol:<8}{snap.price:>8.2f}{snap.gap_pct:>7.1f}%{snap.relative_volume:>7.1f}x  {entry.status}"
        )


def main() -> None:
    config = ScannerConfig.from_env()
    market_data = AlpacaClient()
    fundamentals = CsvFundamentalsProvider(DEFAULT_FUNDAMENTALS_CSV)
    scanner = Scanner(config=config, market_data=market_data, fundamentals=fundamentals)
    print_watchlist(scanner.run())


if __name__ == "__main__":
    main()
