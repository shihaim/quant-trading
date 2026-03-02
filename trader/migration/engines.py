from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from trader.data.db import Base, _seed_timeframe_config, _sync_kst_views, _sync_schema_docs


@dataclass(frozen=True)
class SessionRuntime:
    engine: Engine
    session_factory: sessionmaker

    def create_session(self) -> Session:
        return self.session_factory()


def build_runtime(database_url: str) -> SessionRuntime:
    engine = create_engine(database_url, future=True)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return SessionRuntime(engine=engine, session_factory=factory)


def dispose_runtime(runtime: SessionRuntime) -> None:
    runtime.engine.dispose()


def list_tables(runtime: SessionRuntime) -> set[str]:
    return set(inspect(runtime.engine).get_table_names())


def bootstrap_target_database(runtime: SessionRuntime) -> None:
    Base.metadata.create_all(bind=runtime.engine)
    with runtime.engine.begin() as conn:
        _seed_timeframe_config(conn)
        _sync_schema_docs(conn)
        _sync_kst_views(conn)
