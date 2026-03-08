from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from trader.config.config_repo import RuntimeConfig
from trader.trading.scheduler import TradingScheduler


@dataclass
class _Metric:
    intent: str | None
    slippage_pct: Decimal


@dataclass
class _Order:
    id: int
    market: str
    side: str


class _ExecutionStub:
    def latest_trade_metric(self, order_id: int):
        return _Metric(intent="ENTRY", slippage_pct=Decimal("0.01"))

    def count_slippage_breaches_since(self, **kwargs) -> int:
        return 1


class _NotifierStub:
    def __init__(self):
        self.messages: list[str] = []

    def send(self, text: str) -> None:
        self.messages.append(text)


class _RuntimeState:
    def __init__(self, is_enabled: bool):
        self.is_enabled = is_enabled


class _ConfigRepoStub:
    def __init__(self):
        self.calls: list[tuple[int, bool]] = []

    def set_runtime_enabled(self, *, user_id: int, enabled: bool):
        self.calls.append((user_id, enabled))
        return _RuntimeState(is_enabled=False)


def _cfg() -> RuntimeConfig:
    return RuntimeConfig(
        is_enabled=True,
        timeframe="15m",
        markets=["KRW-BTC"],
        max_daily_loss_pct=Decimal("0.02"),
        max_total_exposure_pct=Decimal("0.30"),
        max_per_market_exposure_pct=Decimal("0.10"),
        slippage_budget_entry_pct=Decimal("0.0005"),
        slippage_budget_exit_pct=Decimal("0.0020"),
        slippage_budget_breach_halt_count=1,
    )


def test_slippage_auto_halt_disables_user_runtime_not_global_bot_row():
    scheduler = TradingScheduler.__new__(TradingScheduler)
    scheduler.user_id = 7
    scheduler.execution = _ExecutionStub()
    scheduler.notifier = _NotifierStub()
    scheduler.config_repo = _ConfigRepoStub()

    scheduler._handle_slippage_budget(_cfg(), _Order(id=11, market="KRW-BTC", side="bid"))

    assert scheduler.config_repo.calls == [(7, False)]
    assert any("HALT user=7 by slippage budget breaches" in msg for msg in scheduler.notifier.messages)
