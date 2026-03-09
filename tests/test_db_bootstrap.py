from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

import trader.data.db as db_module
from trader.data.db import (
    Base,
    _get_kst_view_sql,
    _postgres_ensure_positions_user_scope,
    _seed_timeframe_config,
    _sync_schema_docs,
)
from trader.data.models import BotConfig
from trader.utils.timeframes import SUPPORTED_TIMEFRAMES


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return engine


def test_seed_timeframe_config_populates_supported_rows():
    engine = _engine()
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with Session() as session:
        session.add(BotConfig(id=1, timeframe="5m", markets_json='["KRW-BTC"]'))
        session.commit()

    with engine.begin() as conn:
        _seed_timeframe_config(conn)
        rows = conn.execute(text("SELECT timeframe, is_enabled FROM timeframe_config")).fetchall()

    assert {row[0] for row in rows} == set(SUPPORTED_TIMEFRAMES)
    assert [row[0] for row in rows if row[1]] == ["5m"]


def test_sync_schema_docs_inserts_reference_rows():
    engine = _engine()

    with engine.begin() as conn:
        _sync_schema_docs(conn)
        table_count = conn.execute(text("SELECT COUNT(*) FROM schema_table_docs")).scalar_one()
        column_count = conn.execute(
            text("SELECT COUNT(*) FROM schema_column_docs WHERE table_name = 'bot_config'")
        ).scalar_one()
        audit_table_count = conn.execute(
            text("SELECT COUNT(*) FROM schema_table_docs WHERE table_name = 'audit_log'")
        ).scalar_one()
        audit_column_count = conn.execute(
            text("SELECT COUNT(*) FROM schema_column_docs WHERE table_name = 'audit_log'")
        ).scalar_one()
        risk_guard_table_count = conn.execute(
            text("SELECT COUNT(*) FROM schema_table_docs WHERE table_name = 'user_risk_guard'")
        ).scalar_one()
        risk_guard_column_count = conn.execute(
            text("SELECT COUNT(*) FROM schema_column_docs WHERE table_name = 'user_risk_guard'")
        ).scalar_one()
        budget_table_count = conn.execute(
            text("SELECT COUNT(*) FROM schema_table_docs WHERE table_name = 'user_api_budget'")
        ).scalar_one()
        budget_column_count = conn.execute(
            text("SELECT COUNT(*) FROM schema_column_docs WHERE table_name = 'user_api_budget'")
        ).scalar_one()

    assert table_count > 0
    assert column_count > 0
    assert audit_table_count == 1
    assert audit_column_count >= 5
    assert risk_guard_table_count == 1
    assert risk_guard_column_count >= 6
    assert budget_table_count == 1
    assert budget_column_count >= 7


def test_get_kst_view_sql_switches_by_dialect():
    postgres_bind = type("Bind", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})()
    sqlite_bind = type("Bind", (), {"dialect": type("Dialect", (), {"name": "sqlite"})()})()

    postgres_sql = _get_kst_view_sql(postgres_bind)
    sqlite_sql = _get_kst_view_sql(sqlite_bind)

    assert "AT TIME ZONE 'Asia/Seoul'" in postgres_sql["orders_kst"]
    assert "datetime(created_at, '+9 hours')" in sqlite_sql["orders_kst"]
    assert "AT TIME ZONE 'Asia/Seoul'" in postgres_sql["audit_log_kst"]
    assert "datetime(created_at, '+9 hours')" in sqlite_sql["audit_log_kst"]
    assert "AT TIME ZONE 'Asia/Seoul'" in postgres_sql["user_risk_guard_kst"]
    assert "datetime(updated_at, '+9 hours')" in sqlite_sql["user_risk_guard_kst"]
    assert "AT TIME ZONE 'Asia/Seoul'" in postgres_sql["user_api_budget_kst"]
    assert "datetime(window_started_at, '+9 hours')" in sqlite_sql["user_api_budget_kst"]


def test_audit_log_table_exists_with_expected_indexes():
    engine = _engine()
    inspector = inspect(engine)

    assert "audit_log" in inspector.get_table_names()
    index_names = {index["name"] for index in inspector.get_indexes("audit_log")}
    assert "ix_audit_log_actor_user_id" in index_names
    assert "ix_audit_log_action" in index_names
    assert "ix_audit_log_target_type" in index_names
    assert "ix_audit_log_target_id" in index_names
    assert "ix_audit_log_created_at" in index_names


def test_user_risk_guard_table_exists_with_expected_indexes():
    engine = _engine()
    inspector = inspect(engine)

    assert "user_risk_guard" in inspector.get_table_names()
    index_names = {index["name"] for index in inspector.get_indexes("user_risk_guard")}
    assert "ix_user_risk_guard_user_id" in index_names
    assert "ix_user_risk_guard_manual_halt" in index_names
    assert "ix_user_risk_guard_emergency_kill_switch" in index_names
    unique_names = {row["name"] for row in inspector.get_unique_constraints("user_risk_guard")}
    assert "uq_user_risk_guard_user_id" in unique_names


def test_user_api_budget_table_exists_with_expected_indexes():
    engine = _engine()
    inspector = inspect(engine)

    assert "user_api_budget" in inspector.get_table_names()
    index_names = {index["name"] for index in inspector.get_indexes("user_api_budget")}
    assert "ix_user_api_budget_user_id" in index_names
    assert "ix_user_api_budget_scope" in index_names
    assert "ix_user_api_budget_window_started_at" in index_names
    unique_names = {row["name"] for row in inspector.get_unique_constraints("user_api_budget")}
    assert "uq_user_api_budget_user_scope" in unique_names


def test_user_exchange_credentials_contains_key_version_column():
    engine = _engine()
    inspector = inspect(engine)

    columns = {col["name"] for col in inspector.get_columns("user_exchange_credentials")}
    assert "key_version" in columns


def test_postgres_positions_user_scope_repairs_legacy_primary_key(monkeypatch):
    class _ScalarResult:
        def __init__(self, value):
            self._value = value

        def scalar_one(self):
            return self._value

    class _FakeInspector:
        def get_table_names(self):
            return ["positions"]

        def get_columns(self, table_name: str):
            assert table_name == "positions"
            return [{"name": "user_id"}, {"name": "market"}]

        def get_pk_constraint(self, table_name: str):
            assert table_name == "positions"
            return {"name": "positions_pkey", "constrained_columns": ["market"]}

    class _FakeConn:
        def __init__(self):
            self.statements: list[str] = []

        def execute(self, statement, params=None):
            sql = str(statement)
            self.statements.append(sql)
            if "GROUP BY user_id, market" in sql:
                return _ScalarResult(0)
            return _ScalarResult(1)

    inspector_stub = _FakeInspector()
    fake_conn = _FakeConn()
    monkeypatch.setattr(db_module, "inspect", lambda _conn: inspector_stub)

    _postgres_ensure_positions_user_scope(fake_conn, owner_user_id=7)

    combined = "\n".join(fake_conn.statements)
    assert "UPDATE positions SET user_id = COALESCE(user_id, :owner_user_id) WHERE user_id IS NULL" in combined
    assert 'ALTER TABLE positions DROP CONSTRAINT "positions_pkey"' in combined
    assert "ALTER TABLE positions ADD PRIMARY KEY (user_id, market)" in combined
