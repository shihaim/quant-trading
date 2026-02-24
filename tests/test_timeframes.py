from datetime import datetime, timezone

from trader.utils.timeframes import floor_time, next_run_time, timeframe_to_timedelta


def test_timeframe_to_timedelta():
    assert timeframe_to_timedelta("15m").total_seconds() == 900


def test_floor_time():
    dt = datetime(2026, 2, 23, 14, 7, 31, tzinfo=timezone.utc)
    floored = floor_time(dt, "15m")
    assert floored == datetime(2026, 2, 23, 14, 0, 0, tzinfo=timezone.utc)


def test_next_run_time():
    dt = datetime(2026, 2, 23, 14, 7, 31, tzinfo=timezone.utc)
    nxt = next_run_time(dt, "15m", settle_delay_seconds=3)
    assert nxt == datetime(2026, 2, 23, 14, 15, 3, tzinfo=timezone.utc)

