from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR
from typing import Iterable

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from trader.data.models import Fill, Order, OrderAttempt, TradeMetric
from trader.exchange.upbit_client import UpbitClient
from trader.trading.error_handling import OrderValidationError, classify_exception
from trader.trading.order_attempts import load_latest_attempt_for_order, next_attempt_no_for_order
from trader.trading.order_policy import OrderIntent, OrderPolicy, OrderPolicyConfig, resolve_intent
from trader.trading.order_states import LOCAL_OPEN_STATES, UPBIT_TO_LOCAL

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """실거래/테스트/섀도우 주문 실행과 주문 동기화를 담당한다."""

    def __init__(
        self,
        session: Session,
        upbit_client: UpbitClient,
        max_submit_retries: int = 3,
        retry_backoff_seconds: float = 0.8,
        trade_mode: str = "REAL",
        allowed_markets: Iterable[str] | None = None,
    ):
        self.session = session
        self.upbit_client = upbit_client
        self.max_submit_retries = max_submit_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.trade_mode = trade_mode.upper()
        self.allowed_markets = set(allowed_markets or [])
        self.order_policy = OrderPolicy()
        logger.info(
            "execution_init mode=%s max_submit_retries=%s retry_backoff_seconds=%s allowed_markets=%s",
            self.trade_mode,
            self.max_submit_retries,
            self.retry_backoff_seconds,
            sorted(self.allowed_markets) if self.allowed_markets else [],
        )

    def place_target_order(
        self,
        market: str,
        current_qty: Decimal,
        target_qty: Decimal,
        ref_price: Decimal,
        idempotency_key: str,
        user_id: int = 1,
        current_exposure_pct: Decimal | None = None,
        target_exposure_pct: Decimal | None = None,
        policy_config: OrderPolicyConfig | None = None,
        min_order_krw_buffer: Decimal = Decimal("0"),
        is_stop: bool = False,
        is_hard_halt: bool = False,
    ) -> Order | None:
        """Create and submit an order to move from current_qty to target_qty."""
        delta = target_qty - current_qty
        logger.info(
            "execution_place_target_start user_id=%s market=%s current_qty=%s target_qty=%s delta=%s ref_price=%s",
            user_id,
            market,
            current_qty,
            target_qty,
            delta,
            ref_price,
        )
        normalized_user_id = max(1, int(user_id))
        if abs(delta) < Decimal("0.00000001"):
            logger.info("execution_place_target_skip market=%s reason=no_delta", market)
            return None
        if self.allowed_markets and market not in self.allowed_markets:
            order = Order(
                user_id=normalized_user_id,
                market=market,
                side="bid" if delta > 0 else "ask",
                ord_type="limit",
                requested_price=ref_price,
                requested_volume=abs(delta),
                client_order_id=self._build_client_order_id(
                    idempotency_key=idempotency_key,
                    side="bid" if delta > 0 else "ask",
                    user_id=normalized_user_id,
                ),
                state="REJECTED",
                error_class="VALIDATION_ERROR",
                last_error=f"market_not_allowlisted:{market}",
                exchange_response_raw=json.dumps(
                    {
                        "error_class": "VALIDATION_ERROR",
                        "message": f"market_not_allowlisted:{market}",
                    },
                    ensure_ascii=False,
                ),
            )
            self.session.add(order)
            self.session.commit()
            self.session.refresh(order)
            logger.warning(
                "execution_place_target_rejected market=%s side=%s error_class=%s message=%s",
                order.market,
                order.side,
                order.error_class,
                order.last_error,
            )
            return order

        side = "bid" if delta > 0 else "ask"
        volume = abs(delta)

        policy_cfg = policy_config or OrderPolicyConfig(
            fill_timeout_sec_entry=0,
            fill_timeout_sec_exit=0,
            fill_timeout_sec_rebalance=0,
            max_reprice_attempts_entry=1,
            max_reprice_attempts_exit=1,
            max_reprice_attempts_rebalance=1,
            reprice_step_bps=10,
            allow_market_fallback_on_exit=False,
        )
        current_exposure = Decimal(str(current_exposure_pct if current_exposure_pct is not None else current_qty))
        target_exposure = Decimal(str(target_exposure_pct if target_exposure_pct is not None else target_qty))
        intent = resolve_intent(current_exposure=current_exposure, target_exposure=target_exposure)
        policy = self.order_policy.decide(intent=intent, cfg=policy_cfg, is_stop=is_stop, is_hard_halt=is_hard_halt)
        logger.info(
            "execution_order_policy intent=%s order_type=%s timeout=%s attempts=%s step_bps=%s fallback=%s",
            policy.intent.value,
            policy.order_type,
            policy.fill_timeout_sec,
            policy.max_reprice_attempts,
            policy.reprice_step_bps,
            policy.allow_market_fallback,
        )

        self._resolve_open_order_conflict(user_id=normalized_user_id, market=market, new_side=side)

        client_order_id = self._build_client_order_id(idempotency_key=idempotency_key, side=side, user_id=normalized_user_id)

        existing = self.session.scalar(
            select(Order).where(Order.user_id == normalized_user_id, Order.client_order_id == client_order_id)
        )
        if existing:
            logger.info(
                "execution_place_target_reuse client_order_id=%s market=%s state=%s",
                existing.client_order_id,
                existing.market,
                existing.state,
            )
            return self.sync_order(existing)

        open_order = self.session.scalar(
            select(Order)
            .where(Order.user_id == normalized_user_id, Order.market == market, Order.side == side, Order.state.in_(LOCAL_OPEN_STATES))
            .order_by(Order.created_at.desc())
        )
        if open_order:
            logger.info(
                "execution_place_target_use_open_order market=%s side=%s order_id=%s state=%s",
                open_order.market,
                open_order.side,
                open_order.id,
                open_order.state,
            )
            return self.sync_order(open_order)

        order = Order(
            user_id=normalized_user_id,
            market=market,
            side=side,
            ord_type="limit",
            requested_price=ref_price,
            requested_volume=volume,
            client_order_id=client_order_id,
            intent=policy.intent.value,
            state="NEW",
        )
        self.session.add(order)
        self.session.commit()
        logger.info(
            "execution_order_created order_id=%s market=%s side=%s client_order_id=%s intent=%s",
            order.id,
            order.market,
            order.side,
            order.client_order_id,
            order.intent,
        )

        try:
            chance, price_str, volume_str = self.validate_order_params(
                order,
                ref_price=ref_price,
                volume=volume,
                min_order_krw_buffer=min_order_krw_buffer,
            )
            if self.trade_mode == "SHADOW":
                order.state = "SHADOW"
                order.exchange_response_raw = json.dumps({"mode": "SHADOW", "chance": chance, "intent": order.intent}, ensure_ascii=False)
                self.session.commit()
                self.session.refresh(order)
                logger.info(
                    "execution_submit_shadow_ok order_id=%s market=%s side=%s",
                    order.id,
                    order.market,
                    order.side,
                )
                return order
            if self.trade_mode == "TEST":
                return self._submit_test(order=order, price_str=price_str, volume_str=volume_str, chance=chance)
            return self._submit_with_policy(
                order=order,
                price=Decimal(price_str),
                volume_str=volume_str,
                chance=chance,
                policy=policy,
            )
        except Exception as exc:
            logger.exception(
                "execution_place_target_exception order_id=%s market=%s side=%s",
                order.id,
                order.market,
                order.side,
            )
            self._persist_error(order, exc, default_state="REJECTED")
            return order

    def validate_order_params(
        self,
        order: Order,
        ref_price: Decimal,
        volume: Decimal,
        min_order_krw_buffer: Decimal = Decimal("0"),
    ) -> tuple[dict, str, str]:
        """Validate parameters against chance rules."""
        if ref_price <= 0:
            raise OrderValidationError("price must be > 0")
        if volume <= 0:
            raise OrderValidationError("volume must be > 0")

        chance = self.upbit_client.get_order_chance(order.market)
        min_total = self._extract_min_total(chance, order.side)
        tick = self._resolve_tick_size(chance, order.market, ref_price)
        price = self._adjust_price_by_tick(ref_price, tick, order.side)
        volume_adj = volume.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        total_krw = price * volume_adj
        min_total_with_buffer = min_total + max(Decimal("0"), Decimal(str(min_order_krw_buffer)))

        if min_total_with_buffer > 0 and total_krw < min_total_with_buffer:
            logger.warning(
                "execution_order_validation_fail order_id=%s market=%s side=%s total_krw=%s min_total=%s buffer=%s",
                order.id,
                order.market,
                order.side,
                total_krw,
                min_total,
                min_order_krw_buffer,
            )
            raise OrderValidationError(f"below_min_total: {total_krw} < {min_total_with_buffer}")

        order.requested_price = price
        order.requested_volume = volume_adj
        self.session.commit()
        logger.info(
            "execution_order_validated order_id=%s market=%s side=%s price=%s volume=%s tick=%s min_total=%s",
            order.id,
            order.market,
            order.side,
            price,
            volume_adj,
            tick,
            min_total,
        )
        return chance, self._to_exchange_str(price), self._to_exchange_str(volume_adj)

    def sync_order(self, order: Order) -> Order:
        """거래소 주문 상태를 조회해 로컬 주문/체결을 동기화한다."""
        if not order.upbit_uuid:
            logger.debug("execution_sync_skip_no_uuid order_id=%s client_order_id=%s", order.id, order.client_order_id)
            return order
        status = self.upbit_client.get_order(order.upbit_uuid)
        attempt_row = self._attempt_for_order(order)
        order.state = self._map_state(status.get("state"))
        order.exchange_response_raw = json.dumps(status, ensure_ascii=False)
        if attempt_row is not None:
            attempt_row.upbit_uuid = order.upbit_uuid
            attempt_row.state = order.state
            attempt_row.exchange_response_raw = order.exchange_response_raw
            attempt_row.error_class = None
            attempt_row.last_error = None
        self._upsert_fills(order=order, status=status)
        self._upsert_trade_metric(order)
        executed = Decimal(str(status.get("executed_volume", "0")))
        requested = Decimal(order.requested_volume or 0)
        if order.state == "OPEN" and executed > 0 and executed < requested:
            order.state = "PARTIAL"
        if attempt_row is not None:
            attempt_row.state = order.state
        self.session.commit()
        self.session.refresh(order)
        logger.info(
            "execution_sync_done order_id=%s market=%s side=%s state=%s executed=%s requested=%s upbit_uuid=%s",
            order.id,
            order.market,
            order.side,
            order.state,
            executed,
            requested,
            order.upbit_uuid,
        )
        return order

    def sync_local_open_orders(self, user_id: int | None = None) -> list[Order]:
        """로컬 OPEN 계열 주문들을 일괄 동기화한다."""
        query = select(Order).where(Order.state.in_(LOCAL_OPEN_STATES))
        if user_id is not None:
            query = query.where(Order.user_id == max(1, int(user_id)))
        rows = self.session.scalars(query).all()
        logger.info("execution_sync_open_orders_start count=%s", len(rows))
        synced: list[Order] = []
        for row in rows:
            try:
                synced.append(self.sync_order(row))
            except Exception:
                logger.exception("로컬 미체결 주문 동기화 실패: order_id=%s", row.id)
                continue
        logger.info("execution_sync_open_orders_done synced=%s", len(synced))
        return synced

    def cancel_order(self, order: Order) -> Order:
        """미체결 주문을 취소하고 로컬 상태를 갱신한다."""
        if not order.upbit_uuid:
            logger.debug("execution_cancel_skip_no_uuid order_id=%s", order.id)
            return order
        try:
            attempt_row = self._attempt_for_order(order)
            logger.info("execution_cancel_start order_id=%s upbit_uuid=%s", order.id, order.upbit_uuid)
            payload = self.upbit_client.cancel_order(order.upbit_uuid)
            order.state = self._map_state(payload.get("state"))
            order.exchange_response_raw = json.dumps({"cancel_response": payload}, ensure_ascii=False)
            if attempt_row is not None:
                attempt_row.upbit_uuid = order.upbit_uuid
                attempt_row.state = order.state
                attempt_row.exchange_response_raw = order.exchange_response_raw
                attempt_row.error_class = None
                attempt_row.last_error = None
            self._upsert_fills(order=order, status=payload)
            self.session.commit()
            self._upsert_trade_metric(order)
            self.session.refresh(order)
            logger.info("execution_cancel_done order_id=%s state=%s", order.id, order.state)
            return order
        except Exception as exc:
            logger.exception("주문 취소 중 예외 발생: order_id=%s", order.id)
            self._persist_error(order, exc, default_state=order.state or "ERROR_NEEDS_REVIEW")
            return order

    def cancel_open_orders(self, market: str | None = None, limit: int | None = None, user_id: int | None = None) -> list[Order]:
        """로컬 OPEN 계열 주문을 조회해 순차 취소한다."""
        query = select(Order).where(Order.state.in_(LOCAL_OPEN_STATES)).order_by(Order.created_at.asc())
        if user_id is not None:
            query = query.where(Order.user_id == max(1, int(user_id)))
        if market:
            query = query.where(Order.market == market)
        rows = self.session.scalars(query).all()
        if limit is not None:
            rows = rows[: max(limit, 0)]
        logger.info("execution_cancel_open_orders_start market=%s limit=%s count=%s", market, limit, len(rows))
        canceled: list[Order] = []
        for row in rows:
            canceled.append(self.cancel_order(row))
        logger.info("execution_cancel_open_orders_done canceled=%s", len(canceled))
        return canceled

    def _resolve_open_order_conflict(self, user_id: int, market: str, new_side: str) -> None:
        rows = self.session.scalars(
            select(Order)
            .where(Order.user_id == user_id, Order.market == market, Order.state.in_(LOCAL_OPEN_STATES))
            .order_by(Order.created_at.asc())
        ).all()
        conflicts = [row for row in rows if row.side != new_side]
        if not conflicts:
            return
        logger.info(
            "execution_open_order_conflict_resolve market=%s new_side=%s conflict_count=%s",
            market,
            new_side,
            len(conflicts),
        )
        for row in conflicts:
            self.cancel_order(row)

    def _submit_with_policy(
        self,
        order: Order,
        price: Decimal,
        volume_str: str,
        chance: dict,
        policy,
    ) -> Order:
        tick = self._resolve_tick_size(chance, order.market, price)
        price_step = Decimal(policy.reprice_step_bps) / Decimal("10000")
        max_attempts = max(1, int(policy.max_reprice_attempts))
        timeout = max(0, int(policy.fill_timeout_sec))
        requested_volume = Decimal(volume_str)

        for cycle_no in range(1, max_attempts + 1):
            if cycle_no > 1 or policy.order_type == "AGGRESSIVE_LIMIT":
                multiplier = Decimal("1") + price_step if order.side == "bid" else Decimal("1") - price_step
                if multiplier <= 0:
                    multiplier = Decimal("0.0001")
                price = self._adjust_price_by_tick(price * multiplier, tick, order.side)
            logger.info(
                "execution_reprice_attempt order_id=%s cycle=%s/%s price=%s intent=%s",
                order.id,
                cycle_no,
                max_attempts,
                price,
                order.intent,
            )
            attempt_row = self._begin_attempt(
                order=order,
                submit_reason="INITIAL" if cycle_no == 1 else "REPRICE",
                requested_price=price,
                requested_volume=requested_volume,
            )
            result = self._submit_real_with_recovery(
                order=order,
                attempt_row=attempt_row,
                price_str=self._to_exchange_str(price),
                volume_str=volume_str,
                chance=chance,
            )
            if timeout <= 0:
                return result
            if result.state in {"FILLED", "PARTIAL", "CANCELED", "ERROR", "ERROR_NEEDS_REVIEW", "REJECTED"}:
                return result
            started = time.monotonic()
            while (time.monotonic() - started) < timeout:
                synced = self.sync_order(order)
                if synced.state in {"FILLED", "PARTIAL", "CANCELED", "ERROR", "ERROR_NEEDS_REVIEW", "REJECTED"}:
                    return synced
                time.sleep(min(1.0, self.retry_backoff_seconds))
            synced = self.sync_order(order)
            if synced.state in {"FILLED", "PARTIAL", "CANCELED", "ERROR", "ERROR_NEEDS_REVIEW", "REJECTED"}:
                return synced
            self.cancel_order(order)

        if policy.allow_market_fallback:
            logger.warning("execution_market_fallback order_id=%s", order.id)
        return order

    def _submit_real_with_recovery(
        self,
        order: Order,
        attempt_row: OrderAttempt,
        price_str: str,
        volume_str: str,
        chance: dict,
    ) -> Order:
        """실주문은 1회 전송 후, 실패 시 재전송 없이 identifier 조회 복구만 수행한다."""
        logger.info(
            "execution_submit_real_start order_id=%s attempt_no=%s market=%s side=%s identifier=%s",
            order.id,
            attempt_row.attempt_no,
            order.market,
            order.side,
            attempt_row.upbit_identifier,
        )
        try:
            payload = self.upbit_client.create_order(
                market=order.market,
                side=order.side,
                ord_type=order.ord_type,
                price=price_str,
                volume=volume_str,
                identifier=attempt_row.upbit_identifier,
            )
            attempt_row.upbit_uuid = payload.get("uuid")
            attempt_row.state = self._map_state(payload.get("state"))
            attempt_row.retry_count = 0
            attempt_row.error_class = None
            attempt_row.last_error = None
            attempt_row.exchange_response_raw = json.dumps(
                {"chance": chance, "submit_response": payload},
                ensure_ascii=False,
            )
            self._mirror_attempt_to_order(order, attempt_row)
            self.session.commit()
            self.session.refresh(order)
            logger.info(
                "execution_submit_real_done order_id=%s attempt_no=%s upbit_uuid=%s state=%s",
                order.id,
                attempt_row.attempt_no,
                order.upbit_uuid,
                order.state,
            )
            return self.sync_order(order)
        except Exception as exc:
            info = classify_exception(exc)
            attempt_row.retry_count = 1
            attempt_row.error_class = info.error_class
            attempt_row.last_error = info.message
            attempt_row.state = order.state or "NEW"
            self._mirror_attempt_to_order(order, attempt_row)
            self.session.commit()
            logger.warning(
                "실주문 전송 실패: order_id=%s error_class=%s message=%s",
                order.id,
                order.error_class,
                order.last_error,
            )

        recovered = self._recover_order(order, attempt_row)
        if recovered:
            logger.info("execution_submit_real_recovered order_id=%s upbit_uuid=%s", recovered.id, recovered.upbit_uuid)
            return recovered

        attempt_row.state = "ERROR_NEEDS_REVIEW"
        self._mirror_attempt_to_order(order, attempt_row)
        self.session.commit()
        self.session.refresh(order)
        logger.error("실주문 수동 검토 필요 상태 전환: order_id=%s", order.id)
        return order

    def _submit_test(self, order: Order, price_str: str, volume_str: str, chance: dict) -> Order:
        """테스트 모드에서는 /v1/orders/test만 호출하고 결과를 주문 원장에 저장한다."""
        if not order.upbit_identifier:
            order.upbit_identifier = self._new_upbit_identifier(order.market, order.side)
        logger.info(
            "execution_submit_test_start order_id=%s market=%s side=%s identifier=%s",
            order.id,
            order.market,
            order.side,
            order.upbit_identifier,
        )
        try:
            payload = self.upbit_client.test_order(
                market=order.market,
                side=order.side,
                ord_type=order.ord_type,
                price=price_str,
                volume=volume_str,
                identifier=order.upbit_identifier,
            )
            order.state = "TEST_OK"
            order.error_class = None
            order.last_error = None
            order.exchange_response_raw = json.dumps(
                {"chance": chance, "test_response": payload},
                ensure_ascii=False,
            )
            self.session.commit()
            self.session.refresh(order)
            logger.info("execution_submit_test_done order_id=%s state=%s", order.id, order.state)
            return order
        except Exception as exc:
            logger.exception("테스트 주문 전송 중 예외 발생: order_id=%s", order.id)
            self._persist_error(order, exc, default_state="REJECTED")
            return order

    def _recover_order(self, order: Order, attempt_row: OrderAttempt) -> Order | None:
        """identifier 조회로 주문을 복구한다(재전송 금지)."""
        if not attempt_row.upbit_identifier:
            return None
        for recover_try in range(1, self.max_submit_retries + 1):
            logger.info(
                "execution_recover_attempt order_id=%s attempt_no=%s recover_try=%s/%s identifier=%s",
                order.id,
                attempt_row.attempt_no,
                recover_try,
                self.max_submit_retries,
                attempt_row.upbit_identifier,
            )
            try:
                payload = self.upbit_client.get_order_by_identifier(attempt_row.upbit_identifier)
                if payload:
                    attempt_row.upbit_uuid = payload.get("uuid")
                    attempt_row.state = self._map_state(payload.get("state"))
                    attempt_row.exchange_response_raw = json.dumps(payload, ensure_ascii=False)
                    attempt_row.retry_count = recover_try
                    attempt_row.error_class = None
                    attempt_row.last_error = None
                    self._mirror_attempt_to_order(order, attempt_row)
                    self._upsert_fills(order=order, status=payload)
                    self.session.commit()
                    self._upsert_trade_metric(order)
                    self.session.refresh(order)
                    logger.info(
                        "execution_recover_success order_id=%s attempt_no=%s recover_try=%s upbit_uuid=%s state=%s",
                        order.id,
                        attempt_row.attempt_no,
                        recover_try,
                        order.upbit_uuid,
                        order.state,
                    )
                    return order
            except Exception as exc:
                info = classify_exception(exc)
                attempt_row.error_class = info.error_class
                attempt_row.last_error = info.message
                attempt_row.retry_count = recover_try
                self._mirror_attempt_to_order(order, attempt_row)
                self.session.commit()
                logger.warning(
                    "주문 복구 시도 실패: order_id=%s attempt=%s error_class=%s message=%s",
                    order.id,
                    recover_try,
                    order.error_class,
                    order.last_error,
                )
            time.sleep(self.retry_backoff_seconds * recover_try)
        return None

    def _persist_error(self, order: Order, exc: Exception, default_state: str) -> None:
        """예외를 표준 분류로 저장하고 주문 상태를 실패 상태로 마무리한다."""
        info = classify_exception(exc)
        order.state = default_state
        order.error_class = info.error_class
        order.last_error = info.message
        order.exchange_response_raw = json.dumps(
            {
                "error_class": info.error_class,
                "message": info.message,
                "status_code": info.status_code,
                "exchange_code": info.exchange_code,
            },
            ensure_ascii=False,
        )
        attempt_row = self._attempt_for_order(order)
        if attempt_row is not None:
            self._mirror_order_to_attempt(order, attempt_row)
        self.session.commit()
        self.session.refresh(order)
        logger.warning(
            "주문 오류 상태 저장 완료: order_id=%s market=%s side=%s state=%s error_class=%s message=%s",
            order.id,
            order.market,
            order.side,
            order.state,
            order.error_class,
            order.last_error,
        )

    def _begin_attempt(
        self,
        order: Order,
        submit_reason: str,
        requested_price: Decimal,
        requested_volume: Decimal,
    ) -> OrderAttempt:
        attempt_row = OrderAttempt(
            order_id=order.id,
            attempt_no=self._next_attempt_no(order.id),
            submit_reason=submit_reason,
            requested_price=requested_price,
            requested_volume=requested_volume,
            upbit_identifier=self._reserve_unique_upbit_identifier(order.market, order.side),
            state="NEW",
            retry_count=0,
        )
        self.session.add(attempt_row)
        self._mirror_attempt_to_order(order, attempt_row)
        self.session.commit()
        self.session.refresh(order)
        self.session.refresh(attempt_row)
        return attempt_row

    def _next_attempt_no(self, order_id: int) -> int:
        return next_attempt_no_for_order(self.session, order_id)

    def _reserve_unique_upbit_identifier(self, market: str, side: str) -> str:
        for _ in range(10):
            candidate = self._new_upbit_identifier(market, side)
            exists = self.session.scalar(
                select(OrderAttempt.id).where(OrderAttempt.upbit_identifier == candidate)
            )
            if exists is None:
                return candidate
        raise RuntimeError("failed to allocate unique upbit_identifier")

    def _attempt_for_order(self, order: Order) -> OrderAttempt | None:
        return load_latest_attempt_for_order(
            self.session,
            order_id=order.id,
            upbit_uuid=order.upbit_uuid,
            upbit_identifier=order.upbit_identifier,
        )

    @staticmethod
    def _mirror_attempt_to_order(order: Order, attempt_row: OrderAttempt) -> None:
        order.requested_price = attempt_row.requested_price
        order.requested_volume = attempt_row.requested_volume
        order.upbit_identifier = attempt_row.upbit_identifier
        order.upbit_uuid = attempt_row.upbit_uuid
        order.state = attempt_row.state
        order.retry_count = attempt_row.retry_count
        order.error_class = attempt_row.error_class
        order.last_error = attempt_row.last_error
        order.exchange_response_raw = attempt_row.exchange_response_raw

    @staticmethod
    def _mirror_order_to_attempt(order: Order, attempt_row: OrderAttempt) -> None:
        attempt_row.requested_price = order.requested_price
        attempt_row.requested_volume = order.requested_volume
        attempt_row.upbit_identifier = order.upbit_identifier
        attempt_row.upbit_uuid = order.upbit_uuid
        attempt_row.state = order.state
        attempt_row.retry_count = order.retry_count
        attempt_row.error_class = order.error_class
        attempt_row.last_error = order.last_error
        attempt_row.exchange_response_raw = order.exchange_response_raw

    @staticmethod
    def _build_client_order_id(idempotency_key: str, side: str, user_id: int = 1) -> str:
        """멱등키와 방향을 기반으로 내부 client_order_id를 생성한다."""
        token = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in idempotency_key).strip("-")
        return f"u{max(1, int(user_id))}-{token}-{side}"[:64]

    @staticmethod
    def _new_upbit_identifier(market: str, side: str) -> str:
        """업비트 재사용 금지 정책을 만족하는 1회성 identifier를 생성한다."""
        return f"ubt-{market}-{side}-{uuid.uuid4().hex[:20]}"[:64]

    @staticmethod
    def _extract_min_total(chance: dict, side: str) -> Decimal:
        """chance 응답에서 side별 최소 주문 금액을 추출한다."""
        market_meta = chance.get("market", {}) if isinstance(chance, dict) else {}
        side_meta = market_meta.get(side, {}) if isinstance(market_meta, dict) else {}
        raw = side_meta.get("min_total")
        try:
            return Decimal(str(raw))
        except Exception:
            return Decimal("0")

    @staticmethod
    def _resolve_tick_size(chance: dict, market: str, price: Decimal) -> Decimal:
        """chance 우선, 없으면 KRW 정책 기반으로 호가단위를 계산한다."""
        market_meta = chance.get("market", {}) if isinstance(chance, dict) else {}
        side_meta = market_meta.get("bid", {}) if isinstance(market_meta, dict) else {}
        raw_unit = side_meta.get("price_unit")
        if raw_unit is not None:
            try:
                unit = Decimal(str(raw_unit))
                if unit > 0:
                    return unit
            except Exception:
                pass
        if market.startswith("KRW-"):
            return ExecutionEngine._krw_tick_size(price)
        return Decimal("0.00000001")

    @staticmethod
    def _krw_tick_size(price: Decimal) -> Decimal:
        """KRW 마켓 가격 구간별 호가단위를 반환한다."""
        if price >= Decimal("2000000"):
            return Decimal("1000")
        if price >= Decimal("1000000"):
            return Decimal("500")
        if price >= Decimal("500000"):
            return Decimal("100")
        if price >= Decimal("100000"):
            return Decimal("50")
        if price >= Decimal("10000"):
            return Decimal("10")
        if price >= Decimal("1000"):
            return Decimal("1")
        if price >= Decimal("100"):
            return Decimal("0.1")
        if price >= Decimal("10"):
            return Decimal("0.01")
        if price >= Decimal("1"):
            return Decimal("0.001")
        return Decimal("0.0001")

    @staticmethod
    def _adjust_price_by_tick(price: Decimal, tick: Decimal, side: str) -> Decimal:
        """호가단위 정책에 맞춰 가격을 보정한다."""
        if tick <= 0:
            return price
        scaled = price / tick
        if side == "bid":
            rounded = scaled.to_integral_value(rounding=ROUND_FLOOR)
        else:
            rounded = scaled.to_integral_value(rounding=ROUND_CEILING)
        return (rounded * tick).quantize(tick, rounding=ROUND_DOWN)

    @staticmethod
    def _to_exchange_str(value: Decimal) -> str:
        """Decimal 값을 거래소 요청용 문자열로 정규화한다."""
        text = format(value.normalize(), "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

    def _upsert_fills(self, order: Order, status: dict) -> None:
        """Upsert exchange fills into local DB."""
        inserted = 0
        skipped = 0
        for trade in status.get("trades", []):
            trade_id = str(trade.get("uuid") or trade.get("trade_uuid") or "")
            if not trade_id:
                skipped += 1
                continue
            exists = self.session.scalar(select(Fill).where(Fill.trade_id == trade_id))
            if exists:
                skipped += 1
                continue
            executed_at = self._parse_trade_time(trade)
            self.session.add(
                Fill(
                    order_id=order.id,
                    trade_id=trade_id,
                    price=Decimal(str(trade.get("price", "0"))),
                    volume=Decimal(str(trade.get("volume", "0"))),
                    fee=Decimal(str(trade.get("fee", "0"))),
                    executed_at=executed_at,
                )
            )
            inserted += 1
        if inserted or skipped:
            logger.info(
                "execution_fills_upserted order_id=%s market=%s inserted=%s skipped=%s",
                order.id,
                order.market,
                inserted,
                skipped,
            )

    def _upsert_trade_metric(self, order: Order) -> None:
        self.session.flush()
        fills = self.session.scalars(
            select(Fill).where(Fill.order_id == order.id).order_by(Fill.executed_at.asc(), Fill.id.asc())
        ).all()
        if not fills:
            return

        total_volume = Decimal("0")
        total_notional = Decimal("0")
        total_fee = Decimal("0")
        for fill in fills:
            price = Decimal(fill.price)
            volume = Decimal(fill.volume)
            fee = Decimal(fill.fee)
            total_notional += price * volume
            total_volume += volume
            total_fee += fee

        if total_volume <= 0:
            return

        intended = Decimal(order.requested_price or 0)
        vwap = total_notional / total_volume
        slippage_abs = None
        slippage_pct = None
        if intended > 0:
            raw = (vwap - intended) if order.side == "bid" else (intended - vwap)
            slippage_abs = raw
            slippage_pct = raw / intended

        created_at = order.created_at or datetime.now(timezone.utc)
        filled_at = max((fill.executed_at for fill in fills if fill.executed_at), default=created_at)
        time_to_fill_ms = int(max(0.0, (filled_at - created_at).total_seconds() * 1000))

        metric = self.session.scalar(select(TradeMetric).where(TradeMetric.order_id == order.id))
        if metric is None:
            metric = TradeMetric(order_id=order.id)
            self.session.add(metric)

        metric.intent = order.intent
        metric.intended_price = intended if intended > 0 else None
        metric.filled_vwap_price = vwap
        metric.slippage_abs = slippage_abs
        metric.slippage_pct = slippage_pct
        metric.fee_abs = total_fee
        metric.time_to_fill_ms = time_to_fill_ms
        metric.partial_fill_count = len(fills)
        self.session.commit()
        logger.info(
            "execution_trade_metric_upserted order_id=%s intent=%s vwap=%s slippage_pct=%s time_to_fill_ms=%s fill_count=%s",
            order.id,
            order.intent,
            vwap,
            slippage_pct,
            time_to_fill_ms,
            len(fills),
        )

    def latest_trade_metric(self, order_id: int) -> TradeMetric | None:
        return self.session.scalar(select(TradeMetric).where(TradeMetric.order_id == order_id))

    def count_slippage_breaches_since(
        self,
        since: datetime,
        entry_budget_pct: Decimal,
        exit_budget_pct: Decimal,
        user_id: int | None = None,
    ) -> int:
        query = (
            select(TradeMetric)
            .join(Order, TradeMetric.order_id == Order.id)
            .where(and_(TradeMetric.created_at >= since, TradeMetric.slippage_pct.is_not(None)))
        )
        if user_id is not None:
            query = query.where(Order.user_id == max(1, int(user_id)))
        rows = self.session.scalars(query).all()
        count = 0
        for row in rows:
            budget = exit_budget_pct if row.intent == OrderIntent.EXIT.value else entry_budget_pct
            if row.slippage_pct is not None and Decimal(row.slippage_pct) > budget:
                count += 1
        return count

    @staticmethod
    def _parse_trade_time(trade: dict) -> datetime:
        """체결 시각 문자열을 UTC datetime으로 변환한다."""
        raw = trade.get("created_at") or trade.get("executed_at")
        if not raw:
            return datetime.now(timezone.utc)
        if isinstance(raw, str):
            cleaned = raw.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(cleaned)
            except ValueError:
                return datetime.now(timezone.utc)
        return datetime.now(timezone.utc)

    @staticmethod
    def _map_state(raw_state: str | None) -> str:
        """거래소 상태값을 로컬 상태값으로 매핑한다."""
        if not raw_state:
            return "SENT"
        state = str(raw_state).lower()
        return UPBIT_TO_LOCAL.get(state, state.upper())
