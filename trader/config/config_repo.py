from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.data.models import BotConfig, TimeframeConfig
from trader.utils.timeframes import SUPPORTED_TIMEFRAMES


@dataclass(frozen=True)
class RuntimeConfig:
    """DB에서 읽은 봇 런타임 설정 스냅샷."""

    is_enabled: bool
    timeframe: str
    markets: list[str]
    max_daily_loss_pct: Decimal
    max_total_exposure_pct: Decimal
    max_per_market_exposure_pct: Decimal
    target_exposure_pct: Decimal = Decimal("0.10")


class ConfigRepo:
    def __init__(self, session: Session):
        """설정 조회/초기화에 사용할 DB 세션을 저장한다."""
        self.session = session

    def load(self) -> RuntimeConfig:
        """bot_config(id=1)를 읽고 없으면 기본값으로 생성해 반환한다."""
        row = self.session.execute(select(BotConfig).where(BotConfig.id == 1)).scalar_one_or_none()
        if row is None:
            row = BotConfig(id=1)
            self.session.add(row)
            self.session.commit()
            self.session.refresh(row)

        active_timeframe = self.session.execute(
            select(TimeframeConfig)
            .where(TimeframeConfig.is_enabled.is_(True))
            .order_by(TimeframeConfig.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        timeframe = active_timeframe.timeframe if active_timeframe else row.timeframe
        if timeframe not in SUPPORTED_TIMEFRAMES:
            timeframe = "15m"
        markets = json.loads(row.markets_json or "[]")
        target_exposure_pct = self._sanitize_target_exposure(row.target_exposure_pct)
        return RuntimeConfig(
            is_enabled=bool(row.is_enabled),
            timeframe=timeframe,
            markets=markets,
            max_daily_loss_pct=Decimal(row.max_daily_loss_pct),
            max_total_exposure_pct=Decimal(row.max_total_exposure_pct),
            max_per_market_exposure_pct=Decimal(row.max_per_market_exposure_pct),
            target_exposure_pct=target_exposure_pct,
        )

    @staticmethod
    def _sanitize_target_exposure(raw: Decimal | str | float | int | None) -> Decimal:
        try:
            value = Decimal(str(raw))
        except Exception:
            return Decimal("0.10")
        if value <= 0:
            return Decimal("0.10")
        if value > Decimal("1"):
            return Decimal("1")
        return value
