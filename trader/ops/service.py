from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from math import ceil

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from trader.config.config_repo import ConfigRepo, RuntimeConfig
from trader.data.models import DailyEquity, Order, TradeMetric, UserBotRuntime
from trader.ops.dto import (
    ensure_utc,
    iso_kst,
    iso_utc,
    to_decimal,
    to_float,
    to_order_item,
    to_trade_metric_list_item,
    to_trade_metric_summary_item,
)

IN_FLIGHT_STATES = {"NEW", "SENT", "WAIT"}
REVIEW_STATE = "ERROR_NEEDS_REVIEW"


def _safe_ratio(num: Decimal, den: Decimal) -> Decimal:
    if den <= 0:
        return Decimal("0")
    return num / den


def _percentile_95(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = max(0, ceil(len(ordered) * Decimal("0.95")) - 1)
    return ordered[int(idx)]


class OpsService:
    """Aggregate operation-focused API payloads from the local DB."""

    def __init__(self, session: Session, trade_mode: str, scope_user_id: int | None = None):
        self.session = session
        self.trade_mode = trade_mode.upper()
        self.config_repo = ConfigRepo(session)
        if scope_user_id is None:
            self.owner_user_id = self.config_repo.resolve_owner_user_id()
        else:
            self.owner_user_id = max(1, int(scope_user_id))

    def list_orders(self, state: str | None = None, limit: int = 50) -> dict:
        q = (
            select(Order)
            .options(selectinload(Order.attempts))
            .where(Order.user_id == self.owner_user_id)
            .order_by(Order.updated_at.desc())
            .limit(max(1, min(500, limit)))
        )
        if state:
            q = q.where(Order.state == state)
        rows = self.session.execute(q).scalars().all()
        return {"count": len(rows), "items": [to_order_item(row) for row in rows]}

    def get_pnl_daily(self, days: int = 30, tz: str = "UTC") -> dict:
        normalized_tz = (tz or "UTC").upper()
        normalized_days = max(1, min(365, days))
        rows = (
            self.session.execute(
                select(DailyEquity)
                .where(DailyEquity.user_id == self.owner_user_id)
                .order_by(DailyEquity.date_utc.desc())
                .limit(normalized_days)
            )
            .scalars()
            .all()
        )
        items = []
        for row in rows:
            date_value = row.date_utc.isoformat()
            if normalized_tz == "KST":
                date_value = (
                    datetime.combine(row.date_utc, datetime.min.time(), tzinfo=timezone.utc)
                    .astimezone(timezone(timedelta(hours=9)))
                    .date()
                    .isoformat()
                )
            realized_daily_abs = to_decimal(row.realized_pnl) - to_decimal(row.start_realized_pnl)
            realized_daily_pct = _safe_ratio(realized_daily_abs, to_decimal(row.start_equity))
            items.append(
                {
                    "date": date_value,
                    "start_equity": to_float(row.start_equity),
                    "last_equity": to_float(row.last_equity),
                    "realized_pnl": to_float(row.realized_pnl),
                    "unrealized_pnl": to_float(row.unrealized_pnl),
                    "daily_pnl_abs": to_float(row.daily_pnl_abs),
                    "daily_pnl_pct": to_float(row.daily_pnl_pct),
                    "start_realized_pnl": to_float(row.start_realized_pnl),
                    "realized_daily_abs": to_float(realized_daily_abs),
                    "realized_daily_pct": to_float(realized_daily_pct),
                    "updated_at_utc": iso_utc(row.updated_at),
                    "updated_at_kst": iso_kst(row.updated_at),
                }
            )
        return {"tz": normalized_tz, "days": normalized_days, "items": items}

    def list_trade_metrics(self, limit: int = 200) -> dict:
        normalized_limit = max(1, min(1000, limit))
        rows = (
            self.session.execute(
                select(TradeMetric, Order.market, Order.side)
                .join(Order, TradeMetric.order_id == Order.id)
                .where(Order.user_id == self.owner_user_id)
                .order_by(TradeMetric.created_at.desc())
                .limit(normalized_limit)
            )
            .all()
        )
        items = [to_trade_metric_list_item(metric, market, side) for metric, market, side in rows]
        return {"count": len(items), "limit": normalized_limit, "items": items}

    def get_summary(self, metrics_limit: int = 200, needs_review_limit: int = 10) -> dict:
        now_utc = datetime.now(timezone.utc)
        cfg = self.config_repo.load_for_user(self.owner_user_id)
        runtime_state = self.config_repo.get_runtime_state(self.owner_user_id)
        runtime_row = self.session.execute(
            select(UserBotRuntime).where(UserBotRuntime.user_id == self.owner_user_id)
        ).scalar_one_or_none()
        today = self._today_pnl_snapshot(cfg, now_utc.date())
        orders = self._orders_snapshot(needs_review_limit=needs_review_limit)
        execution = self._execution_quality_snapshot(cfg=cfg, now_utc=now_utc, limit=metrics_limit)
        daily_breach_count = self._count_breach_since(
            since=now_utc.replace(hour=0, minute=0, second=0, microsecond=0),
            entry_budget=cfg.slippage_budget_entry_pct,
            exit_budget=cfg.slippage_budget_exit_pct,
        )
        status, halt = self._resolve_status(
            cfg=cfg,
            runtime_enabled=runtime_state.is_enabled,
            today=today,
            daily_breach_count=daily_breach_count,
            runtime_updated_at=runtime_row.updated_at if runtime_row is not None else None,
        )
        last_tick = self._last_tick_utc()
        return {
            "server_time_utc": iso_utc(now_utc),
            "server_time_kst": iso_kst(now_utc),
            "trade_mode": self.trade_mode,
            "bot": {
                "is_enabled": bool(runtime_state.is_enabled),
                "status": status,
                "last_tick_utc": iso_utc(last_tick),
                "last_tick_kst": iso_kst(last_tick),
            },
            "halt": halt,
            "config": {
                "timeframe": cfg.timeframe,
                "markets": cfg.markets,
                "daily_loss_basis": cfg.daily_loss_basis,
                "max_daily_loss_pct": to_float(cfg.max_daily_loss_pct),
                "target_exposure_pct": to_float(cfg.target_exposure_pct),
                "max_total_exposure_pct": to_float(cfg.max_total_exposure_pct),
                "max_per_market_exposure_pct": to_float(cfg.max_per_market_exposure_pct),
                "min_rebalance_threshold_pct": to_float(cfg.min_rebalance_threshold_pct),
                "min_order_krw_buffer": to_float(cfg.min_order_krw_buffer),
                "fill_timeout_sec_entry": cfg.fill_timeout_sec_entry,
                "fill_timeout_sec_exit": cfg.fill_timeout_sec_exit,
                "fill_timeout_sec_rebalance": cfg.fill_timeout_sec_rebalance,
                "max_reprice_attempts_entry": cfg.max_reprice_attempts_entry,
                "max_reprice_attempts_exit": cfg.max_reprice_attempts_exit,
                "max_reprice_attempts_rebalance": cfg.max_reprice_attempts_rebalance,
                "reprice_step_bps": cfg.reprice_step_bps,
                "slippage_budget_entry_pct": to_float(cfg.slippage_budget_entry_pct),
                "slippage_budget_exit_pct": to_float(cfg.slippage_budget_exit_pct),
                "slippage_budget_breach_halt_count": cfg.slippage_budget_breach_halt_count,
                "status_notify_interval_seconds": cfg.status_notify_interval_seconds,
                "updated_at_utc": iso_utc(runtime_row.updated_at if runtime_row else None),
            },
            "today_pnl": today,
            "orders": orders,
            "execution_quality": execution,
        }

    def _today_pnl_snapshot(self, cfg: RuntimeConfig, today_utc: date) -> dict:
        row = self.session.get(DailyEquity, (self.owner_user_id, today_utc))
        if row is None:
            halt_threshold = -abs(to_decimal(cfg.max_daily_loss_pct))
            return {
                "date_utc": today_utc.isoformat(),
                "start_equity": 0.0,
                "last_equity": 0.0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "daily_pnl_abs": 0.0,
                "daily_pnl_pct": 0.0,
                "start_realized_pnl": 0.0,
                "realized_daily_abs": 0.0,
                "realized_daily_pct": 0.0,
                "basis_used": cfg.daily_loss_basis,
                "halt_threshold_pct": to_float(halt_threshold),
            }

        start_equity = to_decimal(row.start_equity)
        start_realized = to_decimal(row.start_realized_pnl)
        realized = to_decimal(row.realized_pnl)
        realized_daily_abs = realized - start_realized
        realized_daily_pct = _safe_ratio(realized_daily_abs, start_equity)

        total_daily_abs = to_decimal(row.daily_pnl_abs)
        total_daily_pct = to_decimal(row.daily_pnl_pct)
        basis = cfg.daily_loss_basis
        daily_abs = realized_daily_abs if basis == "REALIZED_ONLY" else total_daily_abs
        daily_pct = realized_daily_pct if basis == "REALIZED_ONLY" else total_daily_pct
        halt_threshold = -abs(to_decimal(cfg.max_daily_loss_pct))
        return {
            "date_utc": row.date_utc.isoformat(),
            "start_equity": to_float(row.start_equity),
            "last_equity": to_float(row.last_equity),
            "realized_pnl": to_float(row.realized_pnl),
            "unrealized_pnl": to_float(row.unrealized_pnl),
            "daily_pnl_abs": to_float(daily_abs),
            "daily_pnl_pct": to_float(daily_pct),
            "start_realized_pnl": to_float(row.start_realized_pnl),
            "realized_daily_abs": to_float(realized_daily_abs),
            "realized_daily_pct": to_float(realized_daily_pct),
            "basis_used": basis,
            "halt_threshold_pct": to_float(halt_threshold),
        }

    def _orders_snapshot(self, needs_review_limit: int) -> dict:
        grouped = self.session.execute(
            select(Order.state, func.count())
            .where(Order.user_id == self.owner_user_id)
            .group_by(Order.state)
        ).all()
        by_state = {state: int(count) for state, count in grouped}
        needs_review = (
            self.session.execute(
                select(Order)
                .options(selectinload(Order.attempts))
                .where(Order.user_id == self.owner_user_id, Order.state == REVIEW_STATE)
                .order_by(Order.updated_at.desc())
                .limit(max(1, min(100, needs_review_limit)))
            )
            .scalars()
            .all()
        )
        return {
            "counts": {
                REVIEW_STATE: by_state.get(REVIEW_STATE, 0),
                "OPEN": by_state.get("OPEN", 0),
                "PARTIAL": by_state.get("PARTIAL", 0),
                "IN_FLIGHT": sum(by_state.get(state, 0) for state in IN_FLIGHT_STATES),
            },
            "needs_review_top": [to_order_item(row) for row in needs_review],
        }

    def _execution_quality_snapshot(self, cfg: RuntimeConfig, now_utc: datetime, limit: int) -> dict:
        normalized_limit = max(1, min(1000, limit))
        rows = (
            self.session.execute(
                select(TradeMetric, Order.market, Order.side)
                .join(Order, TradeMetric.order_id == Order.id)
                .where(Order.user_id == self.owner_user_id)
                .order_by(TradeMetric.created_at.desc())
                .limit(normalized_limit)
            )
            .all()
        )
        slippages = [to_decimal(metric.slippage_pct) for metric, _, _ in rows if metric.slippage_pct is not None]
        fill_times = [metric.time_to_fill_ms for metric, _, _ in rows if metric.time_to_fill_ms is not None]
        partial_counts = [metric.partial_fill_count for metric, _, _ in rows]

        avg_slippage = (sum(slippages, Decimal("0")) / Decimal(len(slippages))) if slippages else None
        p95_slippage = _percentile_95(slippages)
        avg_time = (sum(fill_times) / len(fill_times)) if fill_times else None
        avg_partial = (sum(partial_counts) / len(partial_counts)) if partial_counts else None

        since_24h = now_utc - timedelta(hours=24)
        breach_count_24h = self._count_breach_since(
            since=since_24h,
            entry_budget=cfg.slippage_budget_entry_pct,
            exit_budget=cfg.slippage_budget_exit_pct,
        )

        recent = [to_trade_metric_summary_item(metric, market, side) for metric, market, side in rows]

        from_utc = ensure_utc(rows[-1][0].created_at) if rows else since_24h
        to_utc = ensure_utc(rows[0][0].created_at) if rows else now_utc
        return {
            "window": {
                "limit": normalized_limit,
                "from_utc": iso_utc(from_utc),
                "to_utc": iso_utc(to_utc),
            },
            "kpi": {
                "avg_slippage_pct": to_float(avg_slippage) if avg_slippage is not None else None,
                "p95_slippage_pct": to_float(p95_slippage) if p95_slippage is not None else None,
                "avg_time_to_fill_ms": avg_time,
                "avg_partial_fill_count": avg_partial,
            },
            "recent": recent,
            "budget": {
                "entry_pct": to_float(cfg.slippage_budget_entry_pct),
                "exit_pct": to_float(cfg.slippage_budget_exit_pct),
                "breach_halt_count": cfg.slippage_budget_breach_halt_count,
                "breach_count_24h": breach_count_24h,
            },
        }

    def _count_breach_since(self, since: datetime, entry_budget: Decimal, exit_budget: Decimal) -> int:
        conditions = or_(
            and_(TradeMetric.intent == "EXIT", TradeMetric.slippage_pct > exit_budget),
            and_(or_(TradeMetric.intent.is_(None), TradeMetric.intent != "EXIT"), TradeMetric.slippage_pct > entry_budget),
        )
        result = (
            self.session.scalar(
                select(func.count())
                .select_from(TradeMetric)
                .join(Order, TradeMetric.order_id == Order.id)
                .where(
                    Order.user_id == self.owner_user_id,
                    TradeMetric.created_at >= since,
                    TradeMetric.slippage_pct.is_not(None),
                    conditions,
                )
            )
            or 0
        )
        return int(result)

    def _resolve_status(
        self,
        cfg: RuntimeConfig,
        runtime_enabled: bool,
        today: dict,
        daily_breach_count: int,
        runtime_updated_at: datetime | None,
    ) -> tuple[str, dict]:
        halt_reason: str | None = None
        effective_enabled = bool(runtime_enabled) and bool(cfg.is_enabled)
        if not effective_enabled:
            if today["daily_pnl_pct"] <= today["halt_threshold_pct"]:
                halt_reason = "daily_loss_limit"
            elif cfg.slippage_budget_breach_halt_count > 0 and daily_breach_count >= cfg.slippage_budget_breach_halt_count:
                halt_reason = "auto_halt_by_slippage"

        status = "RUNNING"
        if not effective_enabled:
            status = "HALTED" if halt_reason else "DISABLED"
        halt = {
            "is_halted": status == "HALTED",
            "reason": halt_reason,
            "triggered_at_utc": iso_utc(runtime_updated_at),
            "message": "bot disabled by risk guardrail" if halt_reason else None,
        }
        return status, halt

    def _last_tick_utc(self) -> datetime | None:
        latest_order = ensure_utc(
            self.session.scalar(select(func.max(Order.updated_at)).where(Order.user_id == self.owner_user_id))
        )
        latest_metric = ensure_utc(
            self.session.scalar(
                select(func.max(TradeMetric.created_at))
                .join(Order, TradeMetric.order_id == Order.id)
                .where(Order.user_id == self.owner_user_id)
            )
        )
        latest_equity = ensure_utc(
            self.session.scalar(
                select(func.max(DailyEquity.updated_at)).where(DailyEquity.user_id == self.owner_user_id)
            )
        )
        candidates = [ts for ts in [latest_order, latest_metric, latest_equity] if ts is not None]
        if not candidates:
            return None
        return max(candidates)
