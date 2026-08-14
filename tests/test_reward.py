from trading.signals.models import Direction
from trading.risk.reward import (
    compute_r_multiple,
    nearest_target_above,
    nearest_target_below,
    passes_min_risk_reward,
)


def test_nearest_target_above_picks_closest_qualifying_level():
    levels = [5.60, 5.80, 6.20]
    assert nearest_target_above(entry=5.00, levels=levels, min_distance=0.30) == 5.60


def test_nearest_target_above_excludes_levels_inside_min_distance():
    levels = [5.10, 5.80]
    assert nearest_target_above(entry=5.00, levels=levels, min_distance=0.30) == 5.80


def test_nearest_target_above_none_when_no_qualifying_level():
    assert nearest_target_above(entry=5.00, levels=[5.05], min_distance=0.30) is None


def test_nearest_target_below_picks_closest_qualifying_level():
    levels = [4.40, 4.20, 3.80]
    assert nearest_target_below(entry=5.00, levels=levels, min_distance=0.30) == 4.40


def test_r_multiple_long():
    r = compute_r_multiple(Direction.LONG, entry=5.00, stop=4.80, target=5.60)
    assert round(r, 6) == 3.0


def test_r_multiple_short():
    r = compute_r_multiple(Direction.SHORT, entry=5.00, stop=5.20, target=4.40)
    assert round(r, 6) == 3.0


def test_r_multiple_zero_when_risk_is_zero():
    assert compute_r_multiple(Direction.LONG, entry=5.00, stop=5.00, target=5.60) == 0.0


def test_passes_min_risk_reward():
    assert passes_min_risk_reward(Direction.LONG, entry=5.00, stop=4.80, target=5.60, min_risk_reward=2.0)
    assert not passes_min_risk_reward(Direction.LONG, entry=5.00, stop=4.80, target=5.30, min_risk_reward=2.0)
