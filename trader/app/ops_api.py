from __future__ import annotations

import argparse
import logging

from trader.api.ops_http import serve_ops_http
from trader.app.logging_config import configure_file_logging
from trader.config.settings import settings
from trader.data.db import get_session_factory, initialize_database

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve Ops API for dashboard integration.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser.parse_args()


def main() -> None:
    configure_file_logging(
        info_env_key="OPS_API_INFO_LOG_FILE",
        error_env_key="OPS_API_ERROR_LOG_FILE",
        default_info_file="ops-api-info.log",
        default_error_file="ops-api-error.log",
    )
    args = parse_args()
    logger.info("ops_api_start host=%s port=%s mode=%s", args.host, args.port, settings.trade_mode)
    initialize_database()
    serve_ops_http(
        host=args.host,
        port=args.port,
        session_factory=get_session_factory(),
        trade_mode=settings.trade_mode,
        allow_origin=settings.ops_api_allow_origin,
    )


if __name__ == "__main__":
    main()
