from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trader.auth.crypto import SecretCryptoError, decrypt_secret
from trader.data.models import User, UserExchangeCredential
from trader.ops.service import OpsService


class UserScopeError(ValueError):
    """User-scoped read access error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _scope_payload(*, user: User, owner_user_id: int) -> dict:
    return {
        "mode": "legacy_single_bot_owner_bridge",
        "user_id": user.id,
        "owner_user_id": owner_user_id,
    }


class MeReadService:
    """Authenticated user-scoped read APIs with legacy single-bot bridge."""

    def __init__(self, *, session: Session, trade_mode: str, encryption_key: str):
        self.session = session
        self.trade_mode = trade_mode
        self.encryption_key = encryption_key
        self.ops_service = OpsService(session=session, trade_mode=trade_mode)

    def _load_upbit_credential(self, *, user_id: int) -> UserExchangeCredential | None:
        return self.session.execute(
            select(UserExchangeCredential).where(
                UserExchangeCredential.user_id == user_id,
                UserExchangeCredential.exchange == "UPBIT",
            )
        ).scalar_one_or_none()

    def _assert_user_credential_ready(self, *, user: User) -> None:
        row = self._load_upbit_credential(user_id=user.id)
        if row is None:
            raise UserScopeError("credentials_required", "upbit credentials are required")
        try:
            decrypt_secret(row.access_key_encrypted, encryption_key=self.encryption_key)
            decrypt_secret(row.secret_key_encrypted, encryption_key=self.encryption_key)
        except SecretCryptoError as exc:
            raise UserScopeError("credentials_invalid", "stored credentials are invalid") from exc

    def _resolve_legacy_owner_user_id(self) -> int:
        owner_user_id = self.session.scalar(
            select(func.min(UserExchangeCredential.user_id)).where(UserExchangeCredential.exchange == "UPBIT")
        )
        if owner_user_id is None:
            raise UserScopeError("credentials_required", "upbit credentials are required")
        return int(owner_user_id)

    def _assert_read_scope(self, *, user: User) -> int:
        self._assert_user_credential_ready(user=user)
        owner_user_id = self._resolve_legacy_owner_user_id()
        if user.id != owner_user_id:
            raise UserScopeError(
                "no_data_scope",
                "no readable data scope for this user in current legacy bridge mode",
            )
        return owner_user_id

    def list_orders(self, *, user: User, state: str | None = None, limit: int = 50) -> dict:
        owner_user_id = self._assert_read_scope(user=user)
        payload = self.ops_service.list_orders(state=state, limit=limit)
        payload["scope"] = _scope_payload(user=user, owner_user_id=owner_user_id)
        return payload

    def get_pnl_daily(self, *, user: User, days: int = 30, tz: str = "UTC") -> dict:
        owner_user_id = self._assert_read_scope(user=user)
        payload = self.ops_service.get_pnl_daily(days=days, tz=tz)
        payload["scope"] = _scope_payload(user=user, owner_user_id=owner_user_id)
        return payload

    def list_trade_metrics(self, *, user: User, limit: int = 200) -> dict:
        owner_user_id = self._assert_read_scope(user=user)
        payload = self.ops_service.list_trade_metrics(limit=limit)
        payload["scope"] = _scope_payload(user=user, owner_user_id=owner_user_id)
        return payload

