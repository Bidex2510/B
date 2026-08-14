"""Run the scanner and manage your manual watchlist.

Usage:
    python -m trading.cli scan               # run the scanner (default if no command given)
    python -m trading.cli watch add TICKER
    python -m trading.cli watch remove TICKER
    python -m trading.cli watch list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trading.config import ScannerConfig
from trading.data.alpaca_client import AlpacaClient
from trading.data.fundamentals import CsvFundamentalsProvider
from trading.scanner.scanner import Scanner
from trading.watchlist import ManualWatchlist

DEFAULT_FUNDAMENTALS_CSV = Path(__file__).parent / "data" / "fundamentals.csv"


def print_scanner_watchlist(entries) -> None:
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


def print_manual_watchlist(symbols, market_data: AlpacaClient | None) -> None:
    if not symbols:
        print("(empty — add one with: python -m trading.cli watch add TICKER)")
        return
    if market_data is None:
        for symbol in symbols:
            print(f"  {symbol}")
        return
    print(f"{'Ticker':<8}{'Price':>8}")
    print("-" * 16)
    for symbol in symbols:
        try:
            price = market_data.get_latest_price(symbol)
            print(f"{symbol:<8}{price:>8.2f}")
        except Exception as exc:  # noqa: BLE001 - surface per-symbol data failures without aborting the rest
            print(f"{symbol:<8}  (price unavailable: {exc})")


def run_scan() -> None:
    config = ScannerConfig.from_env()
    market_data = AlpacaClient()
    fundamentals = CsvFundamentalsProvider(DEFAULT_FUNDAMENTALS_CSV)
    scanner = Scanner(config=config, market_data=market_data, fundamentals=fundamentals)

    print("SCANNER WATCHLIST")
    print_scanner_watchlist(scanner.run())

    manual_symbols = ManualWatchlist().list()
    print()
    print("MANUALLY WATCHED")
    print_manual_watchlist(manual_symbols, market_data)


def run_watch(args: argparse.Namespace) -> None:
    watchlist = ManualWatchlist()
    if args.watch_command == "add":
        added = watchlist.add(args.symbol)
        print(f"Added {args.symbol.upper()}" if added else f"{args.symbol.upper()} is already on the watchlist")
    elif args.watch_command == "remove":
        removed = watchlist.remove(args.symbol)
        print(f"Removed {args.symbol.upper()}" if removed else f"{args.symbol.upper()} is not on the watchlist")
    else:
        symbols = watchlist.list()
        print_manual_watchlist(symbols, market_data=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Small-cap scanner and watchlist")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("scan", help="Run the scanner and print the watchlist")

    watch_parser = subparsers.add_parser("watch", help="Manage your manual watchlist")
    watch_sub = watch_parser.add_subparsers(dest="watch_command")
    add_parser = watch_sub.add_parser("add", help="Add a ticker to your manual watchlist")
    add_parser.add_argument("symbol")
    remove_parser = watch_sub.add_parser("remove", help="Remove a ticker from your manual watchlist")
    remove_parser.add_argument("symbol")
    watch_sub.add_parser("list", help="List your manual watchlist")

    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.command == "watch":
        if args.watch_command is None:
            args.watch_command = "list"
        run_watch(args)
    else:
        run_scan()


if __name__ == "__main__":
    main()
