import logging
import os

from trader.config.settings import settings
from trader.data.db import Base, SessionLocal, engine, run_lightweight_migrations
from trader.trading.scheduler import TradingScheduler

logger = logging.getLogger(__name__)


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
    logger.info(
        "app_start mode=%s db=%s poll_interval=%s reload_interval=%s",
        settings.trade_mode,
        settings.database_url,
        settings.poll_interval_seconds,
        settings.config_reload_seconds,
    )
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()
    session = SessionLocal()
    try:
        scheduler = TradingScheduler(session=session)
        scheduler.run_forever()
    finally:
        logger.info("app_shutdown")
        session.close()


if __name__ == "__main__":
    main()
