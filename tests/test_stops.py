from trading.signals.models import Direction
from trading.risk.stops import resolve_stop, stop_distance


def test_long_stop_uses_structural_when_wider_than_atr():
    stop = resolve_stop(Direction.LONG, entry=5.00, structural_stop_price=4.80, atr=0.10, atr_multiplier=1.0)
    assert stop == 4.80


def test_long_stop_widens_to_atr_when_structural_too_tight():
    stop = resolve_stop(Direction.LONG, entry=5.00, structural_stop_price=4.95, atr=0.10, atr_multiplier=1.0)
    assert stop == 4.90


def test_short_stop_uses_structural_when_wider_than_atr():
    stop = resolve_stop(Direction.SHORT, entry=5.00, structural_stop_price=5.20, atr=0.10, atr_multiplier=1.0)
    assert stop == 5.20


def test_short_stop_widens_to_atr_when_structural_too_tight():
    stop = resolve_stop(Direction.SHORT, entry=5.00, structural_stop_price=5.05, atr=0.10, atr_multiplier=1.0)
    assert stop == 5.10


def test_stop_distance_long_and_short():
    assert round(stop_distance(Direction.LONG, entry=5.00, stop_price=4.80), 10) == 0.20
    assert round(stop_distance(Direction.SHORT, entry=5.00, stop_price=5.20), 10) == 0.20
