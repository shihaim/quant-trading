from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from trader.data.db import Base, _get_kst_view_sql, _seed_timeframe_config, _sync_schema_docs
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

    assert table_count > 0
    assert column_count > 0


def test_get_kst_view_sql_switches_by_dialect():
    postgres_bind = type("Bind", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})()
    sqlite_bind = type("Bind", (), {"dialect": type("Dialect", (), {"name": "sqlite"})()})()

    postgres_sql = _get_kst_view_sql(postgres_bind)
    sqlite_sql = _get_kst_view_sql(sqlite_bind)

    assert "AT TIME ZONE 'Asia/Seoul'" in postgres_sql["orders_kst"]
    assert "datetime(created_at, '+9 hours')" in sqlite_sql["orders_kst"]
