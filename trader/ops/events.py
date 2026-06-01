from __future__ import annotations

from datetime import datetime, timezone

from trader.ops.dto import iso_kst


def _parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event(
    *,
    event_id: str,
    kind: str,
    severity: str,
    title: str,
    message: str,
    occurred_at_utc: str | None,
    action_label: str,
    action_view: str,
    detail: dict | None = None,
) -> dict:
    payload = {
        "id": event_id,
        "kind": kind,
        "severity": severity,
        "status": "open",
        "occurred_at_utc": occurred_at_utc,
        "occurred_at_kst": iso_kst(_parse_iso_utc(occurred_at_utc)),
        "title": title,
        "message": message,
        "action_label": action_label,
        "action_view": action_view,
    }
    if detail is not None:
        payload["detail"] = detail
    return payload


def user_events(
    *,
    halt: dict,
    credential: dict,
    needs_review_count: int,
    runtime_last_error: str | None,
    runtime_updated_at_utc: str | None,
) -> list[dict]:
    events: list[dict] = []
    halt_reason = str(halt.get("reason") or "").strip()
    if halt.get("is_halted") or halt_reason:
        events.append(
            _event(
                event_id=f"halt:{halt_reason or 'active'}",
                kind="halt",
                severity="critical",
                title="자동매매가 잠시 멈췄어요",
                message="안전 기준에 따라 자동매매가 멈췄어요. 상태를 확인한 뒤 다시 시작해 주세요.",
                occurred_at_utc=halt.get("triggered_at_utc"),
                action_label="자동매매 상태 확인",
                action_view="control",
            )
        )

    if (not credential.get("has_credentials")) or (not credential.get("is_valid")):
        has_credentials = bool(credential.get("has_credentials"))
        events.append(
            _event(
                event_id="credential:upbit",
                kind="credential_issue",
                severity="warning",
                title="업비트 연결을 확인해 주세요",
                message=(
                    "업비트 연결 정보를 다시 저장하면 자동매매를 사용할 수 있어요."
                    if has_credentials
                    else "업비트 연결 정보를 등록하면 자동매매를 사용할 수 있어요."
                ),
                occurred_at_utc=credential.get("updated_at_utc"),
                action_label="업비트 인증 확인",
                action_view="credentials",
            )
        )

    if needs_review_count > 0:
        events.append(
            _event(
                event_id="orders:needs_review",
                kind="order_review",
                severity="warning",
                title="확인이 필요한 주문이 있어요",
                message=f"확인이 필요한 주문 {needs_review_count}건이 있어요.",
                occurred_at_utc=None,
                action_label="주문 확인",
                action_view="orders",
            )
        )

    if str(runtime_last_error or "").strip():
        events.append(
            _event(
                event_id="runtime:last_error",
                kind="runtime_error",
                severity="warning",
                title="최근 실행 상태를 확인해 주세요",
                message="자동매매가 최근 실행 중 문제를 만났어요. 잠시 후 다시 확인해 주세요.",
                occurred_at_utc=runtime_updated_at_utc,
                action_label="자동매매 상태 확인",
                action_view="control",
            )
        )
    return events


def admin_events(
    *,
    target_user_id: int,
    halt: dict,
    credential: dict | None,
    needs_review_count: int,
    runtime_last_error: str | None,
    runtime_consecutive_failures: int,
    runtime_updated_at_utc: str | None,
) -> list[dict]:
    events: list[dict] = []
    halt_reason = str(halt.get("reason") or "").strip()
    if halt.get("is_halted") or halt_reason:
        events.append(
            _event(
                event_id=f"u{target_user_id}:halt:{halt_reason or 'active'}",
                kind="halt",
                severity="critical",
                title="User runtime halted",
                message=f"Runtime halted: {halt_reason or 'active'}",
                occurred_at_utc=halt.get("triggered_at_utc"),
                action_label="Inspect runtime",
                action_view="admin_user_detail",
                detail={
                    "target_user_id": target_user_id,
                    "reason": halt_reason or None,
                    "cooldown_until_utc": halt.get("cooldown_until_utc"),
                    "message": halt.get("message"),
                },
            )
        )

    if credential is not None and ((not credential.get("has_credentials")) or (not credential.get("is_valid"))):
        events.append(
            _event(
                event_id=f"u{target_user_id}:credential:upbit",
                kind="credential_issue",
                severity="warning",
                title="User credential issue",
                message="UPBIT credential is missing or not usable.",
                occurred_at_utc=credential.get("updated_at_utc"),
                action_label="Inspect credential",
                action_view="admin_user_detail",
                detail={
                    "target_user_id": target_user_id,
                    "exchange": credential.get("exchange") or "UPBIT",
                    "has_credentials": bool(credential.get("has_credentials")),
                    "is_valid": bool(credential.get("is_valid")),
                    "key_version": credential.get("key_version"),
                },
            )
        )

    if needs_review_count > 0:
        events.append(
            _event(
                event_id=f"u{target_user_id}:orders:needs_review",
                kind="order_review",
                severity="warning",
                title="Order needs manual review",
                message=f"{needs_review_count} order requires manual review.",
                occurred_at_utc=None,
                action_label="Inspect orders",
                action_view="admin_user_detail",
                detail={
                    "target_user_id": target_user_id,
                    "needs_review_count": needs_review_count,
                },
            )
        )

    if str(runtime_last_error or "").strip():
        events.append(
            _event(
                event_id=f"u{target_user_id}:runtime:last_error",
                kind="runtime_error",
                severity="warning",
                title="Runtime error recorded",
                message=f"Runtime recorded {runtime_consecutive_failures} consecutive failure(s).",
                occurred_at_utc=runtime_updated_at_utc,
                action_label="Inspect runtime",
                action_view="admin_user_detail",
                detail={
                    "target_user_id": target_user_id,
                    "last_error": runtime_last_error,
                    "consecutive_failures": runtime_consecutive_failures,
                },
            )
        )
    return events
