from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.data.models import Fill, Order


class PaperExecutionEngine:
    def __init__(self, session: Session, fee_rate: Decimal):
        """페이퍼 트레이딩 전용 주문 엔진을 초기화한다."""
        self.session = session
        self.fee_rate = fee_rate

    def place_target_order(
        self,
        market: str,
        current_qty: Decimal,
        target_qty: Decimal,
        ref_price: Decimal,
        idempotency_key: str,
    ) -> Order | None:
        """목표 수량 차이만큼 가상 주문/체결을 즉시 생성한다."""
        delta = target_qty - current_qty
        if abs(delta) < Decimal("0.00000001"):
            return None
        side = "bid" if delta > 0 else "ask"
        volume = abs(delta)
        client_order_id = self._build_client_order_id(idempotency_key=idempotency_key, side=side)
        existing = self.session.scalar(select(Order).where(Order.client_order_id == client_order_id))
        if existing:
            return existing
        order = Order(
            market=market,
            side=side,
            ord_type="limit",
            requested_price=ref_price,
            requested_volume=volume,
            client_order_id=client_order_id,
            upbit_uuid=f"paper-{uuid.uuid4().hex[:24]}",
            state="FILLED",
        )
        self.session.add(order)
        self.session.flush()
        fee = (ref_price * volume) * self.fee_rate
        fill = Fill(
            order_id=order.id,
            trade_id=f"{client_order_id}-fill-1",
            price=ref_price,
            volume=volume,
            fee=fee,
        )
        self.session.add(fill)
        self.session.commit()
        self.session.refresh(order)
        return order

    def sync_order(self, order: Order) -> Order:
        """페이퍼 주문은 즉시 확정되므로 입력 주문을 그대로 반환한다."""
        return order

    def sync_local_open_orders(self) -> list[Order]:
        """페이퍼 모드에는 열린 주문 추적이 없어 빈 목록을 반환한다."""
        return []

    @staticmethod
    def _build_client_order_id(idempotency_key: str, side: str) -> str:
        """멱등키를 기반으로 페이퍼 주문 식별자를 생성한다."""
        token = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in idempotency_key).strip("-")
        return f"{token}-{side}"[:64]
