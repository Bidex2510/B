from dataclasses import dataclass
from typing import Dict, List, Optional

from trading.config import ScannerConfig
from trading.scanner.models import Fundamentals
from trading.scanner.scanner import Scanner


@dataclass
class FakeAsset:
    symbol: str
    exchange: str


@dataclass
class FakeVolumeStats:
    avg_daily_volume: float
    previous_close: float


class FakeMarketData:
    def __init__(self, assets, volume_stats, premarket_volumes, prices):
        self._assets = assets
        self._volume_stats = volume_stats
        self._premarket_volumes = premarket_volumes
        self._prices = prices

    def get_tradable_us_equities(self, exclude_otc: bool) -> List[FakeAsset]:
        if exclude_otc:
            return [a for a in self._assets if a.exchange != "OTC"]
        return list(self._assets)

    def get_daily_volume_stats(self, symbol: str, lookback_days: int) -> FakeVolumeStats:
        return self._volume_stats[symbol]

    def get_premarket_volume(self, symbol: str) -> int:
        return self._premarket_volumes[symbol]

    def get_latest_price(self, symbol: str) -> float:
        return self._prices[symbol]


class FakeFundamentals:
    def __init__(self, data: Dict[str, Fundamentals]):
        self._data = data

    def get(self, symbol: str) -> Optional[Fundamentals]:
        return self._data.get(symbol)


def build_scanner(config: ScannerConfig) -> Scanner:
    assets = [
        FakeAsset(symbol="ABCD", exchange="NASDAQ"),  # qualifies
        FakeAsset(symbol="EFGH", exchange="NASDAQ"),  # too big a gap-less move
        FakeAsset(symbol="OTCX", exchange="OTC"),  # excluded by exchange
        FakeAsset(symbol="NOFN", exchange="NASDAQ"),  # missing fundamentals
    ]
    volume_stats = {
        "ABCD": FakeVolumeStats(avg_daily_volume=2_000_000, previous_close=4.0),
        "EFGH": FakeVolumeStats(avg_daily_volume=2_000_000, previous_close=7.0),
        "OTCX": FakeVolumeStats(avg_daily_volume=2_000_000, previous_close=1.0),
        "NOFN": FakeVolumeStats(avg_daily_volume=2_000_000, previous_close=5.0),
    }
    premarket_volumes = {"ABCD": 800_000, "EFGH": 150_000, "OTCX": 800_000, "NOFN": 800_000}
    prices = {"ABCD": 5.0, "EFGH": 7.1, "OTCX": 1.2, "NOFN": 6.0}
    fundamentals = FakeFundamentals(
        {
            "ABCD": Fundamentals(market_cap=200_000_000, float_shares=5_000_000),
            "EFGH": Fundamentals(market_cap=200_000_000, float_shares=5_000_000),
            "OTCX": Fundamentals(market_cap=200_000_000, float_shares=5_000_000),
        }
    )
    market_data = FakeMarketData(assets, volume_stats, premarket_volumes, prices)
    return Scanner(config=config, market_data=market_data, fundamentals=fundamentals)


def test_scanner_filters_to_qualifying_symbols_only():
    config = ScannerConfig(
        price_min=2.0,
        price_max=20.0,
        market_cap_max=1_000_000_000,
        min_premarket_volume=500_000,
        min_avg_daily_volume=1_000_000,
        min_relative_volume=0.1,
        min_gap_pct=10.0,
        min_float_shares=1_000_000,
        max_float_shares=20_000_000,
        exclude_otc=True,
    )
    scanner = build_scanner(config)
    watchlist = scanner.run()

    symbols = [entry.symbol for entry in watchlist]
    assert symbols == ["ABCD"]


def test_scanner_sorts_by_relative_volume_descending():
    config = ScannerConfig(
        price_min=2.0,
        price_max=20.0,
        market_cap_max=1_000_000_000,
        min_premarket_volume=100_000,
        min_avg_daily_volume=1_000_000,
        min_relative_volume=0.01,
        min_gap_pct=0.0,
        min_float_shares=1_000_000,
        max_float_shares=20_000_000,
        exclude_otc=True,
    )
    scanner = build_scanner(config)
    watchlist = scanner.run()

    symbols = [entry.symbol for entry in watchlist]
    assert symbols == ["ABCD", "EFGH"]
    assert watchlist[0].snapshot.relative_volume >= watchlist[1].snapshot.relative_volume
