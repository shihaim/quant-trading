from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from trader.data.models import DailyEquity


@dataclass(frozen=True)
class DailyPnlSnapshot:
    """일일 손익 스냅샷."""

    date_utc: date
    start_equity: Decimal
    last_equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    daily_pnl_abs: Decimal
    daily_pnl_pct: Decimal


class PnLService:
    """일일 기준자산과 손익 스냅샷을 관리한다."""

    def __init__(self, session: Session):
        self.session = session

    def update_daily_snapshot(
        self,
        current_equity: Decimal,
        realized_pnl: Decimal,
        unrealized_pnl: Decimal,
        as_of_date_utc: date | None = None,
    ) -> DailyPnlSnapshot:
        d_utc = as_of_date_utc or datetime.now(timezone.utc).date()
        row = self.session.get(DailyEquity, d_utc)
        if row is None:
            row = DailyEquity(
                date_utc=d_utc,
                start_equity=current_equity,
                last_equity=current_equity,
            )
            self.session.add(row)
        row.last_equity = current_equity
        row.realized_pnl = realized_pnl
        row.unrealized_pnl = unrealized_pnl
        daily_pnl_abs = current_equity - Decimal(row.start_equity)
        row.daily_pnl_abs = daily_pnl_abs
        if Decimal(row.start_equity) > 0:
            row.daily_pnl_pct = daily_pnl_abs / Decimal(row.start_equity)
        else:
            row.daily_pnl_pct = Decimal("0")
        self.session.commit()
        self.session.refresh(row)
        return DailyPnlSnapshot(
            date_utc=row.date_utc,
            start_equity=Decimal(row.start_equity),
            last_equity=Decimal(row.last_equity),
            realized_pnl=Decimal(row.realized_pnl),
            unrealized_pnl=Decimal(row.unrealized_pnl),
            daily_pnl_abs=Decimal(row.daily_pnl_abs),
            daily_pnl_pct=Decimal(row.daily_pnl_pct),
        )
