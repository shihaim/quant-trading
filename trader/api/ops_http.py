from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.auth.api_budget import ApiBudgetService, SCOPE_ADMIN, SCOPE_ME
from trader.audit.service import (
    ACTION_ADMIN_ACTION,
    ACTION_BOT_START,
    ACTION_BOT_STOP,
    ACTION_CREDENTIAL_UPDATE,
    ACTION_REQUEST_BUDGET_BLOCKED,
    AuditLogReadQuery,
    AuditService,
)
from trader.auth.credentials import CredentialRotationError, CredentialValidationError, UserCredentialService
from trader.auth.guard import authenticate_request
from trader.auth.service import (
    AuthConflictError,
    AuthCredentialsError,
    AuthService,
    AuthValidationError,
    normalize_email,
    to_identity_payload,
)
from trader.auth.tokens import issue_access_token
from trader.config.settings import settings
from trader.config.config_repo import ConfigRepo
from trader.data.models import User, UserBotRuntime
from trader.me.read_service import MeReadService, UserScopeError
from trader.ops.dto import iso_kst, iso_utc
from trader.ops.service import OpsService

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


def _parse_positive_int(raw: str | None, fallback: int, max_value: int) -> int:
    if raw is None:
        return fallback
    try:
        value = int(raw)
    except Exception:
        return fallback
    if value <= 0:
        return fallback
    return min(value, max_value)


def _parse_non_negative_int(raw: str | None, fallback: int, max_value: int) -> int:
    if raw is None:
        return fallback
    try:
        value = int(raw)
    except Exception:
        return fallback
    if value < 0:
        return fallback
    return min(value, max_value)


def _parse_optional_positive_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        value = int(str(raw).strip())
    except Exception:
        return None
    return value if value > 0 else None


