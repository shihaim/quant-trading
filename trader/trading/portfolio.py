from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.data.models import Fill, Order, PaperWallet, Position


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

    def get_position(self, market: str) -> Position | None:
        """마켓의 현재 포지션을 조회한다."""
        return self.session.get(Position, market)

    def upsert_position(self, market: str, qty: Decimal, avg_price: Decimal) -> Position:
        """포지션을 생성 또는 갱신하고 최신 상태를 반환한다."""
        row = self.session.get(Position, market)
        if row is None:
            row = Position(market=market, qty=qty, avg_price=avg_price)
            self.session.add(row)
        else:
            row.qty = qty
            row.avg_price = avg_price
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_or_create_paper_wallet(self, initial_cash_krw: Decimal) -> PaperWallet:
        """페이퍼 모드 현금 지갑을 조회하고 없으면 생성한다."""
        wallet = self.session.get(PaperWallet, 1)
        if wallet is None:
            wallet = PaperWallet(id=1, cash_krw=initial_cash_krw)
            self.session.add(wallet)
            self.session.commit()
            self.session.refresh(wallet)
        return wallet

    def apply_unapplied_fills(self, order: Order, use_paper_wallet: bool = False, initial_cash_krw: Decimal = Decimal("0")) -> int:
        """주문의 미반영 체결을 포지션/지갑에 1회만 반영한다."""
        fills = self.session.scalars(
            select(Fill).where(Fill.order_id == order.id, Fill.is_applied.is_(False)).order_by(Fill.executed_at.asc(), Fill.id.asc())
        ).all()
        if not fills:
            return 0
        position = self.session.get(Position, order.market)
        if position is None:
            position = Position(market=order.market, qty=Decimal("0"), avg_price=Decimal("0"))
            self.session.add(position)
        wallet = self.get_or_create_paper_wallet(initial_cash_krw) if use_paper_wallet else None
        for fill in fills:
            self._apply_fill_to_position(position, order.side, Decimal(fill.price), Decimal(fill.volume), Decimal(fill.fee))
            if wallet is not None:
                self._apply_fill_to_wallet(wallet, order.side, Decimal(fill.price), Decimal(fill.volume), Decimal(fill.fee))
            fill.is_applied = True
        self.session.commit()
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

    def snapshot(self, mark_prices: dict[str, Decimal], cash_krw: Decimal) -> PortfolioSnapshot:
        """현재 포지션과 시세를 이용해 총 자산 스냅샷을 계산한다."""
        rows = self.session.scalars(select(Position)).all()
        market_value = Decimal("0")
        for p in rows:
            market_value += Decimal(p.qty) * mark_prices.get(p.market, Decimal("0"))
        return PortfolioSnapshot(cash_krw=cash_krw, market_value=market_value, total_equity=cash_krw + market_value)
