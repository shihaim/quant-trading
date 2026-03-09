import logging

import trader.app.main as app_main
from trader.app.logging_config import KstFormatter, mask_connection_secret


def test_mask_connection_secret_hides_password_and_keeps_route_details():
    masked = mask_connection_secret("postgresql+psycopg://trader:secret@postgres:5432/trading")

    assert masked == "postgresql+psycopg://trader:***@postgres:5432/trading"


def test_mask_connection_secret_keeps_host_when_port_is_omitted():
    masked = mask_connection_secret("postgresql://trader:secret@postgres/trading")

    assert masked == "postgresql://trader:***@postgres/trading"


def test_mask_connection_secret_preserves_query_string():
    masked = mask_connection_secret("postgresql://trader:secret@postgres:5432/trading?sslmode=require")

    assert masked == "postgresql://trader:***@postgres:5432/trading?sslmode=require"


def test_mask_connection_secret_handles_url_encoded_password():
    masked = mask_connection_secret("postgresql://trader:sec%40ret@postgres:5432/trading")

    assert masked == "postgresql://trader:***@postgres:5432/trading"


def test_mask_connection_secret_leaves_passwordless_values_unchanged():
    value = "sqlite:///./trading.db"

    assert mask_connection_secret(value) == value


class _DummySession:
    def close(self) -> None:
        return None


class _DummyScheduler:
    def __init__(self, *, session_factory):
        self.session_factory = session_factory

    def run_forever(self) -> None:
        return None


def test_main_logs_masked_database_url_without_touching_runtime(monkeypatch, caplog):
    monkeypatch.setattr(app_main, "configure_file_logging", lambda **kwargs: None)
    monkeypatch.setattr(app_main, "initialize_database", lambda: None)
    monkeypatch.setattr(app_main, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(app_main, "MultiUserTradingScheduler", _DummyScheduler)

    monkeypatch.setattr(
        app_main.settings,
        "database_url",
        "postgresql+psycopg://trader:secret@postgres:5432/trading",
    )
    monkeypatch.setattr(app_main.settings, "trade_mode", "PAPER")
    monkeypatch.setattr(app_main.settings, "poll_interval_seconds", 1)
    monkeypatch.setattr(app_main.settings, "config_reload_seconds", 15)

    with caplog.at_level(logging.INFO):
        app_main.main()

    joined = "\n".join(caplog.messages)
    assert "app_start" in joined
    assert "secret" not in joined
    assert "postgresql+psycopg://trader:***@postgres:5432/trading" in joined


def test_kst_formatter_formats_time_in_asia_seoul():
    formatter = KstFormatter("%(asctime)s")
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "message", (), None)
    record.created = 0

    assert formatter.formatTime(record).startswith("1970-01-01 09:00:00")
