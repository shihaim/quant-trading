from decimal import Decimal

from trader.trading.risk import should_skip_rebalance


def test_should_skip_rebalance_true_when_delta_below_threshold():
    assert (
        should_skip_rebalance(
            current_exposure_pct=Decimal("0.30"),
            target_exposure_pct=Decimal("0.33"),
            min_rebalance_threshold_pct=Decimal("0.05"),
        )
        is True
    )


def test_should_skip_rebalance_false_when_delta_at_or_above_threshold():
    assert (
        should_skip_rebalance(
            current_exposure_pct=Decimal("0.30"),
            target_exposure_pct=Decimal("0.36"),
            min_rebalance_threshold_pct=Decimal("0.05"),
        )
        is False
    )
