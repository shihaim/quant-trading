from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from trader.exchange.rate_limiter import SimpleRateLimiter
from trader.exchange.upbit_auth import build_auth_header
from trader.utils.timeframes import timeframe_to_upbit_unit


logger = logging.getLogger(__name__)


class UpbitClient:
    def __init__(
        self,
        base_url: str,
        access_key: str,
        secret_key: str,
        calls_per_second: float = 7.0,
        retry_max: int = 3,
        retry_backoff_seconds: float = 0.8,
    ):
        """업비트 REST 호출 클라이언트를 초기화한다."""
        self.base_url = base_url.rstrip("/")
        self.access_key = access_key
        self.secret_key = secret_key
        self.rate_limiter = SimpleRateLimiter(calls_per_second=calls_per_second)
        self.retry_max = retry_max
        self.retry_backoff_seconds = retry_backoff_seconds
        self._chance_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self.client = httpx.Client(timeout=10.0)

    def close(self) -> None:
        """내부 HTTP 클라이언트를 정리한다."""
        self.client.close()

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None, auth: bool = False) -> Any:
        """레이트리밋/재시도를 포함한 공통 HTTP 요청을 수행한다."""
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            attempt += 1
            headers = {}
            if auth:
                # Retries must use a fresh nonce/JWT every time.
                headers.update(build_auth_header(self.access_key, self.secret_key, params=params))
            self.rate_limiter.wait()
            started_at = time.perf_counter()
            try:
                resp = self.client.request(method, url, params=params, headers=headers)
            except httpx.RequestError as exc:
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                logger.warning(
                    "업비트 요청 네트워크 오류: method=%s path=%s attempt=%s/%s elapsed_ms=%.1f error=%s",
                    method,
                    path,
                    attempt,
                    self.retry_max,
                    elapsed_ms,
                    exc,
                )
                if attempt >= self.retry_max:
                    raise
                backoff = self.retry_backoff_seconds * attempt
                logger.info(
                    "upbit_request retry method=%s path=%s attempt=%s/%s backoff_seconds=%.2f",
                    method,
                    path,
                    attempt,
                    self.retry_max,
                    backoff,
                )
                time.sleep(backoff)
                continue

            elapsed_ms = (time.perf_counter() - started_at) * 1000
            status_code = resp.status_code
            if status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "업비트 요청 재시도 가능 상태코드 수신: method=%s path=%s status=%s attempt=%s/%s elapsed_ms=%.1f",
                    method,
                    path,
                    status_code,
                    attempt,
                    self.retry_max,
                    elapsed_ms,
                )
                if attempt >= self.retry_max:
                    logger.error(
                        "업비트 요청 최종 실패: method=%s path=%s status=%s after_attempts=%s",
                        method,
                        path,
                        status_code,
                        attempt,
                    )
                    resp.raise_for_status()
                backoff = self.retry_backoff_seconds * attempt
                logger.info(
                    "upbit_request retry method=%s path=%s attempt=%s/%s backoff_seconds=%.2f",
                    method,
                    path,
                    attempt,
                    self.retry_max,
                    backoff,
                )
                time.sleep(backoff)
                continue

            if resp.is_error:
                logger.error(
                    "업비트 요청 HTTP 오류: method=%s path=%s status=%s attempt=%s elapsed_ms=%.1f",
                    method,
                    path,
                    status_code,
                    attempt,
                    elapsed_ms,
                )
            resp.raise_for_status()
            logger.debug(
                "upbit_request success method=%s path=%s status=%s attempt=%s elapsed_ms=%.1f",
                method,
                path,
                status_code,
                attempt,
                elapsed_ms,
            )
            return resp.json()

    def get_candles(self, market: str, timeframe: str, count: int = 200) -> list[dict[str, Any]]:
        """시세 캔들을 조회한다."""
        group, unit = timeframe_to_upbit_unit(timeframe)
        if group == "days":
            path = "/v1/candles/days"
        else:
            path = f"/v1/candles/minutes/{unit}"
        data = self._request("GET", path, params={"market": market, "count": count})
        return list(data)

    def get_accounts(self) -> list[dict[str, Any]]:
        """계좌 잔고 목록을 조회한다."""
        return self._request("GET", "/v1/accounts", auth=True)

    def get_open_orders(self, market: str | None = None) -> list[dict[str, Any]]:
        """미체결 주문 목록(wait/watch)을 조회한다."""
        params: dict[str, Any] = {"states[]": ["wait", "watch"]}
        if market:
            params["market"] = market
        return self._request("GET", "/v1/orders/open", params=params, auth=True)

    def get_order(self, order_uuid: str) -> dict[str, Any]:
        """주문 UUID로 단일 주문 상태를 조회한다."""
        return self._request("GET", "/v1/order", params={"uuid": order_uuid}, auth=True)

    def cancel_order(self, order_uuid: str) -> dict[str, Any]:
        """주문 UUID 기준으로 미체결 주문을 취소한다."""
        return self._request("DELETE", "/v1/order", params={"uuid": order_uuid}, auth=True)

    def get_order_by_identifier(self, identifier: str) -> dict[str, Any] | None:
        """identifier로 주문을 조회하고 없으면 None을 반환한다."""
        try:
            return self._request("GET", "/v1/order", params={"identifier": identifier}, auth=True)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    def create_order(
        self,
        market: str,
        side: str,
        ord_type: str,
        volume: str | None = None,
        price: str | None = None,
        identifier: str | None = None,
    ) -> dict[str, Any]:
        """신규 주문을 생성한다."""
        params: dict[str, Any] = {
            "market": market,
            "side": side,
            "ord_type": ord_type,
        }
        if volume is not None:
            params["volume"] = volume
        if price is not None:
            params["price"] = price
        if identifier:
            params["identifier"] = identifier
        return self._request("POST", "/v1/orders", params=params, auth=True)

    def test_order(
        self,
        market: str,
        side: str,
        ord_type: str,
        volume: str | None = None,
        price: str | None = None,
        identifier: str | None = None,
    ) -> dict[str, Any]:
        """실주문 없이 주문 파라미터를 검증한다(/v1/orders/test)."""
        params: dict[str, Any] = {
            "market": market,
            "side": side,
            "ord_type": ord_type,
        }
        if volume is not None:
            params["volume"] = volume
        if price is not None:
            params["price"] = price
        if identifier:
            params["identifier"] = identifier
        return self._request("POST", "/v1/orders/test", params=params, auth=True)

    def get_order_chance(self, market: str, cache_ttl_seconds: int = 900) -> dict[str, Any]:
        """주문 가능 정보(chance)를 조회하고 TTL 캐시에 저장한다."""
        now = time.monotonic()
        cached = self._chance_cache.get(market)
        if cached and now < cached[0]:
            logger.debug("upbit_chance cache_hit market=%s expires_in=%.1f", market, max(0.0, cached[0] - now))
            return cached[1]
        logger.debug("upbit_chance cache_miss market=%s", market)
        payload = self._request("GET", "/v1/orders/chance", params={"market": market}, auth=True)
        normalized = json.loads(json.dumps(payload))
        self._chance_cache[market] = (now + cache_ttl_seconds, normalized)
        return normalized
