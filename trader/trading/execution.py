from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.data.models import Fill, Order
from trader.exchange.upbit_client import UpbitClient
from trader.trading.error_handling import OrderValidationError, classify_exception
from trader.trading.order_states import LOCAL_OPEN_STATES, UPBIT_TO_LOCAL


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

    def place_target_order(
        self,
        market: str,
        current_qty: Decimal,
        target_qty: Decimal,
        ref_price: Decimal,
        idempotency_key: str,
    ) -> Order | None:
        """현재/목표 수량 차이를 기준으로 주문을 생성하고 모드별로 처리한다."""
        delta = target_qty - current_qty
        if abs(delta) < Decimal("0.00000001"):
            return None
        if self.allowed_markets and market not in self.allowed_markets:
            order = Order(
                market=market,
                side="bid" if delta > 0 else "ask",
                ord_type="limit",
                requested_price=ref_price,
                requested_volume=abs(delta),
                client_order_id=self._build_client_order_id(idempotency_key=idempotency_key, side="bid" if delta > 0 else "ask"),
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
            return order

        side = "bid" if delta > 0 else "ask"
        volume = abs(delta)
        client_order_id = self._build_client_order_id(idempotency_key=idempotency_key, side=side)

        existing = self.session.scalar(select(Order).where(Order.client_order_id == client_order_id))
        if existing:
            return self.sync_order(existing)

        open_order = self.session.scalar(
            select(Order)
            .where(Order.market == market, Order.side == side, Order.state.in_(LOCAL_OPEN_STATES))
            .order_by(Order.created_at.desc())
        )
        if open_order:
            return self.sync_order(open_order)

        order = Order(
            market=market,
            side=side,
            ord_type="limit",
            requested_price=ref_price,
            requested_volume=volume,
            client_order_id=client_order_id,
            state="NEW",
        )
        self.session.add(order)
        self.session.commit()

        try:
            chance, price_str, volume_str = self.validate_order_params(order, ref_price=ref_price, volume=volume)
            if self.trade_mode == "SHADOW":
                order.state = "SHADOW"
                order.exchange_response_raw = json.dumps({"mode": "SHADOW", "chance": chance}, ensure_ascii=False)
                self.session.commit()
                self.session.refresh(order)
                return order
            if self.trade_mode == "TEST":
                return self._submit_test(order=order, price_str=price_str, volume_str=volume_str, chance=chance)
            return self._submit_real_with_recovery(order=order, price_str=price_str, volume_str=volume_str, chance=chance)
        except Exception as exc:
            self._persist_error(order, exc, default_state="REJECTED")
            return order

    def validate_order_params(self, order: Order, ref_price: Decimal, volume: Decimal) -> tuple[dict, str, str]:
        """chance 정보를 바탕으로 주문 파라미터를 사전 검증/정규화한다."""
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

        if min_total > 0 and total_krw < min_total:
            raise OrderValidationError(f"below_min_total: {total_krw} < {min_total}")

        order.requested_price = price
        order.requested_volume = volume_adj
        self.session.commit()
        return chance, self._to_exchange_str(price), self._to_exchange_str(volume_adj)

    def sync_order(self, order: Order) -> Order:
        """거래소 주문 상태를 조회해 로컬 주문/체결을 동기화한다."""
        if not order.upbit_uuid:
            return order
        status = self.upbit_client.get_order(order.upbit_uuid)
        order.state = self._map_state(status.get("state"))
        order.exchange_response_raw = json.dumps(status, ensure_ascii=False)
        self._upsert_fills(order=order, status=status)
        executed = Decimal(str(status.get("executed_volume", "0")))
        requested = Decimal(order.requested_volume or 0)
        if order.state == "OPEN" and executed > 0 and executed < requested:
            order.state = "PARTIAL"
        self.session.commit()
        self.session.refresh(order)
        return order

    def sync_local_open_orders(self) -> list[Order]:
        """로컬 OPEN 계열 주문들을 일괄 동기화한다."""
        rows = self.session.scalars(select(Order).where(Order.state.in_(LOCAL_OPEN_STATES))).all()
        synced: list[Order] = []
        for row in rows:
            try:
                synced.append(self.sync_order(row))
            except Exception:
                continue
        return synced

    def cancel_order(self, order: Order) -> Order:
        """미체결 주문을 취소하고 로컬 상태를 갱신한다."""
        if not order.upbit_uuid:
            return order
        try:
            payload = self.upbit_client.cancel_order(order.upbit_uuid)
            order.state = self._map_state(payload.get("state"))
            order.exchange_response_raw = json.dumps({"cancel_response": payload}, ensure_ascii=False)
            self._upsert_fills(order=order, status=payload)
            self.session.commit()
            self.session.refresh(order)
            return order
        except Exception as exc:
            self._persist_error(order, exc, default_state=order.state or "ERROR_NEEDS_REVIEW")
            return order

    def cancel_open_orders(self, market: str | None = None, limit: int | None = None) -> list[Order]:
        """로컬 OPEN 계열 주문을 조회해 순차 취소한다."""
        query = select(Order).where(Order.state.in_(LOCAL_OPEN_STATES)).order_by(Order.created_at.asc())
        if market:
            query = query.where(Order.market == market)
        rows = self.session.scalars(query).all()
        if limit is not None:
            rows = rows[: max(limit, 0)]
        canceled: list[Order] = []
        for row in rows:
            canceled.append(self.cancel_order(row))
        return canceled

    def _submit_real_with_recovery(self, order: Order, price_str: str, volume_str: str, chance: dict) -> Order:
        """실주문은 1회 전송 후, 실패 시 재전송 없이 identifier 조회 복구만 수행한다."""
        if not order.upbit_identifier:
            order.upbit_identifier = self._new_upbit_identifier(order.market, order.side)
        try:
            payload = self.upbit_client.create_order(
                market=order.market,
                side=order.side,
                ord_type=order.ord_type,
                price=price_str,
                volume=volume_str,
                identifier=order.upbit_identifier,
            )
            order.upbit_uuid = payload.get("uuid")
            order.state = self._map_state(payload.get("state"))
            order.retry_count = 0
            order.error_class = None
            order.last_error = None
            order.exchange_response_raw = json.dumps(
                {"chance": chance, "submit_response": payload},
                ensure_ascii=False,
            )
            self.session.commit()
            self.session.refresh(order)
            return self.sync_order(order)
        except Exception as exc:
            info = classify_exception(exc)
            order.retry_count = 1
            order.error_class = info.error_class
            order.last_error = info.message
            self.session.commit()

        recovered = self._recover_order(order)
        if recovered:
            return recovered

        order.state = "ERROR_NEEDS_REVIEW"
        self.session.commit()
        self.session.refresh(order)
        return order

    def _submit_test(self, order: Order, price_str: str, volume_str: str, chance: dict) -> Order:
        """테스트 모드에서는 /v1/orders/test만 호출하고 결과를 주문 원장에 저장한다."""
        if not order.upbit_identifier:
            order.upbit_identifier = self._new_upbit_identifier(order.market, order.side)
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
            return order
        except Exception as exc:
            self._persist_error(order, exc, default_state="REJECTED")
            return order

    def _recover_order(self, order: Order) -> Order | None:
        """identifier 조회로 주문을 복구한다(재전송 금지)."""
        if not order.upbit_identifier:
            return None
        for attempt in range(1, self.max_submit_retries + 1):
            try:
                payload = self.upbit_client.get_order_by_identifier(order.upbit_identifier)
                if payload:
                    order.upbit_uuid = payload.get("uuid")
                    order.state = self._map_state(payload.get("state"))
                    order.exchange_response_raw = json.dumps(payload, ensure_ascii=False)
                    self._upsert_fills(order=order, status=payload)
                    self.session.commit()
                    self.session.refresh(order)
                    return order
            except Exception as exc:
                info = classify_exception(exc)
                order.error_class = info.error_class
                order.last_error = info.message
                order.retry_count = attempt
                self.session.commit()
            time.sleep(self.retry_backoff_seconds * attempt)
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
        self.session.commit()
        self.session.refresh(order)

    @staticmethod
    def _build_client_order_id(idempotency_key: str, side: str) -> str:
        """멱등키와 방향을 기반으로 내부 client_order_id를 생성한다."""
        token = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in idempotency_key).strip("-")
        return f"{token}-{side}"[:64]

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
        """주문 조회 응답의 체결 내역을 중복 없이 DB에 반영한다."""
        for trade in status.get("trades", []):
            trade_id = str(trade.get("uuid") or trade.get("trade_uuid") or "")
            if not trade_id:
                continue
            exists = self.session.scalar(select(Fill).where(Fill.trade_id == trade_id))
            if exists:
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
