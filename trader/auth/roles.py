from __future__ import annotations

class AdminRoleResolver:
    """Resolve admin membership from the DB-backed user role."""

    def __init__(self, *, allowlist_emails: list[str] | None = None):
        self._deprecated_allowlist_emails = allowlist_emails

    def is_admin(self, *, user) -> bool:
        return bool(getattr(user, "is_admin", False))

    def role(self, *, user) -> str:
        return "admin" if self.is_admin(user=user) else "member"
