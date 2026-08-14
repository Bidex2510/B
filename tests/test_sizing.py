from trading.signals.models import Direction
from trading.risk.sizing import calculate_shares


def test_calculate_shares_long():
    # $10,000 * 0.5% = $50 max loss; risk/share = $0.20 -> 250 shares
    shares = calculate_shares(account_equity=10_000, risk_pct_per_trade=0.005, direction=Direction.LONG, entry=5.00, stop=4.80)
    assert shares == 250


def test_calculate_shares_short():
    shares = calculate_shares(account_equity=10_000, risk_pct_per_trade=0.005, direction=Direction.SHORT, entry=5.00, stop=5.20)
    assert shares == 250


def test_calculate_shares_zero_when_stop_equals_entry():
    shares = calculate_shares(account_equity=10_000, risk_pct_per_trade=0.005, direction=Direction.LONG, entry=5.00, stop=5.00)
    assert shares == 0


def test_calculate_shares_rounds_down():
    # $50 / $0.30 = 166.67 -> 166 shares, never round up past the risk budget
    shares = calculate_shares(account_equity=10_000, risk_pct_per_trade=0.005, direction=Direction.LONG, entry=5.00, stop=4.70)
    assert shares == 166
