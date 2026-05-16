from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.data.models import (
    BotConfig,
    TimeframeConfig,
    UserBotConfig,
    UserBotRuntime,
    UserRiskGuard,
)
from trader.utils.timeframes import SUPPORTED_TIMEFRAMES

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime config loaded from DB."""

    is_enabled: bool
    timeframe: str
    markets: list[str]
    max_daily_loss_pct: Decimal
    max_total_exposure_pct: Decimal
    max_per_market_exposure_pct: Decimal
    target_exposure_pct: Decimal = Decimal("0.10")
    daily_loss_basis: str = "TOTAL"
    min_rebalance_threshold_pct: Decimal = Decimal("0")
    min_order_krw_buffer: Decimal = Decimal("0")
    fill_timeout_sec_entry: int = 10
    fill_timeout_sec_exit: int = 4
    fill_timeout_sec_rebalance: int = 10
    max_reprice_attempts_entry: int = 2
    max_reprice_attempts_exit: int = 1
    max_reprice_attempts_rebalance: int = 1
    reprice_step_bps: int = 10
    slippage_budget_entry_pct: Decimal = Decimal("0.0005")
    slippage_budget_exit_pct: Decimal = Decimal("0.0020")
    slippage_budget_breach_halt_count: int = 0
    status_notify_interval_seconds: int = 14400
    max_weekly_loss_pct: Decimal = Decimal("0")
    max_monthly_loss_pct: Decimal = Decimal("0")
    cooldown_hours_on_halt: int = 0
    max_new_orders_per_day: int = 0
    max_orders_per_week: int = 0
    min_edge_pct: Decimal = Decimal("0")


@dataclass(frozen=True)
class RuntimeState:
    """Per-user runtime state snapshot."""

    user_id: int
    is_enabled: bool
    status: str
    consecutive_failures: int
    last_error: str | None
    halt_reason: str | None = None
    cooldown_until_utc: datetime | None = None
    halted_at_utc: datetime | None = None


@dataclass(frozen=True)
class RiskGuardState:
    """Per-user risk guard state snapshot."""

    user_id: int
    manual_halt: bool
    emergency_kill_switch: bool
    reason: str | None

    @property
    def is_halted(self) -> bool:
        return bool(self.manual_halt or self.emergency_kill_switch)


class ConfigRepo:
    def __init__(self, session: Session):
        self.session = session

    def load(self) -> RuntimeConfig:
        logger.debug("config_load start")
        row = self.session.execute(select(BotConfig).where(BotConfig.id == 1)).scalar_one_or_none()
        if row is None:
            row = BotConfig(id=1)
            self.session.add(row)
            self.session.commit()
            self.session.refresh(row)
            logger.info("config_init_created id=%s", row.id)

        cfg = self._build_runtime_config(row)
        logger.info(
            "config_loaded enabled=%s timeframe=%s markets=%s target_exposure_pct=%s daily_loss_basis=%s "
            "min_rebalance_threshold_pct=%s min_order_krw_buffer=%s",
            cfg.is_enabled,
            cfg.timeframe,
            cfg.markets,
            cfg.target_exposure_pct,
            cfg.daily_loss_basis,
            cfg.min_rebalance_threshold_pct,
            cfg.min_order_krw_buffer,
        )
        return cfg

    def load_for_user(self, user_id: int) -> RuntimeConfig:
        """Load user-scoped runtime config, creating a default user row when missing."""
        normalized_user_id = max(1, int(user_id))
        row = self.session.execute(
            select(UserBotConfig).where(UserBotConfig.user_id == normalized_user_id)
        ).scalar_one_or_none()
        if row is None:
            row = UserBotConfig(user_id=normalized_user_id)
            self.session.add(row)
            self.session.commit()
            self.session.refresh(row)
        return self._build_runtime_config(row)

    def get_runtime_state(self, user_id: int) -> RuntimeState:
        row = self._get_or_create_runtime_row(user_id=max(1, int(user_id)))
        return RuntimeState(
            user_id=row.user_id,
            is_enabled=bool(row.is_enabled),
            status=str(row.status or "IDLE"),
            consecutive_failures=int(row.consecutive_failures or 0),
            last_error=row.last_error,
            halt_reason=getattr(row, "halt_reason", None),
            cooldown_until_utc=getattr(row, "cooldown_until", None),
            halted_at_utc=getattr(row, "halted_at", None),
        )

    def set_runtime_enabled(self, *, user_id: int, enabled: bool) -> RuntimeState:
        row = self._get_or_create_runtime_row(user_id=max(1, int(user_id)))
        row.is_enabled = bool(enabled)
        if enabled:
            row.halt_reason = None
            row.cooldown_until = None
            row.halted_at = None
            if str(row.status or "").upper() == "HALTED":
                row.status = "IDLE"
        self.session.commit()
        self.session.refresh(row)
        return RuntimeState(
            user_id=row.user_id,
            is_enabled=bool(row.is_enabled),
            status=str(row.status or "IDLE"),
            consecutive_failures=int(row.consecutive_failures or 0),
            last_error=row.last_error,
            halt_reason=getattr(row, "halt_reason", None),
            cooldown_until_utc=getattr(row, "cooldown_until", None),
            halted_at_utc=getattr(row, "halted_at", None),
        )

    def get_risk_guard(self, user_id: int) -> RiskGuardState:
        row = self._get_or_create_risk_guard_row(user_id=max(1, int(user_id)))
        return RiskGuardState(
            user_id=row.user_id,
            manual_halt=bool(row.manual_halt),
            emergency_kill_switch=bool(row.emergency_kill_switch),
            reason=row.reason,
        )

    def _get_or_create_runtime_row(self, *, user_id: int) -> UserBotRuntime:
        row = self.session.execute(
            select(UserBotRuntime).where(UserBotRuntime.user_id == user_id)
        ).scalar_one_or_none()
        if row is not None:
            return row
        row = UserBotRuntime(user_id=user_id)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def _get_or_create_risk_guard_row(self, *, user_id: int) -> UserRiskGuard:
        row = self.session.execute(
            select(UserRiskGuard).where(UserRiskGuard.user_id == user_id)
        ).scalar_one_or_none()
        if row is not None:
            return row
        row = UserRiskGuard(user_id=user_id, manual_halt=False, emergency_kill_switch=False)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def _build_runtime_config(self, row: BotConfig | UserBotConfig) -> RuntimeConfig:
        active_timeframe = self.session.execute(
            select(TimeframeConfig)
            .where(TimeframeConfig.is_enabled.is_(True))
            .order_by(TimeframeConfig.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        timeframe = active_timeframe.timeframe if active_timeframe else row.timeframe
        if timeframe not in SUPPORTED_TIMEFRAMES:
            timeframe = "15m"
        markets = json.loads(row.markets_json or "[]")
        return RuntimeConfig(
            is_enabled=bool(row.is_enabled),
            timeframe=timeframe,
            markets=markets,
            max_daily_loss_pct=self._sanitize_decimal(row.max_daily_loss_pct, Decimal("0.02"), min_value=Decimal("0")),
            max_total_exposure_pct=self._sanitize_decimal(row.max_total_exposure_pct, Decimal("0.30"), min_value=Decimal("0")),
            max_per_market_exposure_pct=self._sanitize_decimal(
                row.max_per_market_exposure_pct,
                Decimal("0.10"),
                min_value=Decimal("0"),
            ),
            target_exposure_pct=self._sanitize_decimal(row.target_exposure_pct, Decimal("0.10"), min_value=Decimal("0"), max_value=Decimal("1")),
            daily_loss_basis=self._sanitize_daily_loss_basis(getattr(row, "daily_loss_basis", None)),
            min_rebalance_threshold_pct=self._sanitize_decimal(
                getattr(row, "min_rebalance_threshold_pct", None),
                Decimal("0.05"),
                min_value=Decimal("0"),
                max_value=Decimal("1"),
            ),
            min_order_krw_buffer=self._sanitize_decimal(
                getattr(row, "min_order_krw_buffer", None),
                Decimal("0"),
                min_value=Decimal("0"),
            ),
            fill_timeout_sec_entry=self._sanitize_int(getattr(row, "fill_timeout_sec_entry", None), 10, min_value=1, max_value=120),
            fill_timeout_sec_exit=self._sanitize_int(getattr(row, "fill_timeout_sec_exit", None), 4, min_value=1, max_value=120),
            fill_timeout_sec_rebalance=self._sanitize_int(
                getattr(row, "fill_timeout_sec_rebalance", None),
                10,
                min_value=1,
                max_value=120,
            ),
            max_reprice_attempts_entry=self._sanitize_int(
                getattr(row, "max_reprice_attempts_entry", None),
                2,
                min_value=1,
                max_value=10,
            ),
            max_reprice_attempts_exit=self._sanitize_int(
                getattr(row, "max_reprice_attempts_exit", None),
                1,
                min_value=1,
                max_value=10,
            ),
            max_reprice_attempts_rebalance=self._sanitize_int(
                getattr(row, "max_reprice_attempts_rebalance", None),
                1,
                min_value=1,
                max_value=10,
            ),
            reprice_step_bps=self._sanitize_int(getattr(row, "reprice_step_bps", None), 10, min_value=1, max_value=500),
            slippage_budget_entry_pct=self._sanitize_decimal(
                getattr(row, "slippage_budget_entry_pct", None),
                Decimal("0.0005"),
                min_value=Decimal("0"),
            ),
            slippage_budget_exit_pct=self._sanitize_decimal(
                getattr(row, "slippage_budget_exit_pct", None),
                Decimal("0.0020"),
                min_value=Decimal("0"),
            ),
            slippage_budget_breach_halt_count=self._sanitize_int(
                getattr(row, "slippage_budget_breach_halt_count", None),
                0,
                min_value=0,
                max_value=100,
            ),
            status_notify_interval_seconds=self._sanitize_int(
                getattr(row, "status_notify_interval_seconds", None),
                14400,
                min_value=300,
                max_value=86400,
            ),
            max_weekly_loss_pct=self._sanitize_decimal(
                getattr(row, "max_weekly_loss_pct", None),
                Decimal("0"),
                min_value=Decimal("0"),
                max_value=Decimal("1"),
            ),
            max_monthly_loss_pct=self._sanitize_decimal(
                getattr(row, "max_monthly_loss_pct", None),
                Decimal("0"),
                min_value=Decimal("0"),
                max_value=Decimal("1"),
            ),
            cooldown_hours_on_halt=self._sanitize_int(
                getattr(row, "cooldown_hours_on_halt", None),
                0,
                min_value=0,
                max_value=168,
            ),
            max_new_orders_per_day=self._sanitize_int(
                getattr(row, "max_new_orders_per_day", None),
                0,
                min_value=0,
                max_value=10000,
            ),
            max_orders_per_week=self._sanitize_int(
                getattr(row, "max_orders_per_week", None),
                0,
                min_value=0,
                max_value=70000,
            ),
            min_edge_pct=self._sanitize_decimal(
                getattr(row, "min_edge_pct", None),
                Decimal("0"),
                min_value=Decimal("0"),
                max_value=Decimal("1"),
            ),
        )

    @staticmethod
    def _sanitize_decimal(
        raw: Decimal | str | float | int | None,
        fallback: Decimal,
        min_value: Decimal | None = None,
        max_value: Decimal | None = None,
    ) -> Decimal:
        try:
            value = Decimal(str(raw))
        except Exception:
            return fallback
        if min_value is not None and value < min_value:
            return fallback
        if max_value is not None and value > max_value:
            return max_value
        return value

    @staticmethod
    def _sanitize_int(raw: int | str | None, fallback: int, min_value: int | None = None, max_value: int | None = None) -> int:
        try:
            value = int(raw)
        except Exception:
            return fallback
        if min_value is not None and value < min_value:
            return fallback
        if max_value is not None and value > max_value:
            return max_value
        return value

    @staticmethod
    def _sanitize_daily_loss_basis(raw: str | None) -> str:
        value = str(raw or "").strip().upper()
        if value in {"TOTAL", "REALIZED_ONLY"}:
            return value
        return "TOTAL"
