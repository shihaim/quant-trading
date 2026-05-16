from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from decimal import Decimal

from trader.config.config_repo import ConfigRepo
from trader.config.settings import settings
from trader.data.candle_service import CandleService
from trader.data.db import Base, SessionLocal, engine, run_lightweight_migrations
from trader.exchange.upbit_client import UpbitClient
from trader.trading.execution import ExecutionEngine
from trader.trading.order_states import LOCAL_OPEN_STATES
from trader.trading.portfolio import PortfolioService
from trader.trading.reconcile import ReconcileService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P1 rehearsal helper")
    parser.add_argument("--scenario", required=True, choices=["smoke", "order-cancel"])
    parser.add_argument("--minutes", type=int, default=10, help="for smoke scenario")
    parser.add_argument("--interval", type=int, default=10, help="seconds between loops for smoke")
    parser.add_argument("--market", default="", help="target market, default from runtime config")
    parser.add_argument("--distance-pct", type=float, default=0.05, help="far limit distance from last price")
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="explicit user id for V3 user-scoped rehearsal; required outside PAPER mode",
    )
    return parser.parse_args()


def _resolve_rehearsal_user_id(config_repo: ConfigRepo, *, explicit_user_id: int | None) -> int:
    if explicit_user_id is not None:
        return max(1, int(explicit_user_id))
    if settings.trade_mode.upper() != "PAPER":
        raise ValueError("user_id_required")
    return int(config_repo.resolve_owner_user_id())


def _build_runtime(*, explicit_user_id: int | None = None):
    session = SessionLocal()
    config_repo = ConfigRepo(session)
    user_id = _resolve_rehearsal_user_id(config_repo, explicit_user_id=explicit_user_id)
    upbit = UpbitClient(
        base_url=settings.upbit_base_url,
        access_key=settings.upbit_access_key,
        secret_key=settings.upbit_secret_key,
        retry_max=settings.order_retry_max,
        retry_backoff_seconds=settings.order_retry_backoff_seconds,
    )
    candle = CandleService(session, upbit)
    portfolio = PortfolioService(session)
    execution = ExecutionEngine(
        session=session,
        upbit_client=upbit,
        max_submit_retries=settings.order_retry_max,
        retry_backoff_seconds=settings.order_retry_backoff_seconds,
        trade_mode=settings.trade_mode,
        allowed_markets=set(settings.allowlist_markets) if settings.enforce_market_allowlist else set(),
    )
    reconcile = ReconcileService(session, upbit, portfolio, execution, user_id=user_id)
    return session, upbit, candle, portfolio, execution, reconcile, config_repo, user_id


def run_smoke(minutes: int, interval: int, *, user_id: int | None = None) -> None:
    session, upbit, candle, _, _, reconcile, config_repo, user_id = _build_runtime(explicit_user_id=user_id)
    try:
        cfg = config_repo.load_for_user(user_id)
        end_at = time.time() + (minutes * 60)
        loops = 0
        while time.time() < end_at:
            mark_prices: dict[str, Decimal] = {}
            for market in cfg.markets:
                candle.upsert_latest_complete(market, cfg.timeframe)
                rows = candle.recent_candles(market, cfg.timeframe, 1)
                if rows:
                    mark_prices[market] = Decimal(rows[-1].close)
            snap = reconcile.reconcile_all(cfg.markets, mark_prices=mark_prices)
            loops += 1
            print(
                f"[smoke] loop={loops} equity={snap.total_equity} cash={snap.cash_krw} "
                f"market_value={snap.market_value}"
            )
            time.sleep(max(interval, 1))
    finally:
        upbit.close()
        session.close()


def run_order_cancel(market: str, distance_pct: float, *, user_id: int | None = None) -> None:
    if settings.trade_mode != "REAL":
        raise ValueError("order-cancel scenario requires TRADE_MODE=REAL")
    session, upbit, candle, portfolio, execution, _, config_repo, user_id = _build_runtime(explicit_user_id=user_id)
    try:
        cfg = config_repo.load_for_user(user_id)
        target_market = market or (cfg.markets[0] if cfg.markets else "KRW-BTC")
        candle.upsert_latest_complete(target_market, cfg.timeframe)
        latest = candle.recent_candles(target_market, cfg.timeframe, 1)
        if not latest:
            raise RuntimeError(f"no candle for {target_market}")
        close = Decimal(latest[-1].close)
        far_price = close * (Decimal("1") - Decimal(str(distance_pct)))
        target_qty = Decimal(str(settings.rehearsal_order_notional_krw)) / far_price

        order = execution.place_target_order(
            market=target_market,
            current_qty=Decimal("0"),
            target_qty=target_qty,
            ref_price=far_price,
            idempotency_key=f"p1-order-cancel-{target_market}-{datetime.now(timezone.utc).isoformat()}",
            user_id=user_id,
        )
        if order is None:
            raise RuntimeError("order not created")
        print(
            f"[order-cancel] created state={order.state} market={order.market} "
            f"client_id={order.client_order_id} upbit_uuid={order.upbit_uuid}"
        )

        # keep local state fresh before cancel
        if order.state in LOCAL_OPEN_STATES or order.state == "OPEN":
            execution.sync_order(order)
        if order.upbit_uuid and order.state in (LOCAL_OPEN_STATES | {"OPEN"}):
            canceled = execution.cancel_order(order)
            print(
                f"[order-cancel] canceled state={canceled.state} client_id={canceled.client_order_id} "
                f"upbit_uuid={canceled.upbit_uuid}"
            )
        else:
            print(f"[order-cancel] skip_cancel state={order.state}")

        # apply any fills if present (normally 0 for far-limit cancel flow)
        applied = portfolio.apply_unapplied_fills(order, use_paper_wallet=False)
        print(f"[order-cancel] fills_applied={applied}")
    finally:
        upbit.close()
        session.close()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()
    args = parse_args()
    if args.scenario == "smoke":
        run_smoke(minutes=args.minutes, interval=args.interval, user_id=args.user_id)
        return
    if args.scenario == "order-cancel":
        run_order_cancel(market=args.market, distance_pct=args.distance_pct, user_id=args.user_id)
        return
    raise ValueError(f"unsupported scenario: {args.scenario}")


if __name__ == "__main__":
    main()
