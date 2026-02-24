from __future__ import annotations

import threading
import time


class SimpleRateLimiter:
    """호출 간 최소 간격을 보장하는 단순 레이트 리미터."""

    def __init__(self, calls_per_second: float):
        """초당 허용 호출 수를 기반으로 간격을 계산한다."""
        if calls_per_second <= 0:
            raise ValueError("calls_per_second must be > 0")
        self.min_interval = 1.0 / calls_per_second
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """다음 호출 가능 시점까지 대기한다."""
        with self._lock:
            now = time.monotonic()
            wait_for = self.min_interval - (now - self._last)
            if wait_for > 0:
                time.sleep(wait_for)
            self._last = time.monotonic()
