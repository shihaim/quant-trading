from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trader.data.db import Base
from trader.data.models import DailyEquity, Order, PaperWallet, Position, User
from trader.migration.contracts import MigrationOptions
from trader.migration.merge import MigrationService
from trader.migration.v3_user_scope import build_backfill_report, build_v3_user_scope_sql_plan, read_pnl_totals


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def _sqlite_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path.resolve().as_posix()}"


def _session_factory(path: Path):
    url = _sqlite_url(path)
    engine = create_engine(url, future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return url, engine, Session


def test_build_v3_user_scope_sql_plan_contains_stage_blocks():
    plan = build_v3_user_scope_sql_plan(legacy_user_id=7)
    expand_sql = "\n".join(plan.expand_sql)
    rollback_sql = "\n".join(plan.rollback_sql)

    assert "ALTER TABLE orders ADD COLUMN user_id" in expand_sql
    assert "CREATE TABLE IF NOT EXISTS user_bot_config" in expand_sql
    assert "CREATE TABLE IF NOT EXISTS audit_log" in expand_sql
    assert "CREATE TABLE IF NOT EXISTS user_risk_guard" in expand_sql
    assert "CREATE TABLE IF NOT EXISTS user_api_budget" in expand_sql
    assert "ADD COLUMN key_version" in expand_sql
    assert "UPDATE orders SET user_id = COALESCE(user_id, 7)" in expand_sql
    assert "DROP TABLE IF EXISTS user_api_budget" in rollback_sql
    assert "DROP TABLE IF EXISTS user_risk_guard" in rollback_sql
    assert "DROP TABLE IF EXISTS audit_log" in rollback_sql
    assert "DROP TABLE IF EXISTS user_bot_runtime" in rollback_sql
    assert len(plan.validation_sql) >= 4


def test_backfill_report_and_pnl_totals_are_grouped_by_user():
    session = _session()
    session.add_all(
        [
            User(email="u1@example.com", password_hash="h1"),
            User(email="u2@example.com", password_hash="h2"),
        ]
    )
    session.flush()
    session.add(
        Order(
            user_id=1,
            market="KRW-BTC",
            side="bid",
            ord_type="limit",
            requested_price=10000,
            requested_volume=1,
            client_order_id="o-1",
            state="OPEN",
        )
    )
    session.add(Position(user_id=1, market="KRW-BTC", qty=Decimal("1"), avg_price=Decimal("100"), realized_pnl=Decimal("10")))
    session.add(PaperWallet(user_id=1, cash_krw=Decimal("1000000")))
    session.add(
        DailyEquity(
            user_id=1,
            date_utc=date(2026, 3, 8),
            start_equity=Decimal("1000000"),
            last_equity=Decimal("1000010"),
            realized_pnl=Decimal("10"),
            daily_pnl_abs=Decimal("10"),
        )
    )
    session.commit()

    report = build_backfill_report(session)
    totals = read_pnl_totals(session)

    assert report["orders"] == [{"user_id": 1, "row_count": 1}]
    assert report["positions"] == [{"user_id": 1, "row_count": 1}]
    assert report["paper_wallet"] == [{"user_id": 1, "row_count": 1}]
    assert totals["positions_realized_pnl_total"] == Decimal("10")
    assert totals["daily_equity_last_equity_total"] == Decimal("1000010")


def test_migration_dry_run_projects_rows_without_writing_target(tmp_path):
    source_url, source_engine, SourceSession = _session_factory(tmp_path / "v3-source-dry-run.db")
    target_url, target_engine, TargetSession = _session_factory(tmp_path / "v3-target-dry-run.db")

    with SourceSession() as session:
        session.add_all(
            [
                User(id=1, email="u1@example.com", password_hash="h1"),
                User(id=2, email="u2@example.com", password_hash="h2"),
            ]
        )
        session.flush()
        session.add_all(
            [
                Order(
                    user_id=1,
                    market="KRW-BTC",
                    side="bid",
                    ord_type="limit",
                    requested_price=10000,
                    requested_volume=1,
                    client_order_id="dry-run-order-1",
                    state="OPEN",
                ),
                Order(
                    user_id=2,
                    market="KRW-ETH",
                    side="ask",
                    ord_type="limit",
                    requested_price=20000,
                    requested_volume=1,
                    client_order_id="dry-run-order-2",
                    state="OPEN",
                ),
                Position(user_id=1, market="KRW-BTC", qty=Decimal("1"), avg_price=Decimal("100"), realized_pnl=Decimal("10")),
                Position(user_id=2, market="KRW-ETH", qty=Decimal("2"), avg_price=Decimal("200"), realized_pnl=Decimal("-5")),
                PaperWallet(user_id=1, cash_krw=Decimal("1000000")),
                PaperWallet(user_id=2, cash_krw=Decimal("2000000")),
                DailyEquity(
                    user_id=1,
                    date_utc=date(2026, 3, 8),
                    start_equity=Decimal("1000000"),
                    last_equity=Decimal("1000010"),
                    realized_pnl=Decimal("10"),
                    daily_pnl_abs=Decimal("10"),
                ),
                DailyEquity(
                    user_id=2,
                    date_utc=date(2026, 3, 8),
                    start_equity=Decimal("2000000"),
                    last_equity=Decimal("1999995"),
                    realized_pnl=Decimal("-5"),
                    daily_pnl_abs=Decimal("-5"),
                ),
            ]
        )
        session.commit()

    with TargetSession() as session:
        session.add_all(
            [
                User(id=1, email="u1@example.com", password_hash="h1"),
                User(id=2, email="u2@example.com", password_hash="h2"),
            ]
        )
        session.commit()

    summary = MigrationService().run(
        MigrationOptions(
            source_url=source_url,
            target_url=target_url,
            tables=("orders",),
            dry_run=True,
            bootstrap_target=False,
            copy_snapshot_tables=True,
        )
    )

    stats_by_name = {stats.table_name: stats for stats in summary.table_stats}
    assert stats_by_name["orders"].inserted == 2
    assert stats_by_name["positions"].inserted == 2
    assert stats_by_name["paper_wallet"].inserted == 2
    assert stats_by_name["daily_equity"].inserted == 2

    with TargetSession() as session:
        assert len(session.scalars(select(Order.id)).all()) == 0
        assert len(session.scalars(select(Position.user_id)).all()) == 0
        assert len(session.scalars(select(PaperWallet.user_id)).all()) == 0
        assert len(session.scalars(select(DailyEquity.user_id)).all()) == 0

    source_engine.dispose()
    target_engine.dispose()


def test_snapshot_copy_preserves_backfill_totals_and_user_counts(tmp_path):
    source_url, source_engine, SourceSession = _session_factory(tmp_path / "v3-source-integrity.db")
    target_url, target_engine, TargetSession = _session_factory(tmp_path / "v3-target-integrity.db")

    with SourceSession() as session:
        session.add_all(
            [
                User(id=1, email="u1@example.com", password_hash="h1"),
                User(id=2, email="u2@example.com", password_hash="h2"),
            ]
        )
        session.flush()
        session.add_all(
            [
                Order(
                    user_id=1,
                    market="KRW-BTC",
                    side="bid",
                    ord_type="limit",
                    requested_price=10000,
                    requested_volume=1,
                    client_order_id="integrity-order-1",
                    state="OPEN",
                ),
                Position(user_id=1, market="KRW-BTC", qty=Decimal("1"), avg_price=Decimal("100"), realized_pnl=Decimal("10")),
                Position(user_id=2, market="KRW-ETH", qty=Decimal("2"), avg_price=Decimal("200"), realized_pnl=Decimal("-5")),
                PaperWallet(user_id=1, cash_krw=Decimal("1000000")),
                PaperWallet(user_id=2, cash_krw=Decimal("2000000")),
                DailyEquity(
                    user_id=1,
                    date_utc=date(2026, 3, 8),
                    start_equity=Decimal("1000000"),
                    last_equity=Decimal("1000010"),
                    realized_pnl=Decimal("10"),
                    daily_pnl_abs=Decimal("10"),
                ),
                DailyEquity(
                    user_id=2,
                    date_utc=date(2026, 3, 8),
                    start_equity=Decimal("2000000"),
                    last_equity=Decimal("1999995"),
                    realized_pnl=Decimal("-5"),
                    daily_pnl_abs=Decimal("-5"),
                ),
            ]
        )
        session.commit()
        source_report = build_backfill_report(session)
        source_totals = read_pnl_totals(session)

    with TargetSession() as session:
        session.add_all(
            [
                User(id=1, email="u1@example.com", password_hash="h1"),
                User(id=2, email="u2@example.com", password_hash="h2"),
            ]
        )
        session.commit()

    summary = MigrationService().run(
        MigrationOptions(
            source_url=source_url,
            target_url=target_url,
            tables=("orders",),
            dry_run=False,
            bootstrap_target=False,
            copy_snapshot_tables=True,
        )
    )

    stats_by_name = {stats.table_name: stats for stats in summary.table_stats}
    assert stats_by_name["positions"].inserted == 2
    assert stats_by_name["paper_wallet"].inserted == 2
    assert stats_by_name["daily_equity"].inserted == 2

    with TargetSession() as session:
        target_report = build_backfill_report(session)
        target_totals = read_pnl_totals(session)

    assert target_report["positions"] == source_report["positions"]
    assert target_report["paper_wallet"] == source_report["paper_wallet"]
    assert target_report["daily_equity"] == source_report["daily_equity"]
    assert target_totals == source_totals

    source_engine.dispose()
    target_engine.dispose()
