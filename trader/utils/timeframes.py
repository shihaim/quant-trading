from __future__ import annotations

from datetime import datetime, timedelta, timezone


SUPPORTED_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "60m", "240m", "day"]


_TF_TO_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "60m": 60,
    "240m": 240,
    "day": 24 * 60,
}


def timeframe_to_timedelta(timeframe: str) -> timedelta:
    """타임프레임 문자열을 timedelta로 변환한다."""
    if timeframe not in _TF_TO_MINUTES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return timedelta(minutes=_TF_TO_MINUTES[timeframe])


def floor_time(dt: datetime, timeframe: str) -> datetime:
    """시각을 타임프레임 경계로 내림(floor)한다."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    step = timeframe_to_timedelta(timeframe)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = dt - epoch
    floored = int(delta.total_seconds() // step.total_seconds()) * step.total_seconds()
    return epoch + timedelta(seconds=floored)


def next_run_time(now: datetime, timeframe: str, settle_delay_seconds: int = 3) -> datetime:
    """다음 봉 마감 실행 시각을 계산한다."""
    return floor_time(now, timeframe) + timeframe_to_timedelta(timeframe) + timedelta(seconds=settle_delay_seconds)


def timeframe_to_upbit_unit(timeframe: str) -> tuple[str, int]:
    """타임프레임을 업비트 캔들 API 단위로 변환한다."""
    if timeframe == "day":
        return ("days", 1)
    minutes = _TF_TO_MINUTES.get(timeframe)
    if minutes is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return ("minutes", minutes)
