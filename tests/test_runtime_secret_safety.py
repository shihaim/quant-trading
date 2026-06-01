from __future__ import annotations

from types import SimpleNamespace

import pytest

import trader.app.ops_api as ops_api_app


DEFAULT_AUTH_SECRET = "dev-ops-auth-secret-change-me"
DEFAULT_CREDENTIAL_KEY = "dev-ops-credentials-encryption-key-change-me"


def _patch_bootstrap(monkeypatch: pytest.MonkeyPatch) -> dict:
    calls = {"initialized": False, "served": False}

    monkeypatch.setattr(ops_api_app, "parse_args", lambda: SimpleNamespace(host="127.0.0.1", port=8080))
    monkeypatch.setattr(ops_api_app, "configure_file_logging", lambda **_: None)

    def fake_initialize_database() -> None:
        calls["initialized"] = True

    def fake_serve_ops_http(**_: object) -> None:
        calls["served"] = True

    monkeypatch.setattr(ops_api_app, "initialize_database", fake_initialize_database)
    monkeypatch.setattr(ops_api_app, "serve_ops_http", fake_serve_ops_http)
    monkeypatch.setattr(ops_api_app, "get_session_factory", lambda: object())
    return calls


def _set_ops_security(
    monkeypatch: pytest.MonkeyPatch,
    *,
    trade_mode: str,
    auth_secret: str = "prod-auth-secret-with-enough-entropy",
    credential_key: str = "prod-credential-key-with-enough-entropy",
    allow_origin: str = "https://ops.example.com",
) -> None:
    monkeypatch.setattr(ops_api_app.settings, "trade_mode", trade_mode)
    monkeypatch.setattr(ops_api_app.settings, "ops_api_auth_secret", auth_secret)
    monkeypatch.setattr(ops_api_app.settings, "ops_api_credentials_encryption_key", credential_key)
    monkeypatch.setattr(ops_api_app.settings, "ops_api_allow_origin", allow_origin)


def test_ops_api_main_rejects_default_auth_secret_in_real_mode(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_bootstrap(monkeypatch)
    _set_ops_security(monkeypatch, trade_mode="REAL", auth_secret=DEFAULT_AUTH_SECRET)

    with pytest.raises(RuntimeError, match="OPS_API_AUTH_SECRET"):
        ops_api_app.main()

    assert calls == {"initialized": False, "served": False}


def test_ops_api_main_rejects_default_credential_key_in_real_mode(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_bootstrap(monkeypatch)
    _set_ops_security(monkeypatch, trade_mode="REAL", credential_key=DEFAULT_CREDENTIAL_KEY)

    with pytest.raises(RuntimeError, match="OPS_API_CREDENTIALS_ENCRYPTION_KEY"):
        ops_api_app.main()

    assert calls == {"initialized": False, "served": False}


def test_ops_api_main_rejects_wildcard_cors_in_real_mode(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_bootstrap(monkeypatch)
    _set_ops_security(monkeypatch, trade_mode="REAL", allow_origin="*")

    with pytest.raises(RuntimeError, match="OPS_API_ALLOW_ORIGIN"):
        ops_api_app.main()

    assert calls == {"initialized": False, "served": False}


def test_ops_api_main_allows_local_paper_defaults(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_bootstrap(monkeypatch)
    _set_ops_security(
        monkeypatch,
        trade_mode="PAPER",
        auth_secret=DEFAULT_AUTH_SECRET,
        credential_key=DEFAULT_CREDENTIAL_KEY,
        allow_origin="*",
    )

    ops_api_app.main()

    assert calls == {"initialized": True, "served": True}
