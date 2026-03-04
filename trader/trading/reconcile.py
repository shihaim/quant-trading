from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trader.data.models import Order, OrderAttempt
from trader.exchange.upbit_client import UpbitClient
from trader.trading.execution import ExecutionEngine
from trader.trading.order_states import UPBIT_TO_LOCAL
from trader.trading.portfolio import PortfolioService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReconcileSnapshot:
    """리컨실 결과로 계산된 자산 스냅샷."""

    cash_krw: Decimal
    market_value: Decimal
    total_equity: Decimal


class ReconcileService:
    def __init__(
        self,
        session: Session,
        upbit_client: UpbitClient,
        portfolio: PortfolioService,
        execution: ExecutionEngine,
    ):
        """거래소 상태를 로컬 DB와 맞추는 서비스 의존성을 초기화한다."""
        self.session = session
        self.upbit_client = upbit_client
        self.portfolio = portfolio
        self.execution = execution

    def reconcile_all(self, markets: list[str], mark_prices: dict[str, Decimal]) -> ReconcileSnapshot:
        """계좌/미체결/주문체결을 일괄 동기화하고 총자산을 계산한다."""
        logger.info("reconcile_all_start markets=%s mark_price_count=%s", markets, len(mark_prices))
        cash_krw, market_value = self._reconcile_accounts(markets=markets, mark_prices=mark_prices)
        self._reconcile_open_orders()
        synced = self.execution.sync_local_open_orders()
        applied_total = 0
        for order in synced:
            applied_total += self.portfolio.apply_unapplied_fills(order, use_paper_wallet=False)
        self.portfolio.update_unrealized_pnl(mark_prices=mark_prices)
        snapshot = ReconcileSnapshot(cash_krw=cash_krw, market_value=market_value, total_equity=cash_krw + market_value)
        logger.info(
            "reconcile_all_done cash_krw=%s market_value=%s total_equity=%s synced_orders=%s fills_applied=%s",
            snapshot.cash_krw,
            snapshot.market_value,
            snapshot.total_equity,
            len(synced),
            applied_total,
        )
        return snapshot

    def _reconcile_accounts(self, markets: list[str], mark_prices: dict[str, Decimal]) -> tuple[Decimal, Decimal]:
        """거래소 잔고를 읽어 포지션을 맞추고 현금/평가액을 계산한다."""
        accounts = self.upbit_client.get_accounts()
        by_currency = {str(a.get("currency")): a for a in accounts}
        krw = by_currency.get("KRW", {})
        cash_krw = Decimal(str(krw.get("balance", "0"))) + Decimal(str(krw.get("locked", "0")))
        market_value = Decimal("0")
        for market in markets:
            asset = market.split("-")[-1]
            account = by_currency.get(asset, {})
            qty = Decimal(str(account.get("balance", "0"))) + Decimal(str(account.get("locked", "0")))
            avg_price = Decimal(str(account.get("avg_buy_price", "0")))
            self.portfolio.upsert_position(market=market, qty=qty, avg_price=avg_price)
            mark = mark_prices.get(market, avg_price)
            market_value += qty * mark
        logger.debug(
            "reconcile_accounts_done markets=%s cash_krw=%s market_value=%s account_count=%s",
            markets,
            cash_krw,
            market_value,
            len(accounts),
        )
        return cash_krw, market_value

    def _reconcile_open_orders(self) -> None:
        """거래소 미체결 주문을 로컬 orders 테이블과 정합화한다."""
        rows = self.upbit_client.get_open_orders()
        created_orders = 0
        created_attempts = 0
        updated_attempts = 0
        for raw in rows:
            upbit_uuid = str(raw.get("uuid") or "")
            if not upbit_uuid:
                continue
            upbit_identifier = str(raw.get("identifier") or "")
            client_order_id = f"upbit-{upbit_uuid}"[:64]
            attempt_row = self._find_attempt_by_exchange_refs(upbit_uuid=upbit_uuid, upbit_identifier=upbit_identifier)
            order = attempt_row.order if attempt_row is not None else None
            if order is None:
                order = self.session.scalar(select(Order).where(Order.client_order_id == client_order_id))
            if order is None:
                order = self.session.scalar(select(Order).where(Order.upbit_uuid == upbit_uuid))
            if order is None and upbit_identifier:
                order = self.session.scalar(select(Order).where(Order.upbit_identifier == upbit_identifier))
            if order is None:
                order = Order(
                    market=str(raw.get("market")),
                    side=str(raw.get("side")),
                    ord_type=str(raw.get("ord_type", "limit")),
                    requested_price=Decimal(str(raw.get("price", "0"))),
                    requested_volume=Decimal(str(raw.get("volume", "0"))),
                    client_order_id=client_order_id,
                    state="NEW",
                    created_at=self._parse_time(raw.get("created_at")),
                )
                self.session.add(order)
                self.session.flush()
                created_orders += 1

            if attempt_row is None:
                attempt_row = OrderAttempt(
                    order_id=order.id,
                    attempt_no=self._next_attempt_no(order.id),
                    submit_reason="RECOVER",
                    state="NEW",
                    retry_count=0,
                )
                self.session.add(attempt_row)
                self.session.flush()
                created_attempts += 1
            else:
                updated_attempts += 1

            if raw.get("price") is not None:
                attempt_row.requested_price = Decimal(str(raw.get("price", "0")))
            if raw.get("volume") is not None:
                attempt_row.requested_volume = Decimal(str(raw.get("volume", "0")))
            if upbit_identifier:
                attempt_row.upbit_identifier = upbit_identifier[:64]
            attempt_row.upbit_uuid = upbit_uuid
            attempt_row.state = self._map_state(raw.get("state"))
            attempt_row.error_class = None
            attempt_row.last_error = None
            self._mirror_attempt_to_order(order, attempt_row)
        self.session.commit()
        logger.info(
            "reconcile_open_orders_done fetched=%s created_orders=%s created_attempts=%s updated_attempts=%s",
            len(rows),
            created_orders,
            created_attempts,
            updated_attempts,
        )

    def _find_attempt_by_exchange_refs(self, upbit_uuid: str, upbit_identifier: str) -> OrderAttempt | None:
        row = self.session.scalar(select(OrderAttempt).where(OrderAttempt.upbit_uuid == upbit_uuid))
        if row is not None:
            return row
        if upbit_identifier:
            row = self.session.scalar(select(OrderAttempt).where(OrderAttempt.upbit_identifier == upbit_identifier))
            if row is not None:
                return row
        return None

    def _next_attempt_no(self, order_id: int) -> int:
        current = self.session.scalar(
            select(func.max(OrderAttempt.attempt_no)).where(OrderAttempt.order_id == order_id)
        )
        return int(current or 0) + 1

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
    def _map_state(raw_state: str | None) -> str:
        """거래소 주문 상태를 로컬 상태명으로 변환한다."""
        if not raw_state:
            return "OPEN"
        return UPBIT_TO_LOCAL.get(str(raw_state).lower(), str(raw_state).upper())

    @staticmethod
    def _parse_time(raw: str | None) -> datetime:
        """ISO 시각 문자열을 UTC datetime으로 파싱한다."""
        if not raw:
            return datetime.now(timezone.utc)
        cleaned = raw.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return datetime.now(timezone.utc)
