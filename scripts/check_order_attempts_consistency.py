from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from trader.data.db import create_session
from trader.data.models import Order, OrderAttempt
from trader.trading.order_attempts import latest_attempt_from_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check order_attempts duplicate refs and orders/attempt drift.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Optional user scope filter.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=200,
        help="Max issue rows to include for each category.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional path to write full JSON report.",
    )
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="Exit with code 1 when any issue is found.",
    )
    return parser.parse_args()


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _normalize_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _duplicate_reference_rows(
    *,
    session,
    field: str,
    user_id: int | None,
    max_items: int,
) -> list[dict]:
    column = getattr(OrderAttempt, field)
    base = (
        select(column, func.count().label("count"))
        .join(Order, OrderAttempt.order_id == Order.id)
        .where(column.is_not(None))
    )
    if user_id is not None:
        base = base.where(Order.user_id == user_id)
    grouped = (
        base.group_by(column)
        .having(func.count() > 1)
        .order_by(func.count().desc(), column.asc())
        .limit(max_items)
    )
    duplicates = []
    for value, count in session.execute(grouped).all():
        if _normalize_text(value) is None:
            continue
        sample_rows = (
            session.execute(
                select(
                    Order.user_id,
                    OrderAttempt.order_id,
                    OrderAttempt.id,
                    OrderAttempt.attempt_no,
                    OrderAttempt.state,
                    OrderAttempt.updated_at,
                )
                .join(Order, OrderAttempt.order_id == Order.id)
                .where(column == value)
                .order_by(OrderAttempt.id.asc())
                .limit(10)
            )
            .all()
        )
        duplicates.append(
            {
                "value": value,
                "count": int(count),
                "samples": [
                    {
                        "user_id": int(sample.user_id),
                        "order_id": int(sample.order_id),
                        "attempt_id": int(sample.id),
                        "attempt_no": int(sample.attempt_no),
                        "state": sample.state,
                        "updated_at": str(sample.updated_at) if sample.updated_at is not None else None,
                    }
                    for sample in sample_rows
                ],
            }
        )
    return duplicates


def _drift_rows(*, session, user_id: int | None, max_items: int) -> list[dict]:
    query = select(Order).options(selectinload(Order.attempts)).order_by(Order.updated_at.desc())
    if user_id is not None:
        query = query.where(Order.user_id == user_id)

    rows = session.execute(query).scalars().all()
    drift_items: list[dict] = []
    compare_fields = (
        "requested_price",
        "requested_volume",
        "upbit_identifier",
        "upbit_uuid",
        "state",
        "retry_count",
        "error_class",
        "last_error",
    )
    for row in rows:
        latest = latest_attempt_from_rows(row.attempts)
        if latest is None:
            continue
        mismatches = []
        for field in compare_fields:
            order_value = _normalize_value(getattr(row, field))
            attempt_value = _normalize_value(getattr(latest, field))
            if order_value != attempt_value:
                mismatches.append(
                    {
                        "field": field,
                        "order": order_value,
                        "latest_attempt": attempt_value,
                    }
                )
        if mismatches:
            drift_items.append(
                {
                    "user_id": int(row.user_id),
                    "order_id": int(row.id),
                    "latest_attempt_id": int(latest.id),
                    "latest_attempt_no": int(latest.attempt_no),
                    "mismatches": mismatches,
                }
            )
        if len(drift_items) >= max_items:
            break
    return drift_items


def build_report(*, user_id: int | None, max_items: int) -> dict:
    normalized_max_items = max(1, int(max_items))
    normalized_user_id = None if user_id is None else max(1, int(user_id))
    session = create_session()
    try:
        duplicate_identifier = _duplicate_reference_rows(
            session=session,
            field="upbit_identifier",
            user_id=normalized_user_id,
            max_items=normalized_max_items,
        )
        duplicate_uuid = _duplicate_reference_rows(
            session=session,
            field="upbit_uuid",
            user_id=normalized_user_id,
            max_items=normalized_max_items,
        )
        drift = _drift_rows(
            session=session,
            user_id=normalized_user_id,
            max_items=normalized_max_items,
        )
    finally:
        session.close()

    total_issues = len(duplicate_identifier) + len(duplicate_uuid) + len(drift)
    return {
        "scope": {"user_id": normalized_user_id, "max_items": normalized_max_items},
        "summary": {
            "duplicate_upbit_identifier_count": len(duplicate_identifier),
            "duplicate_upbit_uuid_count": len(duplicate_uuid),
            "order_latest_attempt_drift_count": len(drift),
            "total_issues": total_issues,
        },
        "issues": {
            "duplicate_upbit_identifier": duplicate_identifier,
            "duplicate_upbit_uuid": duplicate_uuid,
            "order_latest_attempt_drift": drift,
        },
    }


def main() -> int:
    args = parse_args()
    report = build_report(user_id=args.user_id, max_items=args.max_items)
    summary = report["summary"]
    print(
        "order_attempts_consistency "
        f"issues={summary['total_issues']} "
        f"dup_identifier={summary['duplicate_upbit_identifier_count']} "
        f"dup_uuid={summary['duplicate_upbit_uuid_count']} "
        f"drift={summary['order_latest_attempt_drift_count']}"
    )
    print(json.dumps(summary, ensure_ascii=False))

    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report_json={output_path}")

    if args.fail_on_issues and int(summary["total_issues"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