def _parse_utc_datetime(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_success_filter(raw: str | None) -> bool | None:
    if raw is None:
        return None
    value = str(raw).strip().lower()
    if not value or value == "all":
        return None
    if value in {"success", "true", "1", "ok", "allowed", "pass"}:
        return True
    if value in {"failure", "failed", "false", "0", "forbidden", "blocked", "denied", "error"}:
        return False
    return None


def create_ops_handler(
    *,
    session_factory: SessionFactory,
    trade_mode: str,
    allow_origin: str,
) -> type[BaseHTTPRequestHandler]:
    class OpsApiHandler(BaseHTTPRequestHandler):
        server_version = "OpsApi/0.1"

        def _write_cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", allow_origin)
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")

        def _write_json(self, status_code: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self._write_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle_error(self, exc: Exception) -> None:
            logger.exception("ops_api_error path=%s", self.path, exc_info=exc)
            self._write_json(500, {"error": "internal_server_error", "message": str(exc)})

        def _read_json_body(self) -> dict:
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = max(0, int(raw_length))
            except Exception as exc:
                raise ValueError("invalid_json") from exc

            if length == 0:
                return {}

            raw = self.rfile.read(length)
            if not raw:
                return {}

            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                raise ValueError("invalid_json") from exc

            if not isinstance(payload, dict):
                raise ValueError("invalid_json")
            return payload

        def _build_auth_payload(self, *, user) -> dict:
            ttl_seconds = max(1, int(settings.ops_api_auth_token_ttl_seconds))
            token = issue_access_token(
                user_id=user.id,
                secret=settings.ops_api_auth_secret,
                ttl_seconds=ttl_seconds,
            )
            return {
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": ttl_seconds,
                "user": self._identity_payload(user=user),
            }

        def _admin_email_set(self) -> set[str]:
            return {
                normalize_email(str(email))
                for email in settings.ops_api_admin_emails
                if str(email or "").strip()
            }

        def _is_admin_user(self, *, user) -> bool:
            return normalize_email(user.email) in self._admin_email_set()

        def _identity_payload(self, *, user) -> dict:
            return to_identity_payload(user, is_admin=self._is_admin_user(user=user))

        def _credential_service(self, *, session: Session) -> UserCredentialService:
            return UserCredentialService(
                session=session,
                encryption_key=settings.ops_api_credentials_encryption_key,
                active_key_version=settings.ops_api_credentials_active_key_version,
                keyring_json=settings.ops_api_credentials_keyring_json,
            )

        def _budget_window_seconds(self) -> int:
            return max(10, min(3600, int(settings.ops_api_budget_window_seconds)))

        def _budget_limit(self, *, scope: str) -> int:
            if scope == SCOPE_ADMIN:
                return max(1, min(5000, int(settings.ops_api_budget_admin_limit)))
            return max(1, min(5000, int(settings.ops_api_budget_me_limit)))

        def _enforce_request_budget(self, *, session: Session, user, scope: str, source: str) -> dict | None:
            budget_service = ApiBudgetService(session=session)
            snapshot = budget_service.consume(
                user_id=user.id,
                scope=scope,
                limit=self._budget_limit(scope=scope),
                window_seconds=self._budget_window_seconds(),
            )
            if not snapshot.is_limited:
                return snapshot.to_payload()
            self._record_audit_action(
                session=session,
                actor_user_id=user.id,
                action=ACTION_REQUEST_BUDGET_BLOCKED,
                target_type="api_budget",
                target_id=f"{user.id}:{scope}",
                metadata={
                    "source": source,
                    "scope": scope.lower(),
                    "outcome": "blocked",
                    "retry_after_seconds": snapshot.retry_after_seconds,
                },
            )
            self._write_json(
                429,
                {
                    "error": "rate_limited",
                    "message": "request_budget_exceeded",
                    "budget": snapshot.to_payload(),
                },
            )
            return None

        def _current_budget_payload(self, *, session: Session, user, scope: str) -> dict:
            snapshot = ApiBudgetService(session=session).get_current(
                user_id=user.id,
                scope=scope,
                limit=self._budget_limit(scope=scope),
                window_seconds=self._budget_window_seconds(),
            )
            return snapshot.to_payload()

        def _parse_admin_user_scope_path(self, path: str) -> tuple[int, str] | None:
            prefix = "/api/admin/users/"
            if not path.startswith(prefix):
                return None
            suffix = path[len(prefix) :]
            if not suffix:
                return None
            parts = [part for part in suffix.split("/") if part]
            if len(parts) < 2:
                return None
            user_id_raw = parts[0]
            if not user_id_raw.isdigit():
                return None
            user_id = int(user_id_raw)
            if user_id <= 0:
                return None
            scope_path = "/" + "/".join(parts[1:])
            return user_id, scope_path

        def _admin_user_bot_status(self, *, session: Session, target_user_id: int, source: str) -> dict:
            repo = ConfigRepo(session)
            cfg = repo.load_for_user(target_user_id)
            runtime = repo.get_runtime_state(target_user_id)
            runtime_row = session.execute(
                select(UserBotRuntime).where(UserBotRuntime.user_id == target_user_id)
            ).scalar_one_or_none()
            updated_at = runtime_row.updated_at if runtime_row is not None else None
            return {
                "user_id": target_user_id,
                "mode": trade_mode,
                "status": runtime.status,
                "is_enabled": bool(runtime.is_enabled),
                "daily_loss_basis": cfg.daily_loss_basis,
                "max_daily_loss_pct": float(cfg.max_daily_loss_pct),
                "target_exposure_pct": float(cfg.target_exposure_pct),
                "max_total_exposure_pct": float(cfg.max_total_exposure_pct),
                "max_per_market_exposure_pct": float(cfg.max_per_market_exposure_pct),
                "updated_at_utc": iso_utc(updated_at),
                "updated_at_kst": iso_kst(updated_at),
                "source": source,
            }

        def _record_audit_action(
            self,
            *,
            session: Session,
            actor_user_id: int | None,
            action: str,
            target_type: str,
            target_id: str | None = None,
            metadata: dict | None = None,
        ) -> None:
            try:
                AuditService(session=session).record_action(
                    actor_user_id=actor_user_id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    metadata=metadata,
                )
            except Exception as exc:
                logger.exception(
                    "audit_log_write_failed action=%s actor_user_id=%s",
                    action,
                    actor_user_id,
                    exc_info=exc,
                )

        def _require_authenticated_user(self, *, session: Session):
            result = authenticate_request(
                session=session,
                authorization_header=self.headers.get("Authorization"),
                secret=settings.ops_api_auth_secret,
            )
            if result.error is not None:
                self._write_json(401, {"error": "unauthorized", "message": result.error})
                return None
            return result.user

        def _require_admin_user(self, *, session: Session):
            user = self._require_authenticated_user(session=session)
            if user is None:
                return None
            if not self._is_admin_user(user=user):
                self._record_audit_action(
                    session=session,
                    actor_user_id=user.id,
                    action=ACTION_ADMIN_ACTION,
                    target_type="admin_route",
                    target_id=urlparse(self.path).path,
                    metadata={
                        "source": urlparse(self.path).path,
                        "method": self.command,
                        "outcome": "forbidden",
                    },
                )
                self._write_json(403, {"error": "forbidden", "message": "admin_required"})
                return None
            return user

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            session = session_factory()
            try:
                service = OpsService(session=session, trade_mode=trade_mode)
                if parsed.path == "/api/me":
                    user = self._require_authenticated_user(session=session)
                    if user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=user,
                        scope=SCOPE_ME,
                        source=parsed.path,
                    ) is None:
                        return
                    self._write_json(200, {"user": self._identity_payload(user=user)})
                    return
                if parsed.path == "/api/me/credentials/upbit":
                    user = self._require_authenticated_user(session=session)
                    if user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=user,
                        scope=SCOPE_ME,
                        source=parsed.path,
                    ) is None:
                        return
                    credential_service = self._credential_service(
                        session=session,
                    )
                    self._write_json(
                        200,
                        credential_service.get_exchange_credential_status(user=user, exchange="UPBIT"),
                    )
                    return
                if parsed.path == "/api/me/orders":
                    user = self._require_authenticated_user(session=session)
                    if user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=user,
                        scope=SCOPE_ME,
                        source=parsed.path,
                    ) is None:
                        return
                    state = params.get("state", [None])[0]
                    limit = _parse_positive_int(params.get("limit", [None])[0], fallback=50, max_value=500)
                    me_service = MeReadService(
                        session=session,
                        trade_mode=trade_mode,
                        encryption_key=settings.ops_api_credentials_encryption_key,
                    )
                    self._write_json(200, me_service.list_orders(user=user, state=state, limit=limit))
                    return
                if parsed.path == "/api/me/pnl/daily":
                    user = self._require_authenticated_user(session=session)
                    if user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=user,
                        scope=SCOPE_ME,
                        source=parsed.path,
                    ) is None:
                        return
                    days = _parse_positive_int(params.get("days", [None])[0], fallback=30, max_value=365)
                    tz = params.get("tz", ["UTC"])[0]
                    me_service = MeReadService(
                        session=session,
                        trade_mode=trade_mode,
                        encryption_key=settings.ops_api_credentials_encryption_key,
                    )
                    self._write_json(200, me_service.get_pnl_daily(user=user, days=days, tz=tz))
                    return
                if parsed.path == "/api/me/metrics/trade":
                    user = self._require_authenticated_user(session=session)
                    if user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=user,
                        scope=SCOPE_ME,
                        source=parsed.path,
                    ) is None:
                        return
                    limit = _parse_positive_int(params.get("limit", [None])[0], fallback=200, max_value=1000)
                    me_service = MeReadService(
                        session=session,
                        trade_mode=trade_mode,
                        encryption_key=settings.ops_api_credentials_encryption_key,
                    )
                    self._write_json(200, me_service.list_trade_metrics(user=user, limit=limit))
                    return
                if parsed.path == "/api/me/bot/status":
                    user = self._require_authenticated_user(session=session)
                    if user is None:
                        return
                    budget = self._enforce_request_budget(
                        session=session,
                        user=user,
                        scope=SCOPE_ME,
                        source=parsed.path,
                    )
                    if budget is None:
                        return
                    me_service = MeReadService(
                        session=session,
                        trade_mode=trade_mode,
                        encryption_key=settings.ops_api_credentials_encryption_key,
                    )
                    payload = me_service.get_bot_status(user=user)
                    payload["api_budget"] = budget
                    self._write_json(200, payload)
                    return
                if parsed.path == "/api/admin/users/runtime-summary":
                    admin_user = self._require_admin_user(session=session)
                    if admin_user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=admin_user,
                        scope=SCOPE_ADMIN,
                        source=parsed.path,
                    ) is None:
                        return
                    limit = _parse_positive_int(params.get("limit", [None])[0], fallback=200, max_value=1000)
                    payload = service.list_admin_runtime_summary(
                        budget_limit=self._budget_limit(scope=SCOPE_ME),
                        budget_window_seconds=self._budget_window_seconds(),
                        max_users=limit,
                    )
                    items = list(payload.get("items", []))
                    user_ids: list[int] = []
                    for item in items:
                        try:
                            user_id = int(item.get("user_id", 0))
                        except Exception:
                            continue
                        if user_id > 0:
                            user_ids.append(user_id)
                    target_users = (
                        session.execute(select(User).where(User.id.in_(user_ids))).scalars().all()
                        if user_ids
                        else []
                    )
                    user_by_id = {user.id: user for user in target_users}
                    admin_email_set = self._admin_email_set()
                    credential_service = self._credential_service(session=session)
                    for item in items:
                        user_id = int(item.get("user_id", 0))
                        target_user = user_by_id.get(user_id)
                        if target_user is None:
                            role = "member"
                            credential = {
                                "exchange": "UPBIT",
                                "has_credentials": False,
                                "is_valid": False,
                                "key_version": None,
                                "access_key_masked": None,
                                "access_key_fingerprint_prefix": None,
                                "updated_at_utc": None,
                            }
                        else:
                            role = "admin" if normalize_email(target_user.email) in admin_email_set else "member"
                            credential = credential_service.get_exchange_credential_status(user=target_user, exchange="UPBIT")

                        flags = item.setdefault("flags", {})
                        is_credential_invalid = bool((not credential.get("has_credentials")) or (not credential.get("is_valid")))
                        flags["is_credential_invalid"] = is_credential_invalid
                        flags["is_critical"] = bool(
                            flags.get("is_budget_blocked")
                            or flags.get("is_halted")
                            or is_credential_invalid
                        )
                        item["role"] = role
                        item["credential"] = credential

                    items.sort(
                        key=lambda row: (
                            (4 if row.get("flags", {}).get("is_budget_blocked") else 0)
                            + (2 if row.get("flags", {}).get("is_halted") else 0)
                            + (1 if row.get("flags", {}).get("is_credential_invalid") else 0),
                            row.get("activity", {}).get("recent_action_at_utc") or "",
                            int(row.get("user_id", 0)),
                        ),
                        reverse=True,
                    )
                    payload["items"] = items
                    payload["source"] = parsed.path
                    payload["sort"] = {
                        "strategy": "critical_then_recent_action",
                        "fields": [
                            "flags.is_budget_blocked",
                            "flags.is_halted",
                            "flags.is_credential_invalid",
                            "activity.recent_action_at_utc",
                        ],
                    }
                    self._write_json(200, payload)
                    self._record_audit_action(
                        session=session,
                        actor_user_id=admin_user.id,
                        action=ACTION_ADMIN_ACTION,
                        target_type="admin_route",
                        target_id=parsed.path,
                        metadata={"source": parsed.path, "method": "GET", "outcome": "allowed"},
                    )
                    return
                if parsed.path == "/api/admin/audit/logs":
                    admin_user = self._require_admin_user(session=session)
                    if admin_user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=admin_user,
                        scope=SCOPE_ADMIN,
                        source=parsed.path,
                    ) is None:
                        return
                    now_utc = datetime.now(timezone.utc)
                    to_utc = _parse_utc_datetime(params.get("to", [None])[0]) or now_utc
                    from_utc = _parse_utc_datetime(params.get("from", [None])[0]) or (to_utc - timedelta(days=7))
                    if from_utc > to_utc:
                        self._write_json(400, {"error": "invalid_date_range", "message": "from_must_be_before_to"})
                        return
                    if (to_utc - from_utc) > timedelta(days=31):
                        self._write_json(400, {"error": "invalid_date_range", "message": "max_range_days_31"})
                        return
                    query = AuditLogReadQuery(
                        actor_user_id=_parse_optional_positive_int(params.get("actor_user_id", [None])[0]),
                        target_user_id=_parse_optional_positive_int(params.get("target_user_id", [None])[0]),
                        action=(params.get("action", [None])[0] or None),
                        target_type=(params.get("target_type", [None])[0] or None),
                        from_utc=from_utc,
                        to_utc=to_utc,
                        success=_parse_success_filter(params.get("result", [None])[0] or params.get("success", [None])[0]),
                        limit=_parse_positive_int(params.get("limit", [None])[0], fallback=50, max_value=200),
                        offset=_parse_non_negative_int(params.get("offset", [None])[0], fallback=0, max_value=100000),
                    )
                    payload = AuditService(session=session).list_logs(query=query)
                    payload["source"] = parsed.path
                    payload["filters"] = {
                        "actor_user_id": query.actor_user_id,
                        "target_user_id": query.target_user_id,
                        "action": query.action,
                        "target_type": query.target_type,
                        "result": (
                            "success"
                            if query.success is True
                            else "failure"
                            if query.success is False
                            else "all"
                        ),
                        "from_utc": from_utc.isoformat().replace("+00:00", "Z"),
                        "to_utc": to_utc.isoformat().replace("+00:00", "Z"),
                    }
                    self._write_json(200, payload)
                    self._record_audit_action(
                        session=session,
                        actor_user_id=admin_user.id,
                        action=ACTION_ADMIN_ACTION,
                        target_type="admin_route",
                        target_id=parsed.path,
                        metadata={"source": parsed.path, "method": "GET", "outcome": "allowed"},
                    )
                    return
                parsed_admin_scope = self._parse_admin_user_scope_path(parsed.path)
                if parsed_admin_scope is not None:
                    admin_user = self._require_admin_user(session=session)
                    if admin_user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=admin_user,
                        scope=SCOPE_ADMIN,
                        source=parsed.path,
                    ) is None:
                        return

                    target_user_id, scope_path = parsed_admin_scope
                    target_user = session.get(User, target_user_id)
                    if target_user is None:
                        self._write_json(404, {"error": "not_found", "message": "user_not_found"})
                        return

                    scoped_service = OpsService(
                        session=session,
                        trade_mode=trade_mode,
                        scope_user_id=target_user_id,
                    )
                    if scope_path == "/credentials/upbit":
                        payload = self._credential_service(session=session).get_exchange_credential_status(
                            user=target_user,
                            exchange="UPBIT",
                        )
                        payload["user_id"] = target_user_id
                        payload["source"] = parsed.path
                        self._write_json(200, payload)
                    elif scope_path == "/orders":
                        state = params.get("state", [None])[0]
                        limit = _parse_positive_int(params.get("limit", [None])[0], fallback=50, max_value=500)
                        payload = scoped_service.list_orders(state=state, limit=limit)
                        payload["user_id"] = target_user_id
                        payload["source"] = parsed.path
                        self._write_json(200, payload)
                    elif scope_path == "/pnl/daily":
                        days = _parse_positive_int(params.get("days", [None])[0], fallback=30, max_value=365)
                        tz = params.get("tz", ["UTC"])[0]
                        payload = scoped_service.get_pnl_daily(days=days, tz=tz)
                        payload["user_id"] = target_user_id
                        payload["source"] = parsed.path
                        self._write_json(200, payload)
                    elif scope_path == "/metrics/trade":
                        limit = _parse_positive_int(params.get("limit", [None])[0], fallback=200, max_value=1000)
                        payload = scoped_service.list_trade_metrics(limit=limit)
                        payload["user_id"] = target_user_id
                        payload["source"] = parsed.path
                        self._write_json(200, payload)
                    elif scope_path == "/bot/status":
                        payload = self._admin_user_bot_status(
                            session=session,
                            target_user_id=target_user_id,
                            source=parsed.path,
                        )
                        self._write_json(200, payload)
                    else:
                        self._write_json(404, {"error": "not_found"})
                        return

                    self._record_audit_action(
                        session=session,
                        actor_user_id=admin_user.id,
                        action=ACTION_ADMIN_ACTION,
                        target_type="admin_route",
                        target_id=parsed.path,
                        metadata={
                            "source": parsed.path,
                            "method": "GET",
                            "outcome": "allowed",
                            "target_user_id": target_user_id,
                            "scope_path": scope_path,
                        },
                    )
                    return
                if parsed.path in {"/api/ops/summary", "/api/admin/summary"}:
                    admin_user = self._require_admin_user(session=session)
                    if admin_user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=admin_user,
                        scope=SCOPE_ADMIN,
                        source=parsed.path,
                    ) is None:
                        return
                    metrics_limit = _parse_positive_int(params.get("metrics_limit", [None])[0], fallback=200, max_value=1000)
                    needs_review_limit = _parse_positive_int(
                        params.get("needs_review_limit", [None])[0],
                        fallback=10,
                        max_value=100,
                    )
                    summary = service.get_summary(metrics_limit=metrics_limit, needs_review_limit=needs_review_limit)
                    summary["api_budget"] = self._current_budget_payload(
                        session=session,
                        user=admin_user,
                        scope=SCOPE_ADMIN,
                    )
                    self._write_json(
                        200,
                        summary,
                    )
                    self._record_audit_action(
                        session=session,
                        actor_user_id=admin_user.id,
                        action=ACTION_ADMIN_ACTION,
                        target_type="admin_route",
                        target_id=parsed.path,
                        metadata={"source": parsed.path, "method": "GET", "outcome": "allowed"},
                    )
                    return
                if parsed.path in {"/api/orders", "/api/admin/orders"}:
                    admin_user = self._require_admin_user(session=session)
                    if admin_user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=admin_user,
                        scope=SCOPE_ADMIN,
                        source=parsed.path,
                    ) is None:
                        return
                    state = params.get("state", [None])[0]
                    limit = _parse_positive_int(params.get("limit", [None])[0], fallback=50, max_value=500)
                    self._write_json(200, service.list_orders(state=state, limit=limit))
                    self._record_audit_action(
                        session=session,
                        actor_user_id=admin_user.id,
                        action=ACTION_ADMIN_ACTION,
                        target_type="admin_route",
                        target_id=parsed.path,
                        metadata={"source": parsed.path, "method": "GET", "outcome": "allowed"},
                    )
                    return
                if parsed.path in {"/api/pnl/daily", "/api/admin/pnl/daily"}:
                    admin_user = self._require_admin_user(session=session)
                    if admin_user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=admin_user,
                        scope=SCOPE_ADMIN,
                        source=parsed.path,
                    ) is None:
                        return
                    days = _parse_positive_int(params.get("days", [None])[0], fallback=30, max_value=365)
                    tz = params.get("tz", ["UTC"])[0]
                    self._write_json(200, service.get_pnl_daily(days=days, tz=tz))
                    self._record_audit_action(
                        session=session,
                        actor_user_id=admin_user.id,
                        action=ACTION_ADMIN_ACTION,
                        target_type="admin_route",
                        target_id=parsed.path,
                        metadata={"source": parsed.path, "method": "GET", "outcome": "allowed"},
                    )
                    return
                if parsed.path in {"/api/metrics/trade", "/api/admin/metrics/trade"}:
                    admin_user = self._require_admin_user(session=session)
                    if admin_user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=admin_user,
                        scope=SCOPE_ADMIN,
                        source=parsed.path,
                    ) is None:
                        return
                    limit = _parse_positive_int(params.get("limit", [None])[0], fallback=200, max_value=1000)
                    self._write_json(200, service.list_trade_metrics(limit=limit))
                    self._record_audit_action(
                        session=session,
                        actor_user_id=admin_user.id,
                        action=ACTION_ADMIN_ACTION,
                        target_type="admin_route",
                        target_id=parsed.path,
                        metadata={"source": parsed.path, "method": "GET", "outcome": "allowed"},
                    )
                    return
                self._write_json(404, {"error": "not_found"})
            except UserScopeError as exc:
                self._write_json(403, {"error": exc.code, "message": exc.message})
            except Exception as exc:
                self._handle_error(exc)
            finally:
                session.close()

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            session = session_factory()
            try:
                auth_service = AuthService(session=session)
                if parsed.path == "/api/auth/signup":
                    payload = self._read_json_body()
                    user = auth_service.signup(
                        email=str(payload.get("email", "")),
                        password=str(payload.get("password", "")),
                        display_name=payload.get("display_name"),
                    )
                    self._write_json(201, self._build_auth_payload(user=user))
                    return
                if parsed.path == "/api/auth/login":
                    payload = self._read_json_body()
                    user = auth_service.login(
                        email=str(payload.get("email", "")),
                        password=str(payload.get("password", "")),
                    )
                    self._write_json(200, self._build_auth_payload(user=user))
                    return
                if parsed.path == "/api/me/credentials/upbit":
                    user = self._require_authenticated_user(session=session)
                    if user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=user,
                        scope=SCOPE_ME,
                        source=parsed.path,
                    ) is None:
                        return
                    payload = self._read_json_body()
                    credential_service = self._credential_service(session=session)
                    status = credential_service.set_exchange_credentials(
                        user=user,
                        exchange="UPBIT",
                        access_key=str(payload.get("access_key", "")),
                        secret_key=str(payload.get("secret_key", "")),
                    )
                    self._record_audit_action(
                        session=session,
                        actor_user_id=user.id,
                        action=ACTION_CREDENTIAL_UPDATE,
                        target_type="user_exchange_credentials",
                        target_id=f"{user.id}:UPBIT",
                        metadata={
                            "exchange": "UPBIT",
                            "source": "/api/me/credentials/upbit",
                            "has_credentials": bool(status.get("has_credentials")),
                            "is_valid": bool(status.get("is_valid")),
                        },
                    )
                    self._write_json(200, status)
                    return
                if parsed.path == "/api/me/bot/start":
                    user = self._require_authenticated_user(session=session)
                    if user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=user,
                        scope=SCOPE_ME,
                        source=parsed.path,
                    ) is None:
                        return
                    me_service = MeReadService(
                        session=session,
                        trade_mode=trade_mode,
                        encryption_key=settings.ops_api_credentials_encryption_key,
                    )
                    result = me_service.start_bot(user=user)
                    self._record_audit_action(
                        session=session,
                        actor_user_id=user.id,
                        action=ACTION_BOT_START,
                        target_type="user_bot_runtime",
                        target_id=str(user.id),
                        metadata={
                            "source": "/api/me/bot/start",
                            "is_enabled": bool(result.get("is_enabled")),
                            "status": result.get("status"),
                        },
                    )
                    self._write_json(200, result)
                    return
                if parsed.path == "/api/me/bot/stop":
                    user = self._require_authenticated_user(session=session)
                    if user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=user,
                        scope=SCOPE_ME,
                        source=parsed.path,
                    ) is None:
                        return
                    me_service = MeReadService(
                        session=session,
                        trade_mode=trade_mode,
                        encryption_key=settings.ops_api_credentials_encryption_key,
                    )
                    result = me_service.stop_bot(user=user)
                    self._record_audit_action(
                        session=session,
                        actor_user_id=user.id,
                        action=ACTION_BOT_STOP,
                        target_type="user_bot_runtime",
                        target_id=str(user.id),
                        metadata={
                            "source": "/api/me/bot/stop",
                            "is_enabled": bool(result.get("is_enabled")),
                            "status": result.get("status"),
                        },
                    )
                    self._write_json(200, result)
                    return
                if parsed.path in {"/api/admin/credentials/rotate", "/api/ops/credentials/rotate"}:
                    admin_user = self._require_admin_user(session=session)
                    if admin_user is None:
                        return
                    if self._enforce_request_budget(
                        session=session,
                        user=admin_user,
                        scope=SCOPE_ADMIN,
                        source=parsed.path,
                    ) is None:
                        return
                    payload = self._read_json_body()
                    target_key_version = payload.get("target_key_version")
                    dry_run = bool(payload.get("dry_run", False))
                    rotate_result = self._credential_service(session=session).rotate_exchange_credentials(
                        exchange="UPBIT",
                        target_key_version=None if target_key_version is None else str(target_key_version),
                        dry_run=dry_run,
                    )
                    rotate_result["source"] = parsed.path
                    self._record_audit_action(
                        session=session,
                        actor_user_id=admin_user.id,
                        action=ACTION_ADMIN_ACTION,
                        target_type="admin_route",
                        target_id=parsed.path,
                        metadata={
                            "source": parsed.path,
                            "method": "POST",
                            "outcome": "allowed",
                            "dry_run": dry_run,
                            "target_key_version": rotate_result.get("target_key_version"),
                            "rotated": rotate_result.get("rotated"),
                            "failed": rotate_result.get("failed"),
                        },
                    )
                    self._write_json(200, rotate_result)
                    return
                self._write_json(404, {"error": "not_found"})
            except AuthValidationError as exc:
                self._write_json(400, {"error": exc.code, "message": exc.message})
            except AuthConflictError as exc:
                self._write_json(409, {"error": exc.code, "message": exc.message})
            except AuthCredentialsError as exc:
                self._write_json(401, {"error": exc.code, "message": exc.message})
            except CredentialValidationError as exc:
                self._write_json(400, {"error": exc.code, "message": exc.message})
            except CredentialRotationError as exc:
                self._write_json(400, {"error": exc.code, "message": exc.message})
            except UserScopeError as exc:
                self._write_json(403, {"error": exc.code, "message": exc.message})
            except ValueError as exc:
                if str(exc) == "invalid_json":
                    self._write_json(400, {"error": "invalid_json", "message": "request body must be valid JSON object"})
                    return
                self._handle_error(exc)
            except Exception as exc:
                self._handle_error(exc)
            finally:
                session.close()

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._write_cors_headers()
            self.end_headers()

        def log_message(self, format: str, *args) -> None:
            logger.info("ops_api_access %s", format % args)

    return OpsApiHandler


def serve_ops_http(
    *,
    host: str,
    port: int,
    session_factory: SessionFactory,
    trade_mode: str,
    allow_origin: str,
) -> None:
    handler_cls = create_ops_handler(
        session_factory=session_factory,
        trade_mode=trade_mode,
        allow_origin=allow_origin,
    )
    server = ThreadingHTTPServer((host, port), handler_cls)
    logger.info("ops_api_started host=%s port=%s trade_mode=%s", host, port, trade_mode)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("ops_api_stopped signal=keyboard_interrupt")
    finally:
        server.server_close()
