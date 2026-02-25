from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class HealthSnapshot:
    last_loop_at: datetime | None
    error_count_15m: int
    rate_limit_15m: int
    open_orders: int
    exposure_pct: Decimal
    daily_pnl_pct: Decimal
    is_halted: bool


def format_health_status(snapshot: HealthSnapshot) -> str:
    last_loop = snapshot.last_loop_at.isoformat() if snapshot.last_loop_at else "n/a"
    return (
        f"status last_loop={last_loop} "
        f"errors_15m={snapshot.error_count_15m} rate_limit_15m={snapshot.rate_limit_15m} "
        f"open_orders={snapshot.open_orders} exposure_pct={snapshot.exposure_pct:.6f} "
        f"daily_pnl_pct={snapshot.daily_pnl_pct:.6f} halted={snapshot.is_halted}"
    )
