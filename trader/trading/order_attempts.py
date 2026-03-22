from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trader.data.models import OrderAttempt


def next_attempt_no_for_order(session: Session, order_id: int) -> int:
    current = session.scalar(
        select(func.max(OrderAttempt.attempt_no)).where(OrderAttempt.order_id == order_id)
    )
    return int(current or 0) + 1


def latest_attempt_from_rows(attempts: Sequence[OrderAttempt] | None) -> OrderAttempt | None:
    if not attempts:
        return None
    return max(attempts, key=lambda item: (int(item.attempt_no or 0), int(item.id or 0)))


def load_latest_attempt_for_order(
    session: Session,
    *,
    order_id: int,
    upbit_uuid: str | None = None,
    upbit_identifier: str | None = None,
) -> OrderAttempt | None:
    normalized_uuid = (upbit_uuid or "").strip()
    if normalized_uuid:
        row = session.scalar(
            select(OrderAttempt)
            .where(OrderAttempt.order_id == order_id, OrderAttempt.upbit_uuid == normalized_uuid)
            .order_by(OrderAttempt.attempt_no.desc(), OrderAttempt.id.desc())
        )
        if row is not None:
            return row

    normalized_identifier = (upbit_identifier or "").strip()
    if normalized_identifier:
        row = session.scalar(
            select(OrderAttempt)
            .where(
                OrderAttempt.order_id == order_id,
                OrderAttempt.upbit_identifier == normalized_identifier,
            )
            .order_by(OrderAttempt.attempt_no.desc(), OrderAttempt.id.desc())
        )
        if row is not None:
            return row

    return session.scalar(
        select(OrderAttempt)
        .where(OrderAttempt.order_id == order_id)
        .order_by(OrderAttempt.attempt_no.desc(), OrderAttempt.id.desc())
    )
