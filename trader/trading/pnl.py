from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from trader.data.models import DailyEquity

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailyPnlSnapshot:
    """일일 손익 스냅샷."""

    date_utc: date
    start_equity: Decimal
    start_realized_pnl: Decimal
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
        created = row is None
        if row is None:
            row = DailyEquity(
                date_utc=d_utc,
                start_equity=current_equity,
                start_realized_pnl=realized_pnl,
                last_equity=current_equity,
            )
            self.session.add(row)
        elif row.start_realized_pnl is None:
            row.start_realized_pnl = realized_pnl
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
        snapshot = DailyPnlSnapshot(
            date_utc=row.date_utc,
            start_equity=Decimal(row.start_equity),
            start_realized_pnl=Decimal(row.start_realized_pnl),
            last_equity=Decimal(row.last_equity),
            realized_pnl=Decimal(row.realized_pnl),
            unrealized_pnl=Decimal(row.unrealized_pnl),
            daily_pnl_abs=Decimal(row.daily_pnl_abs),
            daily_pnl_pct=Decimal(row.daily_pnl_pct),
        )
        logger.info(
            "pnl_daily_snapshot_updated date_utc=%s created=%s start_equity=%s start_realized_pnl=%s "
            "last_equity=%s daily_pnl_abs=%s daily_pnl_pct=%s",
            snapshot.date_utc,
            created,
            snapshot.start_equity,
            snapshot.start_realized_pnl,
            snapshot.last_equity,
            snapshot.daily_pnl_abs,
            snapshot.daily_pnl_pct,
        )
        return snapshot

    @staticmethod
    def resolve_daily_pnl_pct(
        snapshot: DailyPnlSnapshot,
        basis: str,
        current_realized_pnl: Decimal,
    ) -> tuple[Decimal, Decimal]:
        normalized = str(basis or "").strip().upper()
        if normalized == "REALIZED_ONLY":
            daily_abs = current_realized_pnl - Decimal(snapshot.start_realized_pnl)
            if Decimal(snapshot.start_equity) > 0:
                daily_pct = daily_abs / Decimal(snapshot.start_equity)
            else:
                daily_pct = Decimal("0")
            logger.debug(
                "pnl_basis_resolved basis=%s daily_abs=%s daily_pct=%s",
                normalized,
                daily_abs,
                daily_pct,
            )
            return daily_abs, daily_pct
        daily_abs = Decimal(snapshot.daily_pnl_abs)
        daily_pct = Decimal(snapshot.daily_pnl_pct)
        logger.debug("pnl_basis_resolved basis=%s daily_abs=%s daily_pct=%s", normalized, daily_abs, daily_pct)
        return daily_abs, daily_pct
