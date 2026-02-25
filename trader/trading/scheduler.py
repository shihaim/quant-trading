from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from trader.config.config_repo import ConfigRepo, RuntimeConfig
from trader.config.settings import settings
from trader.data.candle_service import CandleService
from trader.exchange.upbit_client import UpbitClient
from trader.notify.telegram import TelegramNotifier
from trader.trading.execution import ExecutionEngine
from trader.trading.paper_execution import PaperExecutionEngine
from trader.trading.pnl import PnLService
from trader.trading.portfolio import PortfolioService
from trader.trading.reconcile import ReconcileService
from trader.trading.risk import RiskEngine
from trader.trading.strategy import EmaCrossStrategy
from trader.utils.timeframes import next_run_time


logger = logging.getLogger(__name__)


@dataclass
class SchedulerState:
    """스케줄러 루프가 유지하는 실행 상태."""

    runtime_config: RuntimeConfig
    next_run_at: datetime
    last_config_reload_at: datetime


class TradingScheduler:
    def __init__(self, session: Session):
        """모드(real/paper)에 맞는 구성 요소를 초기화한다."""
        self.session = session
        self.config_repo = ConfigRepo(session)
        self.trade_mode = settings.trade_mode.upper()
        self.is_paper = self.trade_mode == "PAPER"
        self.allowed_markets = set(settings.allowlist_markets) if settings.enforce_market_allowlist else set()
        if self.trade_mode in {"REAL", "TEST", "SHADOW"} and (
            not settings.upbit_access_key or not settings.upbit_secret_key
        ):
            raise ValueError("UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY are required in REAL/TEST/SHADOW mode.")
        self.upbit = UpbitClient(
            base_url=settings.upbit_base_url,
            access_key=settings.upbit_access_key,
            secret_key=settings.upbit_secret_key,
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
            self.portfolio.get_or_create_paper_wallet(Decimal(str(settings.paper_initial_cash_krw)))
        else:
            self.execution = ExecutionEngine(
                session,
                self.upbit,
                max_submit_retries=settings.order_retry_max,
                retry_backoff_seconds=settings.order_retry_backoff_seconds,
                trade_mode=self.trade_mode,
                allowed_markets=self.allowed_markets,
            )
            self.reconcile = ReconcileService(session, self.upbit, self.portfolio, self.execution)
        self.notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
        logger.info(
            "scheduler_init mode=%s is_paper=%s allowed_markets=%s poll_interval=%s reload_interval=%s",
            self.trade_mode,
            self.is_paper,
            sorted(self.allowed_markets) if self.allowed_markets else [],
            settings.poll_interval_seconds,
            settings.config_reload_seconds,
        )

    def _reload_config(self, state: SchedulerState, now: datetime) -> SchedulerState:
        """주기적으로 설정을 다시 읽고 다음 실행 시각을 갱신한다."""
        if (now - state.last_config_reload_at).total_seconds() < settings.config_reload_seconds:
            return state
        logger.info("scheduler_config_reload start now=%s", now.isoformat())
        cfg = self.config_repo.load()
        next_at = state.next_run_at
        if cfg.timeframe != state.runtime_config.timeframe:
            # Re-align schedule when timeframe changes at runtime.
            next_at = next_run_time(now, cfg.timeframe)
            self.notifier.send(f"timeframe changed: {state.runtime_config.timeframe} -> {cfg.timeframe}")
            logger.info(
                "scheduler_timeframe_changed old=%s new=%s next_run_at=%s",
                state.runtime_config.timeframe,
                cfg.timeframe,
                next_at.isoformat(),
            )
        logger.info(
            "scheduler_config_reload done enabled=%s timeframe=%s markets=%s next_run_at=%s",
            cfg.is_enabled,
            cfg.timeframe,
            cfg.markets,
            next_at.isoformat(),
        )
        return SchedulerState(runtime_config=cfg, next_run_at=next_at, last_config_reload_at=now)

    def _run_once(self, cfg: RuntimeConfig) -> None:
        """한 번의 봉 마감 사이클에서 데이터/신호/주문/반영을 수행한다."""
        logger.info("scheduler_run_once start timeframe=%s markets=%s", cfg.timeframe, cfg.markets)
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
            wallet = self.portfolio.get_or_create_paper_wallet(Decimal(str(settings.paper_initial_cash_krw)))
            snapshot = self.portfolio.snapshot(mark_prices=mark_prices, cash_krw=Decimal(wallet.cash_krw))
        else:
            if self.reconcile is None:
                logger.warning("scheduler_reconcile_missing mode=%s", self.trade_mode)
                return
            snapshot = self.reconcile.reconcile_all(markets=cfg.markets, mark_prices=mark_prices)
        total_equity = snapshot.total_equity
        logger.info(
            "scheduler_snapshot equity=%s cash=%s market_value=%s",
            snapshot.total_equity,
            snapshot.cash_krw,
            snapshot.market_value,
        )
        if self.is_paper:
            unrealized_total = self.portfolio.update_unrealized_pnl(mark_prices=mark_prices)
        else:
            unrealized_total = self.portfolio.total_unrealized_pnl(markets=cfg.markets)
        realized_total = self.portfolio.total_realized_pnl(markets=cfg.markets)
        daily_snapshot = self.pnl.update_daily_snapshot(
            current_equity=total_equity,
            realized_pnl=realized_total,
            unrealized_pnl=unrealized_total,
        )
        daily_pnl_pct = Decimal(daily_snapshot.daily_pnl_pct)
        logger.info(
            "scheduler_daily_pnl date_utc=%s start_equity=%s last_equity=%s daily_pnl_abs=%s daily_pnl_pct=%s "
            "realized_pnl=%s unrealized_pnl=%s",
            daily_snapshot.date_utc,
            daily_snapshot.start_equity,
            daily_snapshot.last_equity,
            daily_snapshot.daily_pnl_abs,
            daily_snapshot.daily_pnl_pct,
            daily_snapshot.realized_pnl,
            daily_snapshot.unrealized_pnl,
        )
        for market in cfg.markets:
            candles = market_to_candles.get(market, [])
            if not candles:
                continue
            position = self.portfolio.get_position(market)
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
            order = self.execution.place_target_order(
                market=market,
                current_qty=current_qty,
                target_qty=target_qty,
                ref_price=close_price,
                idempotency_key=idempotency_key,
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
        logger.info("scheduler_run_once done timeframe=%s", cfg.timeframe)

    def run_forever(self) -> None:
        """중단될 때까지 스케줄러 메인 루프를 실행한다."""
        now = datetime.now(timezone.utc)
        cfg = self.config_repo.load()
        state = SchedulerState(runtime_config=cfg, next_run_at=next_run_time(now, cfg.timeframe), last_config_reload_at=now)
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
                if now >= state.next_run_at:
                    logger.info(
                        "scheduler_tick_triggered now=%s next_run_at=%s",
                        now.isoformat(),
                        state.next_run_at.isoformat(),
                    )
                    self._run_once(state.runtime_config)
                    state.next_run_at = next_run_time(now, state.runtime_config.timeframe)
                    logger.info("scheduler_next_run_scheduled next_run_at=%s", state.next_run_at.isoformat())
                time.sleep(settings.poll_interval_seconds)
        finally:
            logger.info("scheduler_stopping")
            self.upbit.close()
