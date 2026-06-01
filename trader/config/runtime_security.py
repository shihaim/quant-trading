from __future__ import annotations

from typing import Protocol


DEFAULT_OPS_API_AUTH_SECRET = "dev-ops-auth-secret-change-me"
DEFAULT_OPS_API_CREDENTIALS_ENCRYPTION_KEY = "dev-ops-credentials-encryption-key-change-me"
PRODUCTION_TRADE_MODES = {"REAL", "TEST", "SHADOW"}


class OpsRuntimeSecuritySettings(Protocol):
    trade_mode: str
    ops_api_auth_secret: str
    ops_api_credentials_encryption_key: str
    ops_api_allow_origin: str
    ops_api_env: str


def is_production_like_ops_runtime(settings: OpsRuntimeSecuritySettings) -> bool:
    mode = str(getattr(settings, "trade_mode", "") or "").upper()
    env = str(getattr(settings, "ops_api_env", "") or "").strip().lower()
    return mode in PRODUCTION_TRADE_MODES or env in {"prod", "production"}


def validate_ops_runtime_security(settings: OpsRuntimeSecuritySettings) -> None:
    """Reject unsafe Ops API runtime settings before serving production-like traffic."""

    if not is_production_like_ops_runtime(settings):
        return

    auth_secret = str(getattr(settings, "ops_api_auth_secret", "") or "").strip()
    if not auth_secret or auth_secret == DEFAULT_OPS_API_AUTH_SECRET:
        raise RuntimeError(
            "OPS_API_AUTH_SECRET must be set to a non-default value for production-like Ops API runtime"
        )

    credential_key = str(getattr(settings, "ops_api_credentials_encryption_key", "") or "").strip()
    if not credential_key or credential_key == DEFAULT_OPS_API_CREDENTIALS_ENCRYPTION_KEY:
        raise RuntimeError(
            "OPS_API_CREDENTIALS_ENCRYPTION_KEY must be set to a non-default value for production-like Ops API runtime"
        )

    allow_origin = str(getattr(settings, "ops_api_allow_origin", "") or "").strip()
    if allow_origin == "*":
        raise RuntimeError("OPS_API_ALLOW_ORIGIN must be restricted for production-like Ops API runtime")
