from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.data.models import Fill, Order, PaperWallet, Position

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PortfolioSnapshot:
    """평가 시점 포트폴리오 자산 스냅샷."""

    cash_krw: Decimal
    market_value: Decimal
    total_equity: Decimal


class PortfolioService:
    def __init__(self, session: Session):
        """포트폴리오/체결 반영 로직을 위한 세션을 보관한다."""
        self.session = session

    def get_position(self, market: str, *, user_id: int = 1) -> Position | None:
        """마켓의 현재 포지션을 조회한다."""
        row = self.session.get(Position, (max(1, int(user_id)), market))
        logger.debug("portfolio_get_position user_id=%s market=%s found=%s", user_id, market, row is not None)
        return row

    def upsert_position(self, market: str, qty: Decimal, avg_price: Decimal, *, user_id: int = 1) -> Position:
        """포지션을 생성 또는 갱신하고 최신 상태를 반환한다."""
        normalized_user_id = max(1, int(user_id))
        row = self.session.get(Position, (normalized_user_id, market))
        created = row is None
        if row is None:
            row = Position(user_id=normalized_user_id, market=market, qty=qty, avg_price=avg_price)
            self.session.add(row)
        else:
            row.qty = qty
            row.avg_price = avg_price
        self.session.commit()
        self.session.refresh(row)
        logger.debug(
            "portfolio_upsert_position user_id=%s market=%s created=%s qty=%s avg_price=%s",
            normalized_user_id,
            market,
            created,
            row.qty,
            row.avg_price,
        )
        return row

    def get_or_create_paper_wallet(self, initial_cash_krw: Decimal, *, user_id: int = 1) -> PaperWallet:
        """페이퍼 모드 현금 지갑을 조회하고 없으면 생성한다."""
        normalized_user_id = max(1, int(user_id))
        wallet = self.session.get(PaperWallet, normalized_user_id)
        if wallet is None:
            wallet = PaperWallet(user_id=normalized_user_id, cash_krw=initial_cash_krw)
            self.session.add(wallet)
            self.session.commit()
            self.session.refresh(wallet)
            logger.info("portfolio_wallet_created user_id=%s cash_krw=%s", wallet.user_id, wallet.cash_krw)
        return wallet

    def apply_unapplied_fills(self, order: Order, use_paper_wallet: bool = False, initial_cash_krw: Decimal = Decimal("0")) -> int:
        """주문의 미반영 체결을 포지션/지갑에 1회만 반영한다."""
        fills = self.session.scalars(
            select(Fill).where(Fill.order_id == order.id, Fill.is_applied.is_(False)).order_by(Fill.executed_at.asc(), Fill.id.asc())
        ).all()
        if not fills:
            logger.debug("portfolio_apply_fills_skip order_id=%s reason=no_unapplied_fills", order.id)
            return 0
        user_id = max(1, int(getattr(order, "user_id", 1) or 1))
        position = self.session.get(Position, (user_id, order.market))
        if position is None:
            position = Position(user_id=user_id, market=order.market, qty=Decimal("0"), avg_price=Decimal("0"))
            self.session.add(position)
        wallet = self.get_or_create_paper_wallet(initial_cash_krw, user_id=user_id) if use_paper_wallet else None
        for fill in fills:
            self._apply_fill_to_position(position, order.side, Decimal(fill.price), Decimal(fill.volume), Decimal(fill.fee))
            if wallet is not None:
                self._apply_fill_to_wallet(wallet, order.side, Decimal(fill.price), Decimal(fill.volume), Decimal(fill.fee))
            fill.is_applied = True
        self.session.commit()
        logger.info(
            "portfolio_apply_fills_done order_id=%s market=%s side=%s applied=%s use_paper_wallet=%s",
            order.id,
            order.market,
            order.side,
            len(fills),
            use_paper_wallet,
        )
        return len(fills)

    @staticmethod
    def _apply_fill_to_position(position: Position, side: str, price: Decimal, volume: Decimal, fee: Decimal) -> None:
        """단일 체결을 포지션 수량/평단/실현손익에 반영한다."""
        qty = Decimal(position.qty)
        avg_price = Decimal(position.avg_price)
        if side == "bid":
            new_qty = qty + volume
            if new_qty <= 0:
                position.qty = Decimal("0")
                position.avg_price = Decimal("0")
                return
            old_cost = qty * avg_price
            new_cost = (volume * price) + fee
            position.qty = new_qty
            position.avg_price = (old_cost + new_cost) / new_qty
            return
        sell_qty = min(volume, qty)
        realized = Decimal(position.realized_pnl or 0) + (sell_qty * (price - avg_price)) - fee
        new_qty = qty - sell_qty
        position.qty = new_qty if new_qty > 0 else Decimal("0")
        position.realized_pnl = realized
        if position.qty == 0:
            position.avg_price = Decimal("0")

    @staticmethod
    def _apply_fill_to_wallet(wallet: PaperWallet, side: str, price: Decimal, volume: Decimal, fee: Decimal) -> None:
        """단일 체결을 페이퍼 지갑 현금 잔고에 반영한다."""
        notion = price * volume
        if side == "bid":
            wallet.cash_krw = Decimal(wallet.cash_krw) - notion - fee
        else:
            wallet.cash_krw = Decimal(wallet.cash_krw) + notion - fee

    def snapshot(self, mark_prices: dict[str, Decimal], cash_krw: Decimal, *, user_id: int = 1) -> PortfolioSnapshot:
        """현재 포지션과 시세를 이용해 총 자산 스냅샷을 계산한다."""
        normalized_user_id = max(1, int(user_id))
        rows = self.session.scalars(select(Position).where(Position.user_id == normalized_user_id)).all()
        market_value = Decimal("0")
        for p in rows:
            market_value += Decimal(p.qty) * mark_prices.get(p.market, Decimal("0"))
        return PortfolioSnapshot(cash_krw=cash_krw, market_value=market_value, total_equity=cash_krw + market_value)

    def update_unrealized_pnl(self, mark_prices: dict[str, Decimal], *, user_id: int = 1) -> Decimal:
        """현재 마크가격 기준으로 포지션 평가손익을 갱신하고 합계를 반환한다."""
        normalized_user_id = max(1, int(user_id))
        total = Decimal("0")
        rows = self.session.scalars(select(Position).where(Position.user_id == normalized_user_id)).all()
        for row in rows:
            qty = Decimal(row.qty)
            if qty <= 0:
                row.unrealized_pnl = Decimal("0")
                continue
            avg_price = Decimal(row.avg_price)
            mark_price = mark_prices.get(row.market, avg_price)
            unrealized = qty * (mark_price - avg_price)
            row.unrealized_pnl = unrealized
            total += unrealized
        self.session.commit()
        logger.info("portfolio_unrealized_updated user_id=%s positions=%s total_unrealized=%s", normalized_user_id, len(rows), total)
        return total

    def total_realized_pnl(self, markets: list[str] | None = None, *, user_id: int = 1) -> Decimal:
        """현재 저장된 포지션의 누적 실현손익 합계를 반환한다."""
        normalized_user_id = max(1, int(user_id))
        rows = self.session.scalars(select(Position).where(Position.user_id == normalized_user_id)).all()
        allowed = set(markets or [])
        total = Decimal("0")
        for row in rows:
            if allowed and row.market not in allowed:
                continue
            total += Decimal(row.realized_pnl)
        logger.debug("portfolio_total_realized user_id=%s markets=%s total=%s", normalized_user_id, sorted(allowed) if allowed else [], total)
        return total

    def total_unrealized_pnl(self, markets: list[str] | None = None, *, user_id: int = 1) -> Decimal:
        """현재 저장된 포지션의 평가손익 합계를 반환한다."""
        normalized_user_id = max(1, int(user_id))
        rows = self.session.scalars(select(Position).where(Position.user_id == normalized_user_id)).all()
        allowed = set(markets or [])
        total = Decimal("0")
        for row in rows:
            if allowed and row.market not in allowed:
                continue
            total += Decimal(row.unrealized_pnl)
        logger.debug("portfolio_total_unrealized user_id=%s markets=%s total=%s", normalized_user_id, sorted(allowed) if allowed else [], total)
        return total
