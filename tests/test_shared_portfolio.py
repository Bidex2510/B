from datetime import date, datetime

from trading.backtest.models import BacktestConfig
from trading.backtest.shared_portfolio import run_shared_portfolio_backtest
from trading.risk.models import RiskConfig
from trading.signals.models import Candle, Direction

DAY1 = date(2026, 8, 10)
DAY2 = date(2026, 8, 11)


def candle(o, h, l, c, minute, v=1000):
    return Candle(time=datetime(2026, 8, 14, 9, 30 + minute), open=o, high=h, low=l, close=c, volume=v)


class FakeDataSource:
    def __init__(self, premarket, session):
        self._premarket = premarket
        self._session = session

    def get_premarket_candles(self, symbol, day):
        return self._premarket.get((symbol, day), [])

    def get_session_candles(self, symbol, day, end_time=None):
        return self._session.get((symbol, day), [])


def flat_session():
    # spike sets the day's high to 5.60, giving the next day's setup a
    # prior-day-high target that clears the minimum R:R
    return [candle(5.00, 5.02, 4.98, 5.00, i) for i in range(9)] + [candle(5.00, 5.60, 4.98, 5.02, 9)]


def long_setup_session():
    return [
        candle(4.70, 4.72, 4.68, 4.71, 0),
        candle(4.71, 4.73, 4.69, 4.72, 1),
        candle(4.72, 4.74, 4.70, 4.73, 2),
        candle(4.73, 4.75, 4.71, 4.74, 3),
        candle(4.74, 4.76, 4.72, 4.75, 4),
        candle(4.75, 4.76, 4.74, 4.75, 5),
        candle(4.75, 4.76, 4.74, 4.75, 6),
        candle(4.75, 4.76, 4.74, 4.75, 7),
        candle(4.75, 4.76, 4.55, 4.70, 8),
        candle(4.95, 5.20, 4.90, 5.15, 9),
        candle(5.15, 5.25, 4.85, 5.20, 10),
        candle(5.20, 5.30, 5.15, 5.25, 11),
        candle(5.25, 5.65, 5.20, 5.60, 12),
    ]


def make_config():
    return BacktestConfig(
        risk_config=RiskConfig(risk_pct_per_trade=0.005, min_risk_reward=2.0, atr_stop_multiplier=1.0),
        starting_equity=10_000,
        opening_range_minutes=5,
        atr_period=14,
        min_target_distance=0.10,
    )


def test_shared_portfolio_compounds_equity_across_days():
    data_source = FakeDataSource(
        premarket={("ABCD", DAY2): [candle(4.70, 4.72, 4.65, 4.68, -30)]},
        session={
            ("ABCD", DAY1): flat_session(),
            ("ABCD", DAY2): long_setup_session(),
        },
    )

    result = run_shared_portfolio_backtest(["ABCD"], [DAY1, DAY2], data_source, make_config())

    assert [dr.day for dr in result.day_results] == [DAY1, DAY2]
    day1, day2 = result.day_results
    assert day1.trades == []
    assert day1.ending_equity == 10_000
    assert day2.starting_equity == 10_000
    assert len(day2.trades) == 1
    assert day2.trades[0].direction == Direction.LONG
    assert round(day2.ending_equity, 2) == 10_140.00
    assert round(result.final_equity, 2) == 10_140.00


def test_day_with_no_candles_for_any_symbol_is_skipped():
    data_source = FakeDataSource(premarket={}, session={})
    result = run_shared_portfolio_backtest(["ABCD"], [DAY1], data_source, make_config())
    assert result.day_results[0].trades == []
    assert result.final_equity == 10_000


def test_symbol_with_mismatched_length_excluded_from_that_day():
    # ABCD has a full session, EFGH is short one bar (simulating a halt/gap) -
    # EFGH is dropped from that day's shared run rather than raising.
    data_source = FakeDataSource(
        premarket={},
        session={
            ("ABCD", DAY1): flat_session(),
            ("EFGH", DAY1): flat_session()[:-1],
        },
    )
    result = run_shared_portfolio_backtest(["ABCD", "EFGH"], [DAY1], data_source, make_config())
    assert result.day_results[0].trades == []  # flat data, no signals either way
    assert result.final_equity == 10_000
