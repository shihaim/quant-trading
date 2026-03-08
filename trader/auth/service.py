from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.auth.passwords import hash_password, verify_password
from trader.data.models import User


class AuthError(ValueError):
    """Base auth domain error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class AuthValidationError(AuthError):
    """Invalid auth input."""


class AuthConflictError(AuthError):
    """Unique constraint style conflict."""


class AuthCredentialsError(AuthError):
    """Credential mismatch or disabled user."""


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _validate_email(email: str) -> None:
    if not email:
        raise AuthValidationError("email_required", "email is required")
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        raise AuthValidationError("invalid_email", "email format is invalid")


def _validate_password(password: str) -> None:
    if not password:
        raise AuthValidationError("password_required", "password is required")
    if len(password) < 8:
        raise AuthValidationError("weak_password", "password must be at least 8 characters")


def _normalize_display_name(display_name: str | None) -> str | None:
    if display_name is None:
        return None
    normalized = str(display_name).strip()
    if not normalized:
        return None
    if len(normalized) > 120:
        raise AuthValidationError("display_name_too_long", "display_name must be <= 120 characters")
    return normalized


def _iso_utc(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    normalized = ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def to_identity_payload(user: User, *, is_admin: bool = False) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": bool(is_admin),
        "display_name": user.display_name,
        "is_active": bool(user.is_active),
        "created_at_utc": _iso_utc(user.created_at),
        "updated_at_utc": _iso_utc(user.updated_at),
    }


class AuthService:
    """Signup/login and identity retrieval for V2 foundation."""

    def __init__(self, session: Session):
        self.session = session

    def signup(self, *, email: str, password: str, display_name: str | None = None) -> User:
        normalized_email = normalize_email(email)
        _validate_email(normalized_email)
        _validate_password(password)
        normalized_name = _normalize_display_name(display_name)

        existing = self.session.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()
        if existing is not None:
            raise AuthConflictError("email_already_exists", "email already registered")

        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            display_name=normalized_name,
            is_active=True,
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def login(self, *, email: str, password: str) -> User:
        normalized_email = normalize_email(email)
        _validate_email(normalized_email)
        if not password:
            raise AuthCredentialsError("invalid_credentials", "invalid credentials")

        user = self.session.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            raise AuthCredentialsError("invalid_credentials", "invalid credentials")
        if not user.is_active:
            raise AuthCredentialsError("user_disabled", "user is disabled")
        return user

