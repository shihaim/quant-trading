from __future__ import annotations

import argparse
from decimal import Decimal

from trader.backtest.engine import BacktestConfig, BacktestEngine
from trader.data.db import Base, SessionLocal, engine, run_lightweight_migrations


def parse_args() -> argparse.Namespace:
    """로컬 DB 기반 백테스트 실행 인자를 파싱한다."""
    parser = argparse.ArgumentParser(description="Run local backtest with candles from DB")
    parser.add_argument("--market", required=True, help="e.g. KRW-BTC")
    parser.add_argument("--timeframe", required=True, help="e.g. 15m")
    parser.add_argument("--initial-cash", default="1000000", help="KRW initial cash")
    parser.add_argument("--fee-rate", default="0.0005", help="fee rate, e.g. 0.0005")
    parser.add_argument("--slippage-bps", default="5", help="slippage in bps")
    return parser.parse_args()


def main() -> None:
    """백테스트 1회를 실행하고 핵심 요약 지표를 출력한다."""
    args = parse_args()
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()
    session = SessionLocal()
    try:
        backtest_engine = BacktestEngine(session)
        result = backtest_engine.run(
            BacktestConfig(
                market=args.market,
                timeframe=args.timeframe,
                initial_cash_krw=Decimal(args.initial_cash),
                fee_rate=Decimal(args.fee_rate),
                slippage_bps=Decimal(args.slippage_bps),
            )
        )
        print(f"market={result.market} timeframe={result.timeframe}")
        print(f"trades={result.trades}")
        print(f"start_equity={result.start_equity:.2f} end_equity={result.end_equity:.2f}")
        print(f"total_return_pct={result.total_return_pct:.4f}")
        print(f"max_drawdown_pct={result.max_drawdown_pct:.4f}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
