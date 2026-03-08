from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.data.models import UserApiBudget

SCOPE_ME = "ME"
SCOPE_ADMIN = "ADMIN"


def _normalize_scope(scope: str) -> str:
    normalized = str(scope or "").strip().upper()
    if normalized not in {SCOPE_ME, SCOPE_ADMIN}:
        raise ValueError("invalid_budget_scope")
    return normalized


def _normalize_window_seconds(window_seconds: int) -> int:
    return max(10, min(3600, int(window_seconds)))


def _normalize_limit(limit: int) -> int:
    return max(1, min(5000, int(limit)))


def _to_window_started_at(*, now: datetime, window_seconds: int) -> datetime:
    utc_now = now.astimezone(timezone.utc) if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    epoch = int(utc_now.timestamp())
    window_start_epoch = epoch - (epoch % window_seconds)
    return datetime.fromtimestamp(window_start_epoch, tz=timezone.utc)


def _ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class ApiBudgetSnapshot:
    user_id: int
    scope: str
    limit: int
    window_seconds: int
    window_started_at: datetime
    request_count: int
    blocked_count: int
    is_limited: bool
    retry_after_seconds: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.request_count)

    def to_payload(self) -> dict:
        window_end = self.window_started_at + timedelta(seconds=self.window_seconds)
        return {
            "scope": self.scope.lower(),
            "limit": self.limit,
            "window_seconds": self.window_seconds,
            "window_started_at_utc": self.window_started_at.isoformat().replace("+00:00", "Z"),
            "window_ends_at_utc": window_end.isoformat().replace("+00:00", "Z"),
            "request_count": self.request_count,
            "blocked_count": self.blocked_count,
            "remaining": self.remaining,
            "is_limited": self.is_limited,
            "retry_after_seconds": self.retry_after_seconds,
        }


class ApiBudgetService:
    """Persist and enforce fixed-window request budgets per user and scope."""

    def __init__(self, *, session: Session):
        self.session = session

    def consume(
        self,
        *,
        user_id: int,
        scope: str,
        limit: int,
        window_seconds: int,
        now: datetime | None = None,
    ) -> ApiBudgetSnapshot:
        checked_scope = _normalize_scope(scope)
        checked_limit = _normalize_limit(limit)
        checked_window = _normalize_window_seconds(window_seconds)
        at = _ensure_utc(now or datetime.now(timezone.utc))
        window_started_at = _to_window_started_at(now=at, window_seconds=checked_window)

        row = self._get_or_create_row(user_id=user_id, scope=checked_scope, window_seconds=checked_window)
        row_window_started_at = _ensure_utc(row.window_started_at)
        if row.window_seconds != checked_window or row_window_started_at != window_started_at:
            row.window_seconds = checked_window
            row.window_started_at = window_started_at
            row.request_count = 0
            row.blocked_count = 0

        retry_after = int((window_started_at + timedelta(seconds=checked_window) - at).total_seconds())
        if int(row.request_count or 0) >= checked_limit:
            row.blocked_count = int(row.blocked_count or 0) + 1
            self.session.commit()
            self.session.refresh(row)
            return ApiBudgetSnapshot(
                user_id=user_id,
                scope=checked_scope,
                limit=checked_limit,
                window_seconds=checked_window,
                window_started_at=_ensure_utc(row.window_started_at),
                request_count=int(row.request_count or 0),
                blocked_count=int(row.blocked_count or 0),
                is_limited=True,
                retry_after_seconds=max(1, retry_after),
            )

        row.request_count = int(row.request_count or 0) + 1
        self.session.commit()
        self.session.refresh(row)
        return ApiBudgetSnapshot(
            user_id=user_id,
            scope=checked_scope,
            limit=checked_limit,
            window_seconds=checked_window,
            window_started_at=_ensure_utc(row.window_started_at),
            request_count=int(row.request_count or 0),
            blocked_count=int(row.blocked_count or 0),
            is_limited=False,
            retry_after_seconds=max(1, retry_after),
        )

    def get_current(
        self,
        *,
        user_id: int,
        scope: str,
        limit: int,
        window_seconds: int,
        now: datetime | None = None,
    ) -> ApiBudgetSnapshot:
        checked_scope = _normalize_scope(scope)
        checked_limit = _normalize_limit(limit)
        checked_window = _normalize_window_seconds(window_seconds)
        at = _ensure_utc(now or datetime.now(timezone.utc))
        window_started_at = _to_window_started_at(now=at, window_seconds=checked_window)
        retry_after = int((window_started_at + timedelta(seconds=checked_window) - at).total_seconds())

        row = self._get_or_create_row(user_id=user_id, scope=checked_scope, window_seconds=checked_window)
        row_window_started_at = _ensure_utc(row.window_started_at)
        if row.window_seconds != checked_window or row_window_started_at != window_started_at:
            row.window_seconds = checked_window
            row.window_started_at = window_started_at
            row.request_count = 0
            row.blocked_count = 0
            self.session.commit()
            self.session.refresh(row)

        request_count = int(row.request_count or 0)
        return ApiBudgetSnapshot(
            user_id=user_id,
            scope=checked_scope,
            limit=checked_limit,
            window_seconds=checked_window,
            window_started_at=_ensure_utc(row.window_started_at),
            request_count=request_count,
            blocked_count=int(row.blocked_count or 0),
            is_limited=request_count >= checked_limit,
            retry_after_seconds=max(1, retry_after),
        )

    def _get_or_create_row(self, *, user_id: int, scope: str, window_seconds: int) -> UserApiBudget:
        row = self.session.execute(
            select(UserApiBudget).where(
                UserApiBudget.user_id == max(1, int(user_id)),
                UserApiBudget.scope == scope,
            )
        ).scalar_one_or_none()
        if row is not None:
            return row
        row = UserApiBudget(
            user_id=max(1, int(user_id)),
            scope=scope,
            window_seconds=window_seconds,
            request_count=0,
            blocked_count=0,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row
