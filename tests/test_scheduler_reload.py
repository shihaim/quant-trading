from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from trader.config.config_repo import RuntimeConfig
from trader.trading.scheduler import SchedulerState, TradingScheduler
from trader.utils.timeframes import next_run_time


class _RepoStub:
    def __init__(self, cfg: RuntimeConfig):
        self._cfg = cfg

    def load(self) -> RuntimeConfig:
        return self._cfg


class _NotifierStub:
    def __init__(self):
        self.messages: list[str] = []

    def send(self, text: str) -> None:
        self.messages.append(text)


def _cfg(timeframe: str) -> RuntimeConfig:
    return RuntimeConfig(
        is_enabled=True,
        timeframe=timeframe,
        markets=["KRW-BTC"],
        max_daily_loss_pct=Decimal("0.02"),
        max_total_exposure_pct=Decimal("0.30"),
        max_per_market_exposure_pct=Decimal("0.10"),
    )


def _scheduler_with(cfg: RuntimeConfig) -> tuple[TradingScheduler, _NotifierStub]:
    scheduler = TradingScheduler.__new__(TradingScheduler)
    scheduler.config_repo = _RepoStub(cfg)
    notifier = _NotifierStub()
    scheduler.notifier = notifier
    return scheduler, notifier


def test_reload_keeps_next_run_when_timeframe_unchanged():
    scheduler, notifier = _scheduler_with(_cfg("15m"))
    state = SchedulerState(
        runtime_config=_cfg("15m"),
        next_run_at=datetime(2026, 2, 24, 5, 30, 3, tzinfo=timezone.utc),
        last_config_reload_at=datetime(2026, 2, 24, 5, 20, 0, tzinfo=timezone.utc),
        next_status_notify_at=datetime(2026, 2, 24, 9, 0, 0, tzinfo=timezone.utc),
    )
    now = datetime(2026, 2, 24, 5, 25, 0, tzinfo=timezone.utc)

    updated = scheduler._reload_config(state, now)

    assert updated.next_run_at == state.next_run_at
    assert updated.runtime_config.timeframe == "15m"
    assert updated.last_config_reload_at == now
    assert notifier.messages == []


def test_reload_realigns_next_run_when_timeframe_changes():
    scheduler, notifier = _scheduler_with(_cfg("5m"))
    state = SchedulerState(
        runtime_config=_cfg("15m"),
        next_run_at=datetime(2026, 2, 24, 5, 30, 3, tzinfo=timezone.utc),
        last_config_reload_at=datetime(2026, 2, 24, 5, 20, 0, tzinfo=timezone.utc),
        next_status_notify_at=datetime(2026, 2, 24, 9, 0, 0, tzinfo=timezone.utc),
    )
    now = datetime(2026, 2, 24, 5, 25, 0, tzinfo=timezone.utc)

    updated = scheduler._reload_config(state, now)

    assert updated.next_run_at == next_run_time(now, "5m")
    assert updated.runtime_config.timeframe == "5m"
    assert updated.last_config_reload_at == now
    assert len(notifier.messages) == 1
    assert "timeframe changed: 15m -> 5m" in notifier.messages[0]
