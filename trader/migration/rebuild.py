from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.data.models import DailyEquity, PaperWallet, Position
from trader.migration.contracts import TableStats
from trader.migration.readers import estimate_row_count


def _assign_columns(target_row, source_row, exclude: tuple[str, ...] = ()) -> None:
    excluded = set(exclude)
    for column in source_row.__table__.columns:
        if column.name in excluded:
            continue
        setattr(target_row, column.name, getattr(source_row, column.name))


def _rows_differ(target_row, source_row, exclude: tuple[str, ...] = ()) -> bool:
    excluded = set(exclude)
    for column in source_row.__table__.columns:
        if column.name in excluded:
            continue
        if getattr(target_row, column.name) != getattr(source_row, column.name):
            return True
    return False


@dataclass
class SnapshotTableSynchronizer:
    """
    Copy current-state snapshot tables from source to target.

    This is intentionally separate from the primary event migration because these
    tables are operational snapshots, not immutable source-of-truth records.
    """

    def run(
        self,
        source_session: Session,
        target_session: Session,
        dry_run: bool = False,
        missing_target_tables: set[str] | None = None,
    ) -> list[TableStats]:
        missing = missing_target_tables or set()
        stats = [
            self._sync_positions(source_session, target_session, dry_run=dry_run, target_missing="positions" in missing),
            self._sync_paper_wallet(source_session, target_session, dry_run=dry_run, target_missing="paper_wallet" in missing),
            self._sync_daily_equity(source_session, target_session, dry_run=dry_run, target_missing="daily_equity" in missing),
        ]
        return stats

    def _sync_positions(self, source_session: Session, target_session: Session, dry_run: bool, target_missing: bool) -> TableStats:
        stats = TableStats(
            table_name="positions",
            source_rows=estimate_row_count(source_session, Position),
            target_rows=0 if target_missing else estimate_row_count(target_session, Position),
        )
        for source_row in source_session.scalars(select(Position).order_by(Position.market.asc())).all():
            target_row = None if target_missing else target_session.get(Position, source_row.market)
            if target_row is None:
                stats.inserted += 1
                if not dry_run:
                    target_row = Position(market=source_row.market)
                    target_session.add(target_row)
                    _assign_columns(target_row, source_row, exclude=("market",))
            elif _rows_differ(target_row, source_row, exclude=("market",)):
                stats.updated += 1
                if not dry_run:
                    _assign_columns(target_row, source_row, exclude=("market",))
            else:
                stats.skipped += 1
        if not dry_run:
            target_session.commit()
        return stats

    def _sync_paper_wallet(self, source_session: Session, target_session: Session, dry_run: bool, target_missing: bool) -> TableStats:
        stats = TableStats(
            table_name="paper_wallet",
            source_rows=estimate_row_count(source_session, PaperWallet),
            target_rows=0 if target_missing else estimate_row_count(target_session, PaperWallet),
        )
        source_row = source_session.get(PaperWallet, 1)
        if source_row is None:
            return stats
        target_row = None if target_missing else target_session.get(PaperWallet, 1)
        if target_row is None:
            stats.inserted += 1
            if not dry_run:
                target_row = PaperWallet(id=1)
                target_session.add(target_row)
                _assign_columns(target_row, source_row, exclude=("id",))
        elif _rows_differ(target_row, source_row, exclude=("id",)):
            stats.updated += 1
            if not dry_run:
                _assign_columns(target_row, source_row, exclude=("id",))
        else:
            stats.skipped += 1
        if not dry_run:
            target_session.commit()
        return stats

    def _sync_daily_equity(self, source_session: Session, target_session: Session, dry_run: bool, target_missing: bool) -> TableStats:
        stats = TableStats(
            table_name="daily_equity",
            source_rows=estimate_row_count(source_session, DailyEquity),
            target_rows=0 if target_missing else estimate_row_count(target_session, DailyEquity),
        )
        for source_row in source_session.scalars(select(DailyEquity).order_by(DailyEquity.date_utc.asc())).all():
            target_row = None if target_missing else target_session.get(DailyEquity, source_row.date_utc)
            if target_row is None:
                stats.inserted += 1
                if not dry_run:
                    target_row = DailyEquity(date_utc=source_row.date_utc)
                    target_session.add(target_row)
                    _assign_columns(target_row, source_row, exclude=("date_utc",))
            elif _rows_differ(target_row, source_row, exclude=("date_utc",)):
                stats.updated += 1
                if not dry_run:
                    _assign_columns(target_row, source_row, exclude=("date_utc",))
            else:
                stats.skipped += 1
        if not dry_run:
            target_session.commit()
        return stats
