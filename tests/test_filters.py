from trading.config import ScannerConfig
from trading.scanner.filters import passes_all_filters
from trading.scanner.models import Fundamentals, StockSnapshot

CONFIG = ScannerConfig(
    price_min=2.0,
    price_max=20.0,
    market_cap_max=1_000_000_000,
    min_premarket_volume=500_000,
    min_avg_daily_volume=1_000_000,
    min_relative_volume=5.0,
    min_gap_pct=10.0,
    min_float_shares=1_000_000,
    max_float_shares=20_000_000,
    exclude_otc=True,
)


def make_snapshot(**overrides) -> StockSnapshot:
    defaults = dict(
        symbol="ABCD",
        exchange="NASDAQ",
        price=5.0,
        previous_close=4.0,
        premarket_volume=12_000_000,
        avg_daily_volume=2_000_000,
        fundamentals=Fundamentals(market_cap=200_000_000, float_shares=5_000_000),
    )
    defaults.update(overrides)
    return StockSnapshot(**defaults)


def test_qualifying_snapshot_passes_all_filters():
    assert passes_all_filters(CONFIG, make_snapshot())


def test_price_out_of_range_fails():
    assert not passes_all_filters(CONFIG, make_snapshot(price=25.0))


def test_market_cap_too_large_fails():
    fundamentals = Fundamentals(market_cap=2_000_000_000, float_shares=5_000_000)
    assert not passes_all_filters(CONFIG, make_snapshot(fundamentals=fundamentals))


def test_missing_fundamentals_fails_closed():
    fundamentals = Fundamentals(market_cap=None, float_shares=None)
    assert not passes_all_filters(CONFIG, make_snapshot(fundamentals=fundamentals))


def test_float_outside_range_fails():
    fundamentals = Fundamentals(market_cap=200_000_000, float_shares=50_000_000)
    assert not passes_all_filters(CONFIG, make_snapshot(fundamentals=fundamentals))


def test_insufficient_gap_fails():
    assert not passes_all_filters(CONFIG, make_snapshot(price=4.2, previous_close=4.0))


def test_insufficient_relative_volume_fails():
    assert not passes_all_filters(CONFIG, make_snapshot(premarket_volume=100_000))


def test_otc_excluded_when_configured():
    assert not passes_all_filters(CONFIG, make_snapshot(exchange="OTC"))


def test_otc_allowed_when_not_excluded():
    config = ScannerConfig(
        price_min=2.0,
        price_max=20.0,
        market_cap_max=1_000_000_000,
        min_premarket_volume=500_000,
        min_avg_daily_volume=1_000_000,
        min_relative_volume=5.0,
        min_gap_pct=10.0,
        min_float_shares=1_000_000,
        max_float_shares=20_000_000,
        exclude_otc=False,
    )
    assert passes_all_filters(config, make_snapshot(exchange="OTC"))
