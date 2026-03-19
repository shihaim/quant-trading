from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.data.models import AuditLog, User

ACTION_CREDENTIAL_UPDATE = "credential_update"
ACTION_BOT_START = "bot_start"
ACTION_BOT_STOP = "bot_stop"
ACTION_ADMIN_ACTION = "admin_action"
ACTION_REQUEST_BUDGET_BLOCKED = "request_budget_blocked"

SUCCESS_OUTCOMES = {"allowed", "ok", "success", "succeeded", "pass", "passed"}
FAILURE_OUTCOMES = {"forbidden", "blocked", "failed", "error", "denied", "reject", "rejected"}
SENSITIVE_KEY_PARTS = {
    "password",
    "secret",
    "token",
    "authorization",
    "access_key",
    "secret_key",
    "credential",
}


@dataclass(frozen=True)
class AuditLogReadQuery:
    actor_user_id: int | None = None
    target_user_id: int | None = None
    action: str | None = None
    target_type: str | None = None
    from_utc: datetime | None = None
    to_utc: datetime | None = None
    success: bool | None = None
    limit: int = 50
    offset: int = 0
    max_scan_rows: int = 5000


class AuditService:
    """Persist audit trails for user/admin actions."""

    def __init__(self, *, session: Session):
        self.session = session

    def record_action(
        self,
        *,
        action: str,
        target_type: str,
        actor_user_id: int | None = None,
        target_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        payload = metadata or {}
        row = AuditLog(
            actor_user_id=actor_user_id,
            action=(action or "").strip(),
            target_type=(target_type or "").strip(),
            target_id=target_id,
            metadata_json=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_logs(self, *, query: AuditLogReadQuery) -> dict:
        normalized_limit = max(1, min(200, int(query.limit)))
        normalized_offset = max(0, int(query.offset))
        normalized_max_scan_rows = max(100, min(20000, int(query.max_scan_rows)))
        chunk_size = max(200, normalized_limit * 4)

        stmt = (
            select(AuditLog, User.email)
            .outerjoin(User, AuditLog.actor_user_id == User.id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        )
        if query.actor_user_id is not None:
            stmt = stmt.where(AuditLog.actor_user_id == max(1, int(query.actor_user_id)))
        if query.action:
            stmt = stmt.where(AuditLog.action == str(query.action).strip())
        if query.target_type:
            stmt = stmt.where(AuditLog.target_type == str(query.target_type).strip())
        if query.from_utc is not None:
            stmt = stmt.where(AuditLog.created_at >= self._normalize_utc(query.from_utc))
        if query.to_utc is not None:
            stmt = stmt.where(AuditLog.created_at <= self._normalize_utc(query.to_utc))

        kept_rows: list[dict] = []
        scanned_rows = 0
        base_offset = 0
        scan_capped = False
        needed_count = normalized_offset + normalized_limit + 1
        while len(kept_rows) < needed_count:
            if scanned_rows >= normalized_max_scan_rows:
                scan_capped = True
                break
            batch = self.session.execute(stmt.offset(base_offset).limit(chunk_size)).all()
            if not batch:
                break
            scanned_rows += len(batch)
            for row, actor_email in batch:
                item = self._to_read_item(row=row, actor_email=actor_email)
                if query.target_user_id is not None and item["target_user_id"] != max(1, int(query.target_user_id)):
                    continue
                if query.success is not None and item["is_success"] is not query.success:
                    continue
                kept_rows.append(item)
                if len(kept_rows) >= needed_count:
                    break
            base_offset += len(batch)
            if len(batch) < chunk_size:
                break

        items = kept_rows[normalized_offset : normalized_offset + normalized_limit]
        has_more = len(kept_rows) > (normalized_offset + normalized_limit)
        return {
            "items": items,
            "pagination": {
                "limit": normalized_limit,
                "offset": normalized_offset,
                "returned": len(items),
                "has_more": has_more,
            },
            "scan": {
                "scanned_rows": scanned_rows,
                "scan_capped": scan_capped,
                "max_scan_rows": normalized_max_scan_rows,
            },
        }

    def _to_read_item(self, *, row: AuditLog, actor_email: str | None) -> dict:
        metadata = self._parse_metadata(row.metadata_json)
        target_user_id = self._extract_target_user_id(row=row, metadata=metadata)
        is_success = self._resolve_success(metadata=metadata)
        return {
            "id": row.id,
            "created_at_utc": self._iso_utc(row.created_at),
            "actor_user_id": row.actor_user_id,
            "actor_email": actor_email,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "target_user_id": target_user_id,
            "is_success": is_success,
            "metadata": self._sanitize_metadata(metadata),
        }

    @staticmethod
    def _parse_metadata(raw: str | None) -> dict[str, Any]:
        if not str(raw or "").strip():
            return {}
        try:
            payload = json.loads(str(raw))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _sanitize_metadata(cls, payload: dict[str, Any]) -> dict[str, Any]:
        def scrub(value: Any, key: str | None = None) -> Any:
            if key is not None and any(part in key.lower() for part in SENSITIVE_KEY_PARTS):
                return "[redacted]"
            if isinstance(value, dict):
                out: dict[str, Any] = {}
                for child_key, child_value in value.items():
                    out[str(child_key)] = scrub(child_value, key=str(child_key))
                return out
            if isinstance(value, list):
                return [scrub(item, key=key) for item in value]
            if isinstance(value, str) and value.strip().lower().startswith("bearer "):
                return "[redacted]"
            return value

        return scrub(payload)

    @classmethod
    def _extract_target_user_id(cls, *, row: AuditLog, metadata: dict[str, Any]) -> int | None:
        raw_target_user_id = metadata.get("target_user_id")
        try:
            if raw_target_user_id is not None:
                value = int(raw_target_user_id)
                if value > 0:
                    return value
        except Exception:
            pass

        target_id = str(row.target_id or "").strip()
        if not target_id:
            return None
        first = target_id.split(":", 1)[0]
        if first.isdigit():
            value = int(first)
            return value if value > 0 else None
        return None

    @staticmethod
    def _resolve_success(*, metadata: dict[str, Any]) -> bool | None:
        outcome = str(metadata.get("outcome", "")).strip().lower()
        if not outcome:
            return None
        if outcome in SUCCESS_OUTCOMES:
            return True
        if outcome in FAILURE_OUTCOMES:
            return False
        return None

    @staticmethod
    def _normalize_utc(ts: datetime) -> datetime:
        return ts.astimezone(timezone.utc) if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)

    @classmethod
    def _iso_utc(cls, ts: datetime | None) -> str | None:
        if ts is None:
            return None
        normalized = cls._normalize_utc(ts)
        return normalized.isoformat().replace("+00:00", "Z")
