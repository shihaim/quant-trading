from trader.trading.order_policy import OrderIntent, OrderPolicy, OrderPolicyConfig


def test_entry_policy_defaults():
    decision = OrderPolicy().decide(OrderIntent.ENTRY, OrderPolicyConfig())
    assert decision.intent == OrderIntent.ENTRY
    assert decision.order_type == "LIMIT"
    assert decision.fill_timeout_sec == 10
    assert decision.max_reprice_attempts == 2
    assert decision.allow_market_fallback is False


def test_exit_policy_stop_uses_aggressive_limit():
    cfg = OrderPolicyConfig(allow_market_fallback_on_exit=True)
    decision = OrderPolicy().decide(OrderIntent.EXIT, cfg, is_stop=True)
    assert decision.intent == OrderIntent.EXIT
    assert decision.order_type == "AGGRESSIVE_LIMIT"
    assert decision.fill_timeout_sec == 4
    assert decision.allow_market_fallback is True


def test_rebalance_policy_is_conservative():
    decision = OrderPolicy().decide(OrderIntent.REBALANCE, OrderPolicyConfig())
    assert decision.intent == OrderIntent.REBALANCE
    assert decision.order_type == "LIMIT"
    assert decision.max_reprice_attempts == 1
