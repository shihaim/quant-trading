from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from trader.auth.credentials import CredentialValidationError, UserCredentialService
from trader.config.config_repo import ConfigRepo, RuntimeConfig
from trader.config.settings import settings
from trader.data.candle_service import CandleService
from trader.data.models import Order, User, UserBotRuntime, UserExchangeCredential, UserRiskGuard
from trader.exchange.upbit_client import UpbitClient
from trader.notify.telegram import TelegramNotifier
from trader.trading.execution import ExecutionEngine
from trader.trading.health import HealthSnapshot, format_health_status
from trader.trading.order_policy import OrderIntent, OrderPolicyConfig
from trader.trading.order_states import LOCAL_OPEN_STATES
from trader.trading.paper_execution import PaperExecutionEngine
from trader.trading.pnl import PnLService
from trader.trading.portfolio import PortfolioService
from trader.trading.reconcile import ReconcileService
from trader.trading.risk import RiskEngine, should_skip_rebalance
from trader.trading.strategy import EmaCrossStrategy
from trader.utils.timeframes import next_run_time


logger = logging.getLogger(__name__)


@dataclass
class SchedulerState:
    """Scheduler loop state."""

    runtime_config: RuntimeConfig
    next_run_at: datetime
    last_config_reload_at: datetime
    next_status_notify_at: datetime


