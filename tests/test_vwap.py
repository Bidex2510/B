from datetime import datetime

from trading.signals.models import Candle
from trading.signals.vwap import compute_session_vwap


def candle(o, h, l, c, v, minute=0):
    return Candle(time=datetime(2026, 8, 14, 9, 30 + minute), open=o, high=h, low=l, close=c, volume=v)


def test_vwap_equals_typical_price_on_first_candle():
    candles = [candle(5.0, 5.2, 4.9, 5.1, 1000)]
    vwap = compute_session_vwap(candles)
    typical = (5.2 + 4.9 + 5.1) / 3
    assert vwap[0] == typical


def test_vwap_is_cumulative_volume_weighted():
    candles = [
        candle(5.0, 5.0, 5.0, 5.0, 1000, minute=0),
        candle(6.0, 6.0, 6.0, 6.0, 1000, minute=1),
    ]
    vwap = compute_session_vwap(candles)
    assert vwap[0] == 5.0
    assert vwap[1] == 5.5


def test_vwap_handles_zero_volume_candle():
    candles = [candle(5.0, 5.0, 5.0, 5.0, 0)]
    vwap = compute_session_vwap(candles)
    assert vwap[0] == 5.0
