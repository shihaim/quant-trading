from __future__ import annotations

from collections.abc import Iterator
from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


def estimate_row_count(session: Session, model: type[T]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def fetch_singleton(session: Session, model: type[T], primary_key: Any = 1) -> T | None:
    return session.get(model, primary_key)


def iter_rows_by_id(session: Session, model: type[T], batch_size: int) -> Iterator[list[T]]:
    if not hasattr(model, "id"):
        raise ValueError(f"{model.__name__} does not expose an id column for batch iteration")

    last_seen_id = 0
    while True:
        rows = session.scalars(
            select(model)
            .where(getattr(model, "id") > last_seen_id)
            .order_by(getattr(model, "id").asc())
            .limit(batch_size)
        ).all()
        if not rows:
            return
        yield rows
        last_seen_id = int(getattr(rows[-1], "id"))
