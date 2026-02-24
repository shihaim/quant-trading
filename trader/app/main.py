import logging
import os

from trader.data.db import Base, SessionLocal, engine, run_lightweight_migrations
from trader.trading.scheduler import TradingScheduler


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    """DB를 초기화하고 자동매매 스케줄러 메인 루프를 시작한다."""
    _configure_logging()
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()
    session = SessionLocal()
    try:
        scheduler = TradingScheduler(session=session)
        scheduler.run_forever()
    finally:
        session.close()


if __name__ == "__main__":
    main()
