from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.auth.credentials import CredentialValidationError, UserCredentialService
from trader.config.settings import settings
from trader.config.config_repo import ConfigRepo
from trader.data.models import User, UserBotRuntime, UserExchangeCredential
from trader.ops.dto import iso_kst, iso_utc
from trader.ops.service import OpsService


class UserScopeError(ValueError):
    """User-scoped read access error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class MeReadService:
    """Authenticated user-scoped read APIs."""

    def __init__(self, *, session: Session, trade_mode: str, encryption_key: str):
        self.session = session
        self.trade_mode = trade_mode
        self.encryption_key = encryption_key
        self.config_repo = ConfigRepo(session)

    def _ops_for_user(self, *, user_id: int) -> OpsService:
        return OpsService(session=self.session, trade_mode=self.trade_mode, scope_user_id=user_id)

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
        service = UserCredentialService(
            session=self.session,
            encryption_key=self.encryption_key,
            active_key_version=settings.ops_api_credentials_active_key_version,
            keyring_json=settings.ops_api_credentials_keyring_json,
        )
        try:
            service.get_exchange_credentials_by_user_id(user_id=user.id, exchange="UPBIT")
        except CredentialValidationError as exc:
            raise UserScopeError(exc.code, exc.message) from exc

    def list_orders(self, *, user: User, state: str | None = None, limit: int = 50) -> dict:
        self._assert_user_credential_ready(user=user)
        return self._ops_for_user(user_id=user.id).list_orders(state=state, limit=limit)

    def get_pnl_daily(self, *, user: User, days: int = 30, tz: str = "UTC") -> dict:
        self._assert_user_credential_ready(user=user)
        return self._ops_for_user(user_id=user.id).get_pnl_daily(days=days, tz=tz)

    def list_trade_metrics(self, *, user: User, limit: int = 200) -> dict:
        self._assert_user_credential_ready(user=user)
        return self._ops_for_user(user_id=user.id).list_trade_metrics(limit=limit)

    def get_bot_status(self, *, user: User) -> dict:
        self._assert_user_credential_ready(user=user)
        cfg = self.config_repo.load_for_user(user.id)
        runtime = self.config_repo.get_runtime_state(user.id)
        runtime_row = self.session.execute(
            select(UserBotRuntime).where(UserBotRuntime.user_id == user.id)
        ).scalar_one_or_none()
        updated_at = runtime_row.updated_at if runtime_row is not None else None
        return {
            "mode": self.trade_mode,
            "status": runtime.status,
            "is_enabled": bool(runtime.is_enabled),
            "halt_reason": runtime.halt_reason,
            "halted_at_utc": iso_utc(runtime.halted_at_utc),
            "halted_at_kst": iso_kst(runtime.halted_at_utc),
            "cooldown_until_utc": iso_utc(runtime.cooldown_until_utc),
            "cooldown_until_kst": iso_kst(runtime.cooldown_until_utc),
            "daily_loss_basis": cfg.daily_loss_basis,
            "max_daily_loss_pct": float(cfg.max_daily_loss_pct),
            "max_weekly_loss_pct": float(cfg.max_weekly_loss_pct),
            "max_monthly_loss_pct": float(cfg.max_monthly_loss_pct),
            "cooldown_hours_on_halt": int(cfg.cooldown_hours_on_halt),
            "max_new_orders_per_day": int(cfg.max_new_orders_per_day),
            "max_orders_per_week": int(cfg.max_orders_per_week),
            "min_edge_pct": float(cfg.min_edge_pct),
            "target_exposure_pct": float(cfg.target_exposure_pct),
            "max_total_exposure_pct": float(cfg.max_total_exposure_pct),
            "max_per_market_exposure_pct": float(cfg.max_per_market_exposure_pct),
            "updated_at_utc": iso_utc(updated_at),
            "updated_at_kst": iso_kst(updated_at),
            "source": "/api/me/bot/status",
        }

    def start_bot(self, *, user: User) -> dict:
        self._assert_user_credential_ready(user=user)
        runtime_before = self.config_repo.get_runtime_state(user.id)
        now_utc = datetime.now(timezone.utc)
        if runtime_before.cooldown_until_utc is not None and runtime_before.cooldown_until_utc > now_utc:
            raise UserScopeError(
                "cooldown_active",
                f"cooldown_active_until:{iso_utc(runtime_before.cooldown_until_utc)}",
            )
        runtime = self.config_repo.set_runtime_enabled(user_id=user.id, enabled=True)
        runtime_row = self.session.execute(
            select(UserBotRuntime).where(UserBotRuntime.user_id == user.id)
        ).scalar_one_or_none()
        updated_at = runtime_row.updated_at if runtime_row is not None else None
        return {
            "is_enabled": bool(runtime.is_enabled),
            "status": runtime.status,
            "halt_reason": runtime.halt_reason,
            "cooldown_until_utc": iso_utc(runtime.cooldown_until_utc),
            "cooldown_until_kst": iso_kst(runtime.cooldown_until_utc),
            "updated_at_utc": iso_utc(updated_at),
            "updated_at_kst": iso_kst(updated_at),
            "source": "/api/me/bot/start",
        }

    def stop_bot(self, *, user: User) -> dict:
        self._assert_user_credential_ready(user=user)
        runtime = self.config_repo.set_runtime_enabled(user_id=user.id, enabled=False)
        runtime_row = self.session.execute(
            select(UserBotRuntime).where(UserBotRuntime.user_id == user.id)
        ).scalar_one_or_none()
        updated_at = runtime_row.updated_at if runtime_row is not None else None
        return {
            "is_enabled": bool(runtime.is_enabled),
            "status": runtime.status,
            "halt_reason": runtime.halt_reason,
            "cooldown_until_utc": iso_utc(runtime.cooldown_until_utc),
            "cooldown_until_kst": iso_kst(runtime.cooldown_until_utc),
            "updated_at_utc": iso_utc(updated_at),
            "updated_at_kst": iso_kst(updated_at),
            "source": "/api/me/bot/stop",
        }
