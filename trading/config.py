"""Scanner configuration: the criteria that define the small-cap trading universe."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class ScannerConfig:
    price_min: float = 2.0
    price_max: float = 20.0
    market_cap_max: float = 1_000_000_000
    min_premarket_volume: int = 500_000
    min_avg_daily_volume: int = 1_000_000
    min_relative_volume: float = 5.0
    min_gap_pct: float = 10.0
    min_float_shares: int = 1_000_000
    max_float_shares: int = 20_000_000
    exclude_otc: bool = True
    avg_volume_lookback_days: int = 20

    @classmethod
    def from_env(cls) -> "ScannerConfig":
        return cls(
            price_min=_env_float("SCANNER_PRICE_MIN", cls.price_min),
            price_max=_env_float("SCANNER_PRICE_MAX", cls.price_max),
            market_cap_max=_env_float("SCANNER_MARKET_CAP_MAX", cls.market_cap_max),
            min_premarket_volume=_env_int("SCANNER_MIN_PREMARKET_VOLUME", cls.min_premarket_volume),
            min_avg_daily_volume=_env_int("SCANNER_MIN_AVG_DAILY_VOLUME", cls.min_avg_daily_volume),
            min_relative_volume=_env_float("SCANNER_MIN_RVOL", cls.min_relative_volume),
            min_gap_pct=_env_float("SCANNER_MIN_GAP_PCT", cls.min_gap_pct),
            min_float_shares=_env_int("SCANNER_MIN_FLOAT", cls.min_float_shares),
            max_float_shares=_env_int("SCANNER_MAX_FLOAT", cls.max_float_shares),
            exclude_otc=_env_bool("SCANNER_EXCLUDE_OTC", cls.exclude_otc),
            avg_volume_lookback_days=_env_int("SCANNER_AVG_VOLUME_LOOKBACK_DAYS", cls.avg_volume_lookback_days),
        )
