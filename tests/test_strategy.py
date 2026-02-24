from decimal import Decimal

from trader.trading.strategy import EmaCrossStrategy


def test_set_buy_target_exposure_pct_updates_strategy_value():
    strategy = EmaCrossStrategy()
    strategy.set_buy_target_exposure_pct(Decimal("0.15"))
    assert strategy.buy_target_exposure_pct == Decimal("0.15")


def test_set_buy_target_exposure_pct_caps_to_one():
    strategy = EmaCrossStrategy()
    strategy.set_buy_target_exposure_pct(Decimal("1.5"))
    assert strategy.buy_target_exposure_pct == Decimal("1")