class TradingScheduler:
    def __init__(
        self,
        session: Session,
        *,
        user_id: int | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        notifier: TelegramNotifier | None = None,
    ):
        self.session = session
        self.config_repo = ConfigRepo(session)
        self.user_id = max(1, int(user_id if user_id is not None else self.config_repo.resolve_owner_user_id()))
        self.trade_mode = settings.trade_mode.upper()
        self.is_paper = self.trade_mode == "PAPER"
        self.allowed_markets = set(settings.allowlist_markets) if settings.enforce_market_allowlist else set()
        resolved_access_key = settings.upbit_access_key if access_key is None else access_key
        resolved_secret_key = settings.upbit_secret_key if secret_key is None else secret_key
        if self.trade_mode in {"REAL", "TEST", "SHADOW"} and (not resolved_access_key or not resolved_secret_key):
            raise ValueError("UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY are required in REAL/TEST/SHADOW mode.")

        self.upbit = UpbitClient(
            base_url=settings.upbit_base_url,
            access_key=resolved_access_key,
            secret_key=resolved_secret_key,
            retry_max=settings.order_retry_max,
            retry_backoff_seconds=settings.order_retry_backoff_seconds,
        )
        self.candle_service = CandleService(session, self.upbit)
        self.strategy = EmaCrossStrategy()
        self.risk = RiskEngine()
        self.portfolio = PortfolioService(session)
        self.pnl = PnLService(session)
        if self.is_paper:
            self.execution = PaperExecutionEngine(session, fee_rate=Decimal(str(settings.default_fee_rate)))
            self.reconcile = None
            self.portfolio.get_or_create_paper_wallet(
                Decimal(str(settings.paper_initial_cash_krw)),
                user_id=self.user_id,
            )
        else:
            self.execution = ExecutionEngine(
                session,
                self.upbit,
                max_submit_retries=settings.order_retry_max,
                retry_backoff_seconds=settings.order_retry_backoff_seconds,
                trade_mode=self.trade_mode,
                allowed_markets=self.allowed_markets,
            )
            self.reconcile = ReconcileService(session, self.upbit, self.portfolio, self.execution, user_id=self.user_id)
        self.notifier = notifier or TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
        self._last_success_loop_at: datetime | None = None
        self._last_exposure_pct = Decimal("0")
        self._last_daily_pnl_pct = Decimal("0")
        logger.info(
            "scheduler_init user_id=%s mode=%s is_paper=%s allowed_markets=%s poll_interval=%s reload_interval=%s",
            self.user_id,
            self.trade_mode,
            self.is_paper,
            sorted(self.allowed_markets) if self.allowed_markets else [],
            settings.poll_interval_seconds,
            settings.config_reload_seconds,
        )

    def _reload_config(self, state: SchedulerState, now: datetime) -> SchedulerState:
        if (now - state.last_config_reload_at).total_seconds() < settings.config_reload_seconds:
            return state
        logger.info("scheduler_config_reload start now=%s", now.isoformat())
        cfg = self.config_repo.load_for_user(self.user_id)
        next_at = state.next_run_at
        if cfg.timeframe != state.runtime_config.timeframe:
            next_at = next_run_time(now, cfg.timeframe)
            self.notifier.send(f"timeframe changed: {state.runtime_config.timeframe} -> {cfg.timeframe}")
            logger.info(
                "scheduler_timeframe_changed old=%s new=%s next_run_at=%s",
                state.runtime_config.timeframe,
                cfg.timeframe,
                next_at.isoformat(),
            )
        logger.info(
            "scheduler_config_reload done enabled=%s timeframe=%s markets=%s daily_loss_basis=%s next_run_at=%s",
            cfg.is_enabled,
            cfg.timeframe,
            cfg.markets,
            cfg.daily_loss_basis,
            next_at.isoformat(),
        )
        return SchedulerState(
            runtime_config=cfg,
            next_run_at=next_at,
            last_config_reload_at=now,
            next_status_notify_at=state.next_status_notify_at,
        )

    def _run_once(self, cfg: RuntimeConfig) -> None:
        logger.info(
            "scheduler_run_once start timeframe=%s markets=%s daily_loss_basis=%s",
            cfg.timeframe,
            cfg.markets,
            cfg.daily_loss_basis,
        )
        self.strategy.set_buy_target_exposure_pct(cfg.target_exposure_pct)
        logger.info("scheduler_strategy_target_exposure buy_target_exposure_pct=%s", cfg.target_exposure_pct)

        market_to_candles: dict[str, list] = {}
        mark_prices: dict[str, Decimal] = {}
        for market in cfg.markets:
            if self.allowed_markets and market not in self.allowed_markets:
                self.notifier.send(
                    f"order_error market={market} mode={self.trade_mode} error_class=VALIDATION_ERROR "
                    f"action=skip message=market_not_allowlisted"
                )
                logger.warning("scheduler_market_skipped market=%s reason=market_not_allowlisted", market)
                continue
            self.candle_service.ensure_backfill(market, cfg.timeframe, settings.min_strategy_candles)
            self.candle_service.upsert_latest_complete(market, cfg.timeframe)
            candles = self.candle_service.recent_candles(market, cfg.timeframe, settings.min_strategy_candles)
            market_to_candles[market] = candles
            if candles:
                mark_prices[market] = Decimal(candles[-1].close)
            else:
                logger.warning("scheduler_no_candles market=%s timeframe=%s", market, cfg.timeframe)

        if self.is_paper:
            wallet = self.portfolio.get_or_create_paper_wallet(
                Decimal(str(settings.paper_initial_cash_krw)),
                user_id=self.user_id,
            )
            snapshot = self.portfolio.snapshot(mark_prices=mark_prices, cash_krw=Decimal(wallet.cash_krw), user_id=self.user_id)
        else:
            if self.reconcile is None:
                logger.warning("scheduler_reconcile_missing mode=%s", self.trade_mode)
                return
            snapshot = self.reconcile.reconcile_all(markets=cfg.markets, mark_prices=mark_prices)

        total_equity = snapshot.total_equity
        self._last_exposure_pct = (snapshot.market_value / total_equity) if total_equity > 0 else Decimal("0")
        logger.info(
            "scheduler_snapshot equity=%s cash=%s market_value=%s",
            snapshot.total_equity,
            snapshot.cash_krw,
            snapshot.market_value,
        )

        if self.is_paper:
            unrealized_total = self.portfolio.update_unrealized_pnl(mark_prices=mark_prices, user_id=self.user_id)
        else:
            unrealized_total = self.portfolio.total_unrealized_pnl(markets=cfg.markets, user_id=self.user_id)
        realized_total = self.portfolio.total_realized_pnl(markets=cfg.markets, user_id=self.user_id)

        daily_snapshot = self.pnl.update_daily_snapshot(
            current_equity=total_equity,
            realized_pnl=realized_total,
            unrealized_pnl=unrealized_total,
            user_id=self.user_id,
        )
        daily_pnl_abs, daily_pnl_pct = self.pnl.resolve_daily_pnl_pct(
            snapshot=daily_snapshot,
            basis=cfg.daily_loss_basis,
            current_realized_pnl=realized_total,
        )
        self._last_daily_pnl_pct = daily_pnl_pct
        logger.info(
            "scheduler_daily_pnl basis=%s date_utc=%s start_equity=%s start_realized_pnl=%s last_equity=%s "
            "daily_pnl_abs=%s daily_pnl_pct=%s realized_pnl=%s unrealized_pnl=%s",
            cfg.daily_loss_basis,
            daily_snapshot.date_utc,
            daily_snapshot.start_equity,
            daily_snapshot.start_realized_pnl,
            daily_snapshot.last_equity,
            daily_pnl_abs,
            daily_pnl_pct,
            daily_snapshot.realized_pnl,
            daily_snapshot.unrealized_pnl,
        )

        for market in cfg.markets:
            candles = market_to_candles.get(market, [])
            if not candles:
                continue
            position = self.portfolio.get_position(market, user_id=self.user_id)
            signal = self.strategy.evaluate(candles, position)
            decision = self.risk.evaluate(signal=signal, config=cfg, daily_pnl_pct=daily_pnl_pct)
            if decision.halted:
                self.notifier.send(f"HALT {market}: {decision.reason}")
                logger.warning("scheduler_halt market=%s reason=%s", market, decision.reason)
                continue

            close_price = Decimal(candles[-1].close)
            target_notional = total_equity * decision.target_exposure_pct
            target_qty = target_notional / close_price if close_price > 0 else Decimal("0")
            current_qty = Decimal(position.qty) if position else Decimal("0")
            current_notional = current_qty * close_price
            current_exposure_pct = (current_notional / total_equity) if total_equity > 0 else Decimal("0")

            if should_skip_rebalance(
                current_exposure_pct=current_exposure_pct,
                target_exposure_pct=decision.target_exposure_pct,
                min_rebalance_threshold_pct=cfg.min_rebalance_threshold_pct,
            ):
                delta_pct = abs(decision.target_exposure_pct - current_exposure_pct)
                logger.info(
                    "scheduler_order_skipped market=%s reason=min_rebalance_threshold rebalance_delta_pct=%s threshold=%s",
                    market,
                    delta_pct,
                    cfg.min_rebalance_threshold_pct,
                )
                continue

            order_notional = abs(target_qty - current_qty) * close_price
            min_notional = Decimal("5000") + max(Decimal("0"), cfg.min_order_krw_buffer)
            if order_notional < min_notional:
                logger.info(
                    "scheduler_order_skipped market=%s reason=min_order_buffer order_notional=%s min_notional=%s",
                    market,
                    order_notional,
                    min_notional,
                )
                continue

            candle_key = candles[-1].candle_time_utc.isoformat()
            idempotency_key = f"{cfg.timeframe}-{market}-{candle_key}"
            logger.info(
                "scheduler_signal market=%s action=%s reason=%s current_qty=%s target_qty=%s close=%s",
                market,
                signal.action,
                signal.reason,
                current_qty,
                target_qty,
                close_price,
            )

            policy_cfg = OrderPolicyConfig(
                fill_timeout_sec_entry=cfg.fill_timeout_sec_entry,
                fill_timeout_sec_exit=cfg.fill_timeout_sec_exit,
                fill_timeout_sec_rebalance=cfg.fill_timeout_sec_rebalance,
                max_reprice_attempts_entry=cfg.max_reprice_attempts_entry,
                max_reprice_attempts_exit=cfg.max_reprice_attempts_exit,
                max_reprice_attempts_rebalance=cfg.max_reprice_attempts_rebalance,
                reprice_step_bps=cfg.reprice_step_bps,
                allow_market_fallback_on_exit=False,
            )

            order = self.execution.place_target_order(
                user_id=self.user_id,
                market=market,
                current_qty=current_qty,
                target_qty=target_qty,
                ref_price=close_price,
                idempotency_key=idempotency_key,
                current_exposure_pct=current_exposure_pct,
                target_exposure_pct=decision.target_exposure_pct,
                policy_config=policy_cfg,
                min_order_krw_buffer=cfg.min_order_krw_buffer,
            )
            if not order:
                logger.info("scheduler_order_skipped market=%s reason=no_delta", market)
                continue

            self.execution.sync_order(order)
            applied = self.portfolio.apply_unapplied_fills(
                order,
                use_paper_wallet=self.is_paper,
                initial_cash_krw=Decimal(str(settings.paper_initial_cash_krw)),
            )

            self._handle_slippage_budget(cfg, order)

            if order.error_class:
                action = "manual_review" if order.state in {"ERROR", "ERROR_NEEDS_REVIEW"} else "skip"
                self.notifier.send(
                    f"order_error market={order.market} side={order.side} price={order.requested_price} "
                    f"volume={order.requested_volume} mode={self.trade_mode} error_class={order.error_class} "
                    f"action={action} message={order.last_error}"
                )
                logger.warning(
                    "scheduler_order_error market=%s state=%s error_class=%s message=%s",
                    order.market,
                    order.state,
                    order.error_class,
                    order.last_error,
                )
            else:
                self.notifier.send(
                    f"order {order.market} {order.side} {order.requested_volume}@{order.requested_price} "
                    f"state={order.state} mode={self.trade_mode} fills_applied={applied}"
                )
                logger.info(
                    "scheduler_order_ok market=%s side=%s price=%s volume=%s state=%s fills_applied=%s",
                    order.market,
                    order.side,
                    order.requested_price,
                    order.requested_volume,
                    order.state,
                    applied,
                )

        self._last_success_loop_at = datetime.now(timezone.utc)
        logger.info("scheduler_run_once done timeframe=%s", cfg.timeframe)

    def _handle_slippage_budget(self, cfg: RuntimeConfig, order) -> None:
        if not hasattr(self.execution, "latest_trade_metric"):
            return
        metric = self.execution.latest_trade_metric(order.id)
        if metric is None or metric.slippage_pct is None:
            return

        budget = cfg.slippage_budget_exit_pct if metric.intent == OrderIntent.EXIT.value else cfg.slippage_budget_entry_pct
        slippage_pct = Decimal(metric.slippage_pct)
        if slippage_pct <= budget:
            return

        self.notifier.send(
            f"slippage_budget_breach market={order.market} side={order.side} intent={metric.intent} "
            f"slippage_pct={slippage_pct} budget={budget} order_id={order.id}"
        )
        logger.warning(
            "scheduler_slippage_budget_breach order_id=%s market=%s intent=%s slippage_pct=%s budget=%s",
            order.id,
            order.market,
            metric.intent,
            slippage_pct,
            budget,
        )

        if cfg.slippage_budget_breach_halt_count <= 0:
            return
        since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        breach_count = self.execution.count_slippage_breaches_since(
            user_id=self.user_id,
            since=since,
            entry_budget_pct=cfg.slippage_budget_entry_pct,
            exit_budget_pct=cfg.slippage_budget_exit_pct,
        )
        if breach_count < cfg.slippage_budget_breach_halt_count:
            return

        runtime = self.config_repo.set_runtime_enabled(user_id=self.user_id, enabled=False)
        if not runtime.is_enabled:
            self.notifier.send(
                f"HALT user={self.user_id} by slippage budget breaches count={breach_count} "
                f"threshold={cfg.slippage_budget_breach_halt_count}"
            )
            logger.error(
                "scheduler_auto_halt_by_slippage user_id=%s breaches=%s threshold=%s",
                self.user_id,
                breach_count,
                cfg.slippage_budget_breach_halt_count,
            )

    def _build_health_snapshot(self, cfg: RuntimeConfig) -> HealthSnapshot:
        now = datetime.now(timezone.utc)
        since = now - timedelta(minutes=15)
        error_count = (
            self.session.scalar(
                select(func.count()).select_from(Order).where(
                    Order.user_id == self.user_id,
                    Order.updated_at >= since,
                    Order.error_class.is_not(None),
                )
            )
            or 0
        )
        rate_limit_count = (
            self.session.scalar(
                select(func.count()).select_from(Order).where(
                    Order.user_id == self.user_id,
                    Order.updated_at >= since,
                    Order.error_class == "RATE_LIMIT",
                )
            )
            or 0
        )
        open_orders = (
            self.session.scalar(
                select(func.count()).select_from(Order).where(Order.user_id == self.user_id, Order.state.in_(LOCAL_OPEN_STATES))
            )
            or 0
        )
        return HealthSnapshot(
            last_loop_at=self._last_success_loop_at,
            error_count_15m=int(error_count),
            rate_limit_15m=int(rate_limit_count),
            open_orders=int(open_orders),
            exposure_pct=self._last_exposure_pct,
            daily_pnl_pct=self._last_daily_pnl_pct,
            is_halted=not cfg.is_enabled,
        )

    def _send_periodic_status(self, cfg: RuntimeConfig) -> None:
        snapshot = self._build_health_snapshot(cfg)
        msg = format_health_status(snapshot)
        logger.info("scheduler_status %s", msg)
        self.notifier.send(msg)

    def _current_risk_guard_reason(self) -> str | None:
        getter = getattr(self.config_repo, "get_risk_guard", None)
        if not callable(getter):
            return None
        guard = getter(self.user_id)
        if not getattr(guard, "is_halted", False):
            return None
        if getattr(guard, "manual_halt", False):
            return "manual_halt"
        if getattr(guard, "emergency_kill_switch", False):
            return "emergency_kill_switch"
        return "risk_guard"

    def _run_due_tick(self, state: SchedulerState, now: datetime) -> SchedulerState:
        logger.info(
            "scheduler_tick_triggered now=%s next_run_at=%s",
            now.isoformat(),
            state.next_run_at.isoformat(),
        )
        halt_reason = self._current_risk_guard_reason()
        if halt_reason:
            self.notifier.send(f"HALT user={self.user_id} by risk guard ({halt_reason})")
            logger.warning("scheduler_tick_skipped user_id=%s reason=%s", self.user_id, halt_reason)
            state.next_run_at = next_run_time(now, state.runtime_config.timeframe)
            logger.info("scheduler_next_run_scheduled next_run_at=%s", state.next_run_at.isoformat())
            return state
        try:
            self._run_once(state.runtime_config)
        except Exception:
            logger.exception(
                "scheduler_run_once_failed timeframe=%s markets=%s",
                state.runtime_config.timeframe,
                state.runtime_config.markets,
            )
        state.next_run_at = next_run_time(now, state.runtime_config.timeframe)
        logger.info("scheduler_next_run_scheduled next_run_at=%s", state.next_run_at.isoformat())
        return state

    def run_forever(self) -> None:
        now = datetime.now(timezone.utc)
        cfg = self.config_repo.load_for_user(self.user_id)
        state = SchedulerState(
            runtime_config=cfg,
            next_run_at=next_run_time(now, cfg.timeframe),
            last_config_reload_at=now,
            next_status_notify_at=now + timedelta(seconds=max(300, cfg.status_notify_interval_seconds)),
        )
        self.notifier.send(f"trading scheduler started mode={self.trade_mode}")
        logger.info(
            "scheduler_started mode=%s timeframe=%s markets=%s next_run_at=%s",
            self.trade_mode,
            cfg.timeframe,
            cfg.markets,
            state.next_run_at.isoformat(),
        )
        try:
            while True:
                now = datetime.now(timezone.utc)
                state = self._reload_config(state, now)
                if now >= state.next_status_notify_at:
                    self._send_periodic_status(state.runtime_config)
                    state.next_status_notify_at = now + timedelta(
                        seconds=max(300, state.runtime_config.status_notify_interval_seconds)
                    )
                if now >= state.next_run_at:
                    state = self._run_due_tick(state, now)
                time.sleep(settings.poll_interval_seconds)
        finally:
            logger.info("scheduler_stopping")
            self.upbit.close()


