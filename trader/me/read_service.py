from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trader.auth.crypto import SecretCryptoError, decrypt_secret
from trader.data.models import BotConfig, User, UserExchangeCredential
from trader.ops.dto import iso_kst, iso_utc
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

    def get_bot_status(self, *, user: User) -> dict:
        self._assert_read_scope(user=user)
        summary = self.ops_service.get_summary(metrics_limit=1, needs_review_limit=1)
        config_row = self.session.get(BotConfig, 1)
        updated_at = config_row.updated_at if config_row is not None else None
        return {
            "mode": summary["trade_mode"],
            "status": summary["bot"]["status"],
            "is_enabled": bool(summary["bot"]["is_enabled"]),
            "daily_loss_basis": summary["config"]["daily_loss_basis"],
            "max_daily_loss_pct": summary["config"]["max_daily_loss_pct"],
            "target_exposure_pct": summary["config"]["target_exposure_pct"],
            "max_total_exposure_pct": summary["config"]["max_total_exposure_pct"],
            "max_per_market_exposure_pct": summary["config"]["max_per_market_exposure_pct"],
            "updated_at_utc": iso_utc(updated_at),
            "updated_at_kst": iso_kst(updated_at),
            "source": "/api/me/bot/status",
        }

    def start_bot(self, *, user: User) -> dict:
        self._assert_read_scope(user=user)
        payload = self.ops_service.set_bot_enabled(enabled=True)
        payload["source"] = "/api/me/bot/start"
        return payload

    def stop_bot(self, *, user: User) -> dict:
        self._assert_read_scope(user=user)
        payload = self.ops_service.set_bot_enabled(enabled=False)
        payload["source"] = "/api/me/bot/stop"
        return payload
