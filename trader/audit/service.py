from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from trader.data.models import AuditLog

ACTION_CREDENTIAL_UPDATE = "credential_update"
ACTION_BOT_START = "bot_start"
ACTION_BOT_STOP = "bot_stop"
ACTION_ADMIN_ACTION = "admin_action"
ACTION_REQUEST_BUDGET_BLOCKED = "request_budget_blocked"


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