class MultiUserTradingScheduler:
    """Coordinator that executes user-scoped scheduler ticks with failure isolation."""

    def __init__(self, *, session_factory: Callable[[], Session]):
        self.session_factory = session_factory
        self.trade_mode = settings.trade_mode.upper()
        self.is_paper = self.trade_mode == "PAPER"
        self.notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
        self._states: dict[int, SchedulerState] = {}
        self._locks: dict[int, threading.Lock] = {}
        logger.info(
            "multi_user_scheduler_init mode=%s is_paper=%s poll_interval=%s reload_interval=%s",
            self.trade_mode,
            self.is_paper,
            settings.poll_interval_seconds,
            settings.config_reload_seconds,
        )

    def _list_active_user_ids(self) -> list[int]:
        session = self.session_factory()
        try:
            stmt = (
                select(User.id)
                .outerjoin(UserBotRuntime, UserBotRuntime.user_id == User.id)
                .outerjoin(UserRiskGuard, UserRiskGuard.user_id == User.id)
                .where(
                    User.is_active.is_(True),
                    or_(UserBotRuntime.user_id.is_(None), UserBotRuntime.is_enabled.is_(True)),
                    or_(
                        UserRiskGuard.user_id.is_(None),
                        and_(
                            UserRiskGuard.manual_halt.is_(False),
                            UserRiskGuard.emergency_kill_switch.is_(False),
                        ),
                    ),
                )
            )
            if not self.is_paper:
                stmt = stmt.join(
                    UserExchangeCredential,
                    and_(
                        UserExchangeCredential.user_id == User.id,
                        UserExchangeCredential.exchange == "UPBIT",
                    ),
                )
            return [int(user_id) for user_id in session.scalars(stmt.order_by(User.id.asc())).all()]
        finally:
            session.close()

    def _load_config(self, user_id: int) -> RuntimeConfig:
        session = self.session_factory()
        try:
            return ConfigRepo(session).load_for_user(user_id)
        finally:
            session.close()

    def _load_risk_guard(self, user_id: int):
        session = self.session_factory()
        try:
            return ConfigRepo(session).get_risk_guard(user_id)
        finally:
            session.close()

    def _load_user_credentials(self, user_id: int) -> tuple[str, str]:
        session = self.session_factory()
        try:
            service = UserCredentialService(
                session=session,
                encryption_key=settings.ops_api_credentials_encryption_key,
                active_key_version=settings.ops_api_credentials_active_key_version,
                keyring_json=settings.ops_api_credentials_keyring_json,
            )
            return service.get_exchange_credentials_by_user_id(user_id=user_id, exchange="UPBIT")
        except CredentialValidationError as exc:
            raise ValueError(exc.message) from exc
        finally:
            session.close()

    def _update_runtime(
        self,
        *,
        user_id: int,
        status: str,
        now: datetime,
        last_error: str | None = None,
        reset_failures: bool = False,
        increment_failures: bool = False,
    ) -> None:
        session = self.session_factory()
        try:
            row = session.execute(select(UserBotRuntime).where(UserBotRuntime.user_id == user_id)).scalar_one_or_none()
            if row is None:
                row = UserBotRuntime(user_id=user_id)
                session.add(row)
                session.flush()
            row.status = status
            row.last_tick_at = now
            row.last_error = None if last_error is None else str(last_error)[:2000]
            if reset_failures:
                row.consecutive_failures = 0
            elif increment_failures:
                row.consecutive_failures = int(row.consecutive_failures or 0) + 1
            session.commit()
        finally:
            session.close()

    def _ensure_state(self, user_id: int, now: datetime) -> SchedulerState:
        state = self._states.get(user_id)
        if state is None:
            cfg = self._load_config(user_id)
            state = SchedulerState(
                runtime_config=cfg,
                next_run_at=next_run_time(now, cfg.timeframe),
                last_config_reload_at=now,
                next_status_notify_at=now + timedelta(seconds=max(300, cfg.status_notify_interval_seconds)),
            )
            self._states[user_id] = state
            return state

        if (now - state.last_config_reload_at).total_seconds() < settings.config_reload_seconds:
            return state

        cfg = self._load_config(user_id)
        next_at = state.next_run_at
        if cfg.timeframe != state.runtime_config.timeframe:
            next_at = next_run_time(now, cfg.timeframe)
            self.notifier.send(f"user={user_id} timeframe changed: {state.runtime_config.timeframe} -> {cfg.timeframe}")
        state.runtime_config = cfg
        state.next_run_at = next_at
        state.last_config_reload_at = now
        return state

    def _notify_runtime_status(self, user_id: int) -> None:
        session = self.session_factory()
        try:
            row = session.execute(select(UserBotRuntime).where(UserBotRuntime.user_id == user_id)).scalar_one_or_none()
            if row is None:
                return
            self.notifier.send(
                f"user={user_id} runtime status={row.status} failures={int(row.consecutive_failures or 0)}"
            )
        finally:
            session.close()

    def _run_user_tick(self, user_id: int, cfg: RuntimeConfig, now: datetime) -> None:
        lock = self._locks.setdefault(user_id, threading.Lock())
        if not lock.acquire(blocking=False):
            logger.warning("multi_user_scheduler_tick_skipped user_id=%s reason=lock_busy", user_id)
            return

        worker: TradingScheduler | None = None
        session: Session | None = None
        try:
            guard = self._load_risk_guard(user_id)
            if guard.is_halted:
                reason = "manual_halt" if guard.manual_halt else "emergency_kill_switch"
                self._update_runtime(
                    user_id=user_id,
                    status="HALTED",
                    now=now,
                    last_error=f"risk_guard:{reason}",
                )
                logger.warning(
                    "multi_user_scheduler_tick_skipped user_id=%s reason=%s",
                    user_id,
                    reason,
                )
                return
            self._update_runtime(user_id=user_id, status="RUNNING", now=now, last_error=None)
            access_key = ""
            secret_key = ""
            if not self.is_paper:
                access_key, secret_key = self._load_user_credentials(user_id)

            session = self.session_factory()
            worker = TradingScheduler(
                session=session,
                user_id=user_id,
                access_key=access_key,
                secret_key=secret_key,
                notifier=self.notifier,
            )
            worker._run_once(cfg)
            self._update_runtime(
                user_id=user_id,
                status="IDLE",
                now=datetime.now(timezone.utc),
                last_error=None,
                reset_failures=True,
            )
        except Exception as exc:
            self._update_runtime(
                user_id=user_id,
                status="ERROR",
                now=datetime.now(timezone.utc),
                last_error=str(exc),
                increment_failures=True,
            )
            logger.exception("multi_user_scheduler_tick_failed user_id=%s", user_id)
        finally:
            if worker is not None:
                worker.upbit.close()
            if session is not None:
                session.close()
            lock.release()

    def run_forever(self) -> None:
        self.notifier.send(f"trading scheduler started mode={self.trade_mode} multi_user=true")
        logger.info("multi_user_scheduler_started mode=%s", self.trade_mode)
        try:
            while True:
                now = datetime.now(timezone.utc)
                active_user_ids = self._list_active_user_ids()
                active_set = set(active_user_ids)
                stale_user_ids = [user_id for user_id in self._states if user_id not in active_set]
                for stale_user_id in stale_user_ids:
                    self._states.pop(stale_user_id, None)
                    self._locks.pop(stale_user_id, None)

                for user_id in active_user_ids:
                    state = self._ensure_state(user_id, now)
                    if now >= state.next_status_notify_at:
                        self._notify_runtime_status(user_id)
                        state.next_status_notify_at = now + timedelta(
                            seconds=max(300, state.runtime_config.status_notify_interval_seconds)
                        )
                    if now >= state.next_run_at:
                        self._run_user_tick(user_id, state.runtime_config, now)
                        state.next_run_at = next_run_time(now, state.runtime_config.timeframe)

                time.sleep(settings.poll_interval_seconds)
        finally:
            logger.info("multi_user_scheduler_stopping")
