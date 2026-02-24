from __future__ import annotations

import json
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ErrorInfo:
    """주문/연동 오류를 표준화한 구조."""

    error_class: str
    message: str
    status_code: int | None = None
    exchange_code: str | None = None


def classify_exception(exc: Exception) -> ErrorInfo:
    """예외를 운영 친화적인 오류 클래스로 분류한다."""
    if isinstance(exc, OrderValidationError):
        return ErrorInfo(error_class="VALIDATION_ERROR", message=str(exc))
    if isinstance(exc, httpx.TimeoutException):
        return ErrorInfo(error_class="NETWORK_TIMEOUT", message=str(exc))
    if isinstance(exc, httpx.HTTPStatusError):
        return _classify_http_status_error(exc)
    if isinstance(exc, httpx.RequestError):
        return ErrorInfo(error_class="NETWORK_TIMEOUT", message=str(exc))
    return ErrorInfo(error_class="UNKNOWN", message=str(exc))


def _classify_http_status_error(exc: httpx.HTTPStatusError) -> ErrorInfo:
    status = exc.response.status_code
    payload = _safe_json(exc.response.text)
    exchange_code = payload.get("error", {}).get("name") if isinstance(payload, dict) else None
    exchange_message = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
    message = exchange_message or str(exc)
    if status == 429:
        return ErrorInfo(error_class="RATE_LIMIT", message=message, status_code=status, exchange_code=exchange_code)
    if status in (401, 403):
        return ErrorInfo(error_class="AUTH_ERROR", message=message, status_code=status, exchange_code=exchange_code)
    if status in (400, 422):
        return ErrorInfo(
            error_class="VALIDATION_ERROR",
            message=message,
            status_code=status,
            exchange_code=exchange_code,
        )
    return ErrorInfo(error_class="UNKNOWN", message=message, status_code=status, exchange_code=exchange_code)


def _safe_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        return {}


class OrderValidationError(ValueError):
    """주문 사전검증 실패를 표현하는 예외."""

