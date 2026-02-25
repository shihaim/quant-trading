from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from trader.data.models import Candle
from trader.exchange.upbit_client import UpbitClient

logger = logging.getLogger(__name__)


class CandleService:
    def __init__(self, session: Session, upbit_client: UpbitClient):
        """캔들 적재/조회에 필요한 DB 세션과 거래소 클라이언트를 설정한다."""
        self.session = session
        self.upbit_client = upbit_client

    def ensure_backfill(self, market: str, timeframe: str, minimum_count: int) -> None:
        """전략 최소 길이를 만족하도록 과거 캔들을 채운다."""
        current_count = self.session.scalar(
            select(func.count(Candle.id)).where(Candle.market == market, Candle.timeframe == timeframe)
        )
        if current_count and current_count >= minimum_count:
            logger.debug(
                "candle_backfill_skip market=%s timeframe=%s current_count=%s minimum=%s",
                market,
                timeframe,
                current_count,
                minimum_count,
            )
            return
        logger.info(
            "candle_backfill_start market=%s timeframe=%s current_count=%s minimum=%s",
            market,
            timeframe,
            current_count or 0,
            minimum_count,
        )
        candles = self.upbit_client.get_candles(market=market, timeframe=timeframe, count=minimum_count)
        self._upsert_upbit_candles(market=market, timeframe=timeframe, candles=candles)
        logger.info(
            "candle_backfill_done market=%s timeframe=%s fetched=%s",
            market,
            timeframe,
            len(candles),
        )

    def upsert_latest_complete(self, market: str, timeframe: str) -> None:
        """가장 최근 완성 봉 1개를 갱신한다(업서트)."""
        candles = self.upbit_client.get_candles(market=market, timeframe=timeframe, count=2)
        if not candles:
            logger.warning("candle_latest_empty market=%s timeframe=%s", market, timeframe)
            return
        complete = candles[1] if len(candles) > 1 else candles[0]
        self._upsert_upbit_candles(market=market, timeframe=timeframe, candles=[complete])
        logger.debug(
            "candle_latest_upserted market=%s timeframe=%s candle_time=%s",
            market,
            timeframe,
            complete.get("candle_date_time_utc"),
        )

    def recent_candles(self, market: str, timeframe: str, limit: int) -> list[Candle]:
        """최근 캔들을 시간 오름차순으로 반환한다."""
        rows = self.session.scalars(
            select(Candle)
            .where(Candle.market == market, Candle.timeframe == timeframe)
            .order_by(Candle.candle_time_utc.desc())
            .limit(limit)
        ).all()
        result = list(reversed(rows))
        logger.debug(
            "candle_recent_loaded market=%s timeframe=%s requested=%s loaded=%s",
            market,
            timeframe,
            limit,
            len(result),
        )
        return result

    def _upsert_upbit_candles(self, market: str, timeframe: str, candles: list[dict]) -> None:
        """업비트 응답 캔들을 PK 기준으로 생성/갱신한다."""
        inserted = 0
        updated = 0
        for raw in candles:
            candle_time = datetime.fromisoformat(raw["candle_date_time_utc"]).replace(tzinfo=timezone.utc)
            row = self.session.scalar(
                select(Candle).where(
                    Candle.market == market,
                    Candle.timeframe == timeframe,
                    Candle.candle_time_utc == candle_time,
                )
            )
            if row is None:
                row = Candle(market=market, timeframe=timeframe, candle_time_utc=candle_time)
                self.session.add(row)
                inserted += 1
            else:
                updated += 1
            row.open = Decimal(str(raw["opening_price"]))
            row.high = Decimal(str(raw["high_price"]))
            row.low = Decimal(str(raw["low_price"]))
            row.close = Decimal(str(raw["trade_price"]))
            row.volume = Decimal(str(raw["candle_acc_trade_volume"]))
        self.session.commit()
        logger.debug(
            "candle_upsert_done market=%s timeframe=%s input=%s inserted=%s updated=%s",
            market,
            timeframe,
            len(candles),
            inserted,
            updated,
        )

    def clear_market_timeframe(self, market: str, timeframe: str) -> None:
        """특정 마켓/타임프레임 캔들을 모두 삭제한다."""
        self.session.execute(delete(Candle).where(Candle.market == market, Candle.timeframe == timeframe))
        self.session.commit()
        logger.warning("candle_cleared market=%s timeframe=%s", market, timeframe)
