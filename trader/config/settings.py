from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수(.env 포함)에서 런타임 설정을 로드한다."""

    trade_mode: Literal["REAL", "TEST", "PAPER", "SHADOW"] = Field(
        default="PAPER",
        validation_alias=AliasChoices("TRADE_MODE", "TRADING_MODE"),
    )
    upbit_access_key: str = Field(default="", alias="UPBIT_ACCESS_KEY")
    upbit_secret_key: str = Field(default="", alias="UPBIT_SECRET_KEY")
    upbit_base_url: str = Field(default="https://api.upbit.com", alias="UPBIT_BASE_URL")
    database_url: str = Field(default="sqlite:///./trading.db", alias="DATABASE_URL")
    poll_interval_seconds: int = Field(default=1, alias="POLL_INTERVAL_SECONDS")
    config_reload_seconds: int = Field(default=15, alias="CONFIG_RELOAD_SECONDS")
    min_strategy_candles: int = Field(default=120, alias="MIN_STRATEGY_CANDLES")
    order_retry_max: int = Field(default=3, alias="ORDER_RETRY_MAX")
    order_retry_backoff_seconds: float = Field(default=0.8, alias="ORDER_RETRY_BACKOFF_SECONDS")
    default_fee_rate: float = Field(default=0.0005, alias="DEFAULT_FEE_RATE")
    paper_initial_cash_krw: float = Field(default=1_000_000, alias="PAPER_INITIAL_CASH_KRW")
    enforce_market_allowlist: bool = Field(default=False, alias="ENFORCE_MARKET_ALLOWLIST")
    allowlist_markets: list[str] = Field(default_factory=lambda: ["KRW-BTC"], alias="ALLOWLIST_MARKETS")
    rehearsal_order_notional_krw: float = Field(default=6000.0, alias="REHEARSAL_ORDER_NOTIONAL_KRW")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    ops_api_allow_origin: str = Field(default="*", alias="OPS_API_ALLOW_ORIGIN")
    ops_api_auth_secret: str = Field(default="dev-ops-auth-secret-change-me", alias="OPS_API_AUTH_SECRET")
    ops_api_auth_token_ttl_seconds: int = Field(default=43200, alias="OPS_API_AUTH_TOKEN_TTL_SECONDS")
    ops_api_credentials_encryption_key: str = Field(
        default="dev-ops-credentials-encryption-key-change-me",
        alias="OPS_API_CREDENTIALS_ENCRYPTION_KEY",
    )
    ops_api_credentials_active_key_version: str = Field(
        default="v1",
        alias="OPS_API_CREDENTIALS_ACTIVE_KEY_VERSION",
    )
    ops_api_credentials_keyring_json: str = Field(
        default="{}",
        alias="OPS_API_CREDENTIALS_KEYRING_JSON",
    )
    ops_api_budget_window_seconds: int = Field(default=60, alias="OPS_API_BUDGET_WINDOW_SECONDS")
    ops_api_budget_me_limit: int = Field(default=120, alias="OPS_API_BUDGET_ME_LIMIT")
    ops_api_budget_admin_limit: int = Field(default=300, alias="OPS_API_BUDGET_ADMIN_LIMIT")

    model_config = SettingsConfigDict(
        env_file=Path(".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
