from __future__ import annotations

class AdminRoleResolver:
    """Resolve admin membership from DB-backed user role."""

    def is_admin(self, *, user) -> bool:
        return bool(getattr(user, "is_admin", False))

    def role(self, *, user) -> str:
        return "admin" if self.is_admin(user=user) else "member"
