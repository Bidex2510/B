from trading.signals.spread import passes_spread_filter, spread_pct


def test_spread_pct_computation():
    assert round(spread_pct(3.99, 4.01), 4) == round(0.02 / 4.00 * 100, 4)


def test_tight_spread_passes():
    assert passes_spread_filter(bid=3.99, ask=4.01, max_spread_pct=0.5)


def test_wide_spread_fails():
    assert not passes_spread_filter(bid=3.90, ask=4.10, max_spread_pct=0.5)
