from datetime import date

import pytest

from trading.backtest.period_split import generate_weekdays, split_trading_days


def test_generate_weekdays_excludes_saturday_and_sunday():
    # 2026-08-10 is a Monday
    days = generate_weekdays(date(2026, 8, 10), date(2026, 8, 16))
    assert days == [date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 12), date(2026, 8, 13), date(2026, 8, 14)]


def test_generate_weekdays_single_day():
    assert generate_weekdays(date(2026, 8, 10), date(2026, 8, 10)) == [date(2026, 8, 10)]


def test_split_trading_days_preserves_chronological_order():
    days = [date(2026, 8, 1 + i) for i in range(10)]
    split = split_trading_days(days, train_pct=0.6, validate_pct=0.2)
    assert split.train == days[:6]
    assert split.validate == days[6:8]
    assert split.test == days[8:]
    assert split.train + split.validate + split.test == days


def test_split_trading_days_rejects_invalid_percentages():
    days = [date(2026, 8, 1 + i) for i in range(10)]
    with pytest.raises(ValueError):
        split_trading_days(days, train_pct=0.7, validate_pct=0.4)
    with pytest.raises(ValueError):
        split_trading_days(days, train_pct=0.0, validate_pct=0.2)
