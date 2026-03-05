from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from trader.auth.tokens import TokenError, decode_access_token
from trader.data.models import User


@dataclass(frozen=True)
class AuthGuardResult:
    user: User | None
    error: str | None


def extract_bearer_token(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None
    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def authenticate_request(
    *,
    session: Session,
    authorization_header: str | None,
    secret: str,
) -> AuthGuardResult:
    token = extract_bearer_token(authorization_header)
    if not token:
        return AuthGuardResult(user=None, error="missing_token")

    try:
        claims = decode_access_token(token, secret=secret)
    except TokenError:
        return AuthGuardResult(user=None, error="invalid_token")

    user = session.get(User, claims.user_id)
    if user is None or not user.is_active:
        return AuthGuardResult(user=None, error="invalid_user")
    return AuthGuardResult(user=user, error=None)

