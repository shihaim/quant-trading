from decimal import Decimal

from trader.config.config_repo import RuntimeConfig
from trader.trading.risk import RiskEngine
from trader.trading.strategy import StrategySignal


def _cfg() -> RuntimeConfig:
    return RuntimeConfig(
        is_enabled=True,
        timeframe="15m",
        markets=["KRW-BTC"],
        max_daily_loss_pct=Decimal("0.02"),
        max_total_exposure_pct=Decimal("0.30"),
        max_per_market_exposure_pct=Decimal("0.10"),
    )


def test_halts_on_daily_loss():
    engine = RiskEngine()
    decision = engine.evaluate(
        signal=StrategySignal(action="BUY", target_exposure_pct=Decimal("0.2"), reason="x"),
        config=_cfg(),
        daily_pnl_pct=Decimal("-0.03"),
    )
    assert decision.halted is True


def test_caps_exposure():
    engine = RiskEngine()
    decision = engine.evaluate(
        signal=StrategySignal(action="BUY", target_exposure_pct=Decimal("0.2"), reason="x"),
        config=_cfg(),
        daily_pnl_pct=Decimal("0"),
    )
    assert decision.halted is False
    assert decision.target_exposure_pct == Decimal("0.10")


def test_halts_on_weekly_loss():
    engine = RiskEngine()
    cfg = RuntimeConfig(
        is_enabled=True,
        timeframe="15m",
        markets=["KRW-BTC"],
        max_daily_loss_pct=Decimal("0.02"),
        max_weekly_loss_pct=Decimal("0.03"),
        max_total_exposure_pct=Decimal("0.30"),
        max_per_market_exposure_pct=Decimal("0.10"),
    )
    decision = engine.evaluate(
        signal=StrategySignal(action="BUY", target_exposure_pct=Decimal("0.2"), reason="x"),
        config=cfg,
        daily_pnl_pct=Decimal("0"),
        weekly_pnl_pct=Decimal("-0.031"),
    )
    assert decision.halted is True
    assert decision.reason == "weekly_loss_limit"


def test_halts_on_daily_order_limit():
    engine = RiskEngine()
    cfg = RuntimeConfig(
        is_enabled=True,
        timeframe="15m",
        markets=["KRW-BTC"],
        max_daily_loss_pct=Decimal("0.02"),
        max_total_exposure_pct=Decimal("0.30"),
        max_per_market_exposure_pct=Decimal("0.10"),
        max_new_orders_per_day=2,
    )
    decision = engine.evaluate(
        signal=StrategySignal(action="BUY", target_exposure_pct=Decimal("0.2"), reason="x"),
        config=cfg,
        daily_pnl_pct=Decimal("0"),
        new_orders_today=2,
    )
    assert decision.halted is True
    assert decision.reason == "new_orders_daily_limit"

