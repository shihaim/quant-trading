import logging

from trader.app.logging_config import configure_file_logging, mask_connection_secret
from trader.config.settings import settings
from trader.data.db import SessionLocal, initialize_database
from trader.trading.scheduler import TradingScheduler

logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize DB and run the trading scheduler loop."""
    configure_file_logging(
        info_env_key="APP_INFO_LOG_FILE",
        error_env_key="APP_ERROR_LOG_FILE",
        default_info_file="application-info.log",
        default_error_file="application-error.log",
    )
    logger.info(
        "app_start mode=%s db=%s poll_interval=%s reload_interval=%s",
        settings.trade_mode,
        mask_connection_secret(settings.database_url),
        settings.poll_interval_seconds,
        settings.config_reload_seconds,
    )
    initialize_database()
    session = SessionLocal()
    try:
        scheduler = TradingScheduler(session=session)
        scheduler.run_forever()
    finally:
        logger.info("app_shutdown")
        session.close()


if __name__ == "__main__":
    main()
