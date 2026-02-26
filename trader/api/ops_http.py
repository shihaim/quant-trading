from __future__ import annotations

import json
import logging
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm import Session

from trader.ops.service import OpsService

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


def _parse_positive_int(raw: str | None, fallback: int, max_value: int) -> int:
    if raw is None:
        return fallback
    try:
        value = int(raw)
    except Exception:
        return fallback
    if value <= 0:
        return fallback
    return min(value, max_value)


def create_ops_handler(
    *,
    session_factory: SessionFactory,
    trade_mode: str,
    allow_origin: str,
) -> type[BaseHTTPRequestHandler]:
    class OpsApiHandler(BaseHTTPRequestHandler):
        server_version = "OpsApi/0.1"

        def _write_cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", allow_origin)
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _write_json(self, status_code: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self._write_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle_error(self, exc: Exception) -> None:
            logger.exception("ops_api_error path=%s", self.path, exc_info=exc)
            self._write_json(500, {"error": "internal_server_error", "message": str(exc)})

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            session = session_factory()
            try:
                service = OpsService(session=session, trade_mode=trade_mode)
                if parsed.path == "/api/ops/summary":
                    metrics_limit = _parse_positive_int(params.get("metrics_limit", [None])[0], fallback=200, max_value=1000)
                    needs_review_limit = _parse_positive_int(
                        params.get("needs_review_limit", [None])[0],
                        fallback=10,
                        max_value=100,
                    )
                    self._write_json(
                        200,
                        service.get_summary(metrics_limit=metrics_limit, needs_review_limit=needs_review_limit),
                    )
                    return
                if parsed.path == "/api/orders":
                    state = params.get("state", [None])[0]
                    limit = _parse_positive_int(params.get("limit", [None])[0], fallback=50, max_value=500)
                    self._write_json(200, service.list_orders(state=state, limit=limit))
                    return
                if parsed.path == "/api/pnl/daily":
                    days = _parse_positive_int(params.get("days", [None])[0], fallback=30, max_value=365)
                    tz = params.get("tz", ["UTC"])[0]
                    self._write_json(200, service.get_pnl_daily(days=days, tz=tz))
                    return
                if parsed.path == "/api/metrics/trade":
                    limit = _parse_positive_int(params.get("limit", [None])[0], fallback=200, max_value=1000)
                    self._write_json(200, service.list_trade_metrics(limit=limit))
                    return
                self._write_json(404, {"error": "not_found"})
            except Exception as exc:
                self._handle_error(exc)
            finally:
                session.close()

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            session = session_factory()
            try:
                service = OpsService(session=session, trade_mode=trade_mode)
                if parsed.path == "/api/bot/enable":
                    self._write_json(200, service.set_bot_enabled(enabled=True))
                    return
                if parsed.path == "/api/bot/disable":
                    self._write_json(200, service.set_bot_enabled(enabled=False))
                    return
                self._write_json(404, {"error": "not_found"})
            except Exception as exc:
                self._handle_error(exc)
            finally:
                session.close()

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._write_cors_headers()
            self.end_headers()

        def log_message(self, format: str, *args) -> None:
            logger.info("ops_api_access %s", format % args)

    return OpsApiHandler


def serve_ops_http(
    *,
    host: str,
    port: int,
    session_factory: SessionFactory,
    trade_mode: str,
    allow_origin: str,
) -> None:
    handler_cls = create_ops_handler(
        session_factory=session_factory,
        trade_mode=trade_mode,
        allow_origin=allow_origin,
    )
    server = ThreadingHTTPServer((host, port), handler_cls)
    logger.info("ops_api_started host=%s port=%s trade_mode=%s", host, port, trade_mode)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("ops_api_stopped signal=keyboard_interrupt")
    finally:
        server.server_close()

