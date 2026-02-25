import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from trader.config.settings import settings
from trader.data.db import Base, SessionLocal, engine, run_lightweight_migrations
from trader.trading.scheduler import TradingScheduler

logger = logging.getLogger(__name__)


class MaxLevelFilter(logging.Filter):
    """Allow records up to a specific level (inclusive)."""

    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.max_level


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    info_log_file = os.getenv("APP_INFO_LOG_FILE", "application-info.log")
    error_log_file = os.getenv("APP_ERROR_LOG_FILE", "application-error.log")
    rotate_max_bytes = int(os.getenv("LOG_ROTATE_MAX_BYTES", str(10 * 1024 * 1024)))
    rotate_backup_count = int(os.getenv("LOG_ROTATE_BACKUP_COUNT", "10"))

    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    info_file_handler = RotatingFileHandler(
        filename=log_dir / info_log_file,
        maxBytes=rotate_max_bytes,
        backupCount=rotate_backup_count,
        encoding="utf-8",
    )
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.addFilter(MaxLevelFilter(logging.WARNING))
    info_file_handler.setFormatter(formatter)

    error_file_handler = RotatingFileHandler(
        filename=log_dir / error_log_file,
        maxBytes=rotate_max_bytes,
        backupCount=rotate_backup_count,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(info_file_handler)
    root_logger.addHandler(error_file_handler)
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
