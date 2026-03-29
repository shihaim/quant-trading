from __future__ import annotations

from trader.auth.service import normalize_email
from trader.config.settings import settings


class AdminRoleResolver:
    """Resolve admin membership using DB role first, with allowlist fallback."""

    def __init__(self, *, allowlist_emails: list[str] | None = None):
        raw_allowlist = settings.ops_api_admin_emails if allowlist_emails is None else allowlist_emails
        self._allowlist = {
            normalize_email(str(email))
            for email in raw_allowlist
            if str(email or "").strip()
        }

    def is_admin(self, *, user) -> bool:
        return bool(getattr(user, "is_admin", False)) or normalize_email(str(getattr(user, "email", ""))) in self._allowlist

    def role(self, *, user) -> str:
        return "admin" if self.is_admin(user=user) else "member"
