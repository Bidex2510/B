from datetime import date, datetime

from trading.backtest.models import BacktestConfig
from trading.backtest.portfolio import run_backtest_many
from trading.risk.models import RiskConfig
from trading.signals.models import Candle

DAY1 = date(2026, 8, 10)
DAY2 = date(2026, 8, 11)


def candle(o, h, l, c, minute, v=1000):
    return Candle(time=datetime(2026, 8, 14, 9, 30 + minute), open=o, high=h, low=l, close=c, volume=v)


class FakeDataSource:
    """Keyed by (symbol, day) so different symbols can have different data."""

    def __init__(self, premarket, session):
        self._premarket = premarket
        self._session = session

    def get_premarket_candles(self, symbol, day):
        return self._premarket.get((symbol, day), [])

    def get_session_candles(self, symbol, day, end_time=None):
        return self._session.get((symbol, day), [])


def flat_session():
    # A spike candle sets the day's high to 5.60, giving the next day's setup
    # a prior-day-high target that clears the minimum R:R.
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


def test_run_backtest_many_keeps_symbols_independent():
    data_source = FakeDataSource(
        premarket={("ABCD", DAY2): [candle(4.70, 4.72, 4.65, 4.68, -30)]},
        session={
            ("ABCD", DAY1): flat_session(),
            ("ABCD", DAY2): long_setup_session(),
            ("EFGH", DAY1): flat_session(),
            ("EFGH", DAY2): flat_session(),
        },
    )

    result = run_backtest_many(["ABCD", "EFGH"], [DAY1, DAY2], data_source, make_config())

    assert set(result.results_by_symbol.keys()) == {"ABCD", "EFGH"}
    assert round(result.results_by_symbol["ABCD"].final_equity, 2) == 10_140.00
    assert result.results_by_symbol["EFGH"].final_equity == 10_000

    assert len(result.trades) == 1
    assert round(result.total_pnl, 2) == 140.00


def test_run_backtest_many_with_no_symbols():
    data_source = FakeDataSource(premarket={}, session={})
    result = run_backtest_many([], [DAY1, DAY2], data_source, make_config())
    assert result.results_by_symbol == {}
    assert result.trades == []
    assert result.total_pnl == 0.0
