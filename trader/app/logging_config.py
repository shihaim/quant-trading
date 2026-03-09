from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import SplitResult, urlsplit, urlunsplit


class MaxLevelFilter(logging.Filter):
    """Allow records up to a specific level (inclusive)."""

    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.max_level


KST = timezone(timedelta(hours=9), name="Asia/Seoul")


class KstFormatter(logging.Formatter):
    """Always format log timestamps in Asia/Seoul."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=KST)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


def mask_connection_secret(value: str) -> str:
    """Mask password segments in DSN-style values while preserving routing context."""

    if not value:
        return value

    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value

    if parsed.password is None or parsed.hostname is None:
        return value

    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    userinfo = ""
    if parsed.username:
        userinfo = f"{parsed.username}:***@"

    netloc = userinfo + host
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    return urlunsplit(
        SplitResult(
            scheme=parsed.scheme,
            netloc=netloc,
            path=parsed.path,
            query=parsed.query,
            fragment=parsed.fragment,
        )
    )


def configure_file_logging(
    *,
    info_env_key: str,
    error_env_key: str,
    default_info_file: str,
    default_error_file: str,
) -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    info_log_file = os.getenv(info_env_key, default_info_file)
    error_log_file = os.getenv(error_env_key, default_error_file)
    rotate_max_bytes = int(os.getenv("LOG_ROTATE_MAX_BYTES", str(10 * 1024 * 1024)))
    rotate_backup_count = int(os.getenv("LOG_ROTATE_BACKUP_COUNT", "10"))

    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = KstFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

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
