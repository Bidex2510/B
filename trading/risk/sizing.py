"""Dynamic position sizing from account risk, not a fixed share count."""

from __future__ import annotations

import math

from trading.signals.models import Direction
from trading.risk.stops import stop_distance


def calculate_shares(account_equity: float, risk_pct_per_trade: float, direction: Direction, entry: float, stop: float) -> int:
    risk_per_share = stop_distance(direction, entry, stop)
    if risk_per_share <= 0:
        return 0
    max_loss = account_equity * risk_pct_per_trade
    # Tiny epsilon guards against float noise (e.g. 0.2 stored as
    # 0.20000000000000018) knocking a boundary case down a whole share.
    return math.floor(max_loss / risk_per_share + 1e-9)
