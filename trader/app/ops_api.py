from __future__ import annotations

import argparse
import logging

from trader.api.ops_http import serve_ops_http
from trader.config.settings import settings
from trader.data.db import get_session_factory, initialize_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve Ops API for dashboard integration.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    initialize_database()
    args = parse_args()
    serve_ops_http(
        host=args.host,
        port=args.port,
        session_factory=get_session_factory(),
        trade_mode=settings.trade_mode,
        allow_origin=settings.ops_api_allow_origin,
    )


if __name__ == "__main__":
    main()

