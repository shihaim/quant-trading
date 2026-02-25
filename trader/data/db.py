from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from trader.config.settings import settings
from trader.utils.timeframes import SUPPORTED_TIMEFRAMES


class Base(DeclarativeBase):
    """SQLAlchemy 선언형 모델의 공통 베이스."""

    pass


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

TABLE_DOCS_EN = {
    "bot_config": "Runtime control and risk configuration (single active row).",
    "timeframe_config": "Executable timeframe rows with enable flags.",
    "candles": "OHLCV candle history by market and timeframe.",
    "orders": "Order intents and exchange status tracking.",
    "fills": "Trade fills linked to orders (idempotent by trade_id).",
    "positions": "Current position state per market.",
    "daily_equity": "Daily equity baseline and PnL snapshots (UTC date keyed).",
    "paper_wallet": "Paper-trading cash wallet.",
}

COLUMN_DOCS_EN = {
    "bot_config": {
        "id": "Primary key. Normally 1.",
        "is_enabled": "Global bot on/off switch.",
        "timeframe": "Legacy fallback timeframe when no enabled timeframe row exists.",
        "markets_json": "Target markets as JSON array string.",
        "target_exposure_pct": "Base BUY target exposure ratio (0-1).",
        "max_daily_loss_pct": "Daily loss halt threshold ratio.",
        "max_total_exposure_pct": "Maximum total exposure ratio.",
        "max_per_market_exposure_pct": "Maximum exposure ratio per market.",
        "updated_at": "Last update timestamp.",
    },
    "timeframe_config": {
        "id": "Primary key.",
        "timeframe": "Timeframe key (1m/3m/5m/15m/30m/60m/240m/day).",
        "is_enabled": "Whether this timeframe is enabled (1/0).",
        "updated_at": "Last update timestamp.",
    },
    "candles": {
        "id": "Primary key.",
        "market": "Market code such as KRW-BTC.",
        "timeframe": "Timeframe key.",
        "candle_time_utc": "Candle open time in UTC.",
        "open": "Open price.",
        "high": "High price.",
        "low": "Low price.",
        "close": "Close price.",
        "volume": "Trade volume.",
    },
    "orders": {
        "id": "Primary key.",
        "market": "Market code.",
        "side": "bid/ask.",
        "ord_type": "Order type (usually limit).",
        "requested_price": "Requested limit price.",
        "requested_volume": "Requested order volume.",
        "client_order_id": "Local idempotency key.",
        "upbit_identifier": "Exchange identifier used for recovery query.",
        "upbit_uuid": "Exchange order UUID.",
        "state": "Local order state.",
        "retry_count": "Retry count for submit/recovery.",
        "error_class": "Normalized error class.",
        "last_error": "Latest error message.",
        "exchange_response_raw": "Raw exchange payload snapshot.",
        "created_at": "Creation timestamp.",
        "updated_at": "Last update timestamp.",
    },
    "fills": {
        "id": "Primary key.",
        "order_id": "Foreign key to orders.id.",
        "trade_id": "Unique fill/trade id from exchange.",
        "price": "Fill price.",
        "volume": "Fill volume.",
        "fee": "Fee amount.",
        "is_applied": "Whether portfolio application is done.",
        "executed_at": "Fill execution timestamp.",
    },
    "positions": {
        "market": "Primary key market code.",
        "qty": "Current position quantity.",
        "avg_price": "Average entry price.",
        "realized_pnl": "Accumulated realized PnL.",
        "unrealized_pnl": "Current unrealized PnL snapshot.",
        "updated_at": "Last update timestamp.",
    },
    "daily_equity": {
        "date_utc": "UTC date key.",
        "start_equity": "Start-of-day equity baseline.",
        "last_equity": "Latest equity snapshot for the day.",
        "realized_pnl": "Accumulated realized PnL snapshot.",
        "unrealized_pnl": "Current unrealized PnL snapshot.",
        "daily_pnl_abs": "Absolute day PnL from baseline.",
        "daily_pnl_pct": "Day PnL ratio from baseline.",
        "updated_at": "Last update timestamp.",
    },
    "paper_wallet": {
        "id": "Primary key (single row).",
        "cash_krw": "Paper wallet KRW cash balance.",
        "updated_at": "Last update timestamp.",
    },
}

TABLE_DOCS_KO = {
    "bot_config": "런타임 제어 및 리스크 설정(일반적으로 단일 행).",
    "timeframe_config": "실행 타임프레임 목록과 활성 여부.",
    "candles": "마켓/타임프레임별 OHLCV 캔들 이력.",
    "orders": "주문 의도 및 거래소 상태 추적.",
    "fills": "주문 체결 내역(trade_id 기준 중복 방지).",
    "positions": "마켓별 현재 포지션 상태.",
    "paper_wallet": "페이퍼 트레이딩 현금 지갑.",
}

COLUMN_DOCS_KO = {
    "bot_config": {
        "id": "기본 키. 보통 1.",
        "is_enabled": "봇 전체 실행 on/off 스위치.",
        "timeframe": "활성 타임프레임이 없을 때 사용하는 예비 타임프레임.",
        "markets_json": "대상 마켓 JSON 배열 문자열.",
        "target_exposure_pct": "BUY 신호 기본 목표 비중(0~1).",
        "max_daily_loss_pct": "일일 손실 한도(중지 기준) 비율.",
        "max_total_exposure_pct": "전체 익스포저 최대 비율.",
        "max_per_market_exposure_pct": "마켓별 익스포저 최대 비율.",
        "updated_at": "마지막 갱신 시각.",
    },
    "timeframe_config": {
        "id": "기본 키.",
        "timeframe": "타임프레임 키(1m/3m/5m/15m/30m/60m/240m/day).",
        "is_enabled": "해당 타임프레임 활성 여부(1/0).",
        "updated_at": "마지막 갱신 시각.",
    },
    "candles": {
        "id": "기본 키.",
        "market": "마켓 코드(예: KRW-BTC).",
        "timeframe": "타임프레임 키.",
        "candle_time_utc": "UTC 기준 캔들 시각.",
        "open": "시가.",
        "high": "고가.",
        "low": "저가.",
        "close": "종가.",
        "volume": "거래량.",
    },
    "orders": {
        "id": "기본 키.",
        "market": "마켓 코드.",
        "side": "매수/매도 구분(bid/ask).",
        "ord_type": "주문 타입(보통 limit).",
        "requested_price": "요청 지정가.",
        "requested_volume": "요청 수량.",
        "client_order_id": "로컬 멱등 키.",
        "upbit_identifier": "복구 조회용 거래소 identifier.",
        "upbit_uuid": "거래소 주문 UUID.",
        "state": "로컬 주문 상태.",
        "retry_count": "제출/복구 재시도 횟수.",
        "error_class": "정규화된 에러 분류.",
        "last_error": "최신 에러 메시지.",
        "exchange_response_raw": "거래소 응답 원문 스냅샷.",
        "created_at": "생성 시각.",
        "updated_at": "마지막 갱신 시각.",
    },
    "fills": {
        "id": "기본 키.",
        "order_id": "orders.id 외래 키.",
        "trade_id": "거래소 체결 고유 id.",
        "price": "체결 가격.",
        "volume": "체결 수량.",
        "fee": "수수료.",
        "is_applied": "포트폴리오 반영 여부.",
        "executed_at": "체결 시각.",
    },
    "positions": {
        "market": "기본 키 마켓 코드.",
        "qty": "현재 보유 수량.",
        "avg_price": "평균 단가.",
        "realized_pnl": "누적 실현 손익.",
        "unrealized_pnl": "평가 손익 스냅샷.",
        "updated_at": "마지막 갱신 시각.",
    },
    "paper_wallet": {
        "id": "기본 키(보통 단일 행).",
        "cash_krw": "페이퍼 지갑 KRW 현금 잔고.",
        "updated_at": "마지막 갱신 시각.",
    },
}

KST_VIEW_SQL = {
    "bot_config_kst": """
        CREATE VIEW bot_config_kst AS
        SELECT
            id,
            is_enabled,
            timeframe,
            markets_json,
            target_exposure_pct,
            max_daily_loss_pct,
            max_total_exposure_pct,
            max_per_market_exposure_pct,
            updated_at AS updated_at_utc,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM bot_config
    """,
    "timeframe_config_kst": """
        CREATE VIEW timeframe_config_kst AS
        SELECT
            id,
            timeframe,
            is_enabled,
            updated_at AS updated_at_utc,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM timeframe_config
    """,
    "candles_kst": """
        CREATE VIEW candles_kst AS
        SELECT
            id,
            market,
            timeframe,
            candle_time_utc,
            datetime(candle_time_utc, '+9 hours') AS candle_time_kst,
            open,
            high,
            low,
            close,
            volume
        FROM candles
    """,
    "orders_kst": """
        CREATE VIEW orders_kst AS
        SELECT
            id,
            market,
            side,
            ord_type,
            requested_price,
            requested_volume,
            client_order_id,
            upbit_identifier,
            upbit_uuid,
            state,
            retry_count,
            error_class,
            last_error,
            exchange_response_raw,
            created_at AS created_at_utc,
            datetime(created_at, '+9 hours') AS created_at_kst,
            updated_at AS updated_at_utc,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM orders
    """,
    "fills_kst": """
        CREATE VIEW fills_kst AS
        SELECT
            id,
            order_id,
            trade_id,
            price,
            volume,
            fee,
            is_applied,
            executed_at AS executed_at_utc,
            datetime(executed_at, '+9 hours') AS executed_at_kst
        FROM fills
    """,
    "positions_kst": """
        CREATE VIEW positions_kst AS
        SELECT
            market,
            qty,
            avg_price,
            realized_pnl,
            unrealized_pnl,
            updated_at AS updated_at_utc,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM positions
    """,
    "daily_equity_kst": """
        CREATE VIEW daily_equity_kst AS
        SELECT
            date_utc,
            datetime(date_utc || ' 00:00:00', '+9 hours') AS date_kst,
            start_equity,
            last_equity,
            realized_pnl,
            unrealized_pnl,
            daily_pnl_abs,
            daily_pnl_pct,
            updated_at AS updated_at_utc,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM daily_equity
    """,
    "paper_wallet_kst": """
        CREATE VIEW paper_wallet_kst AS
        SELECT
            id,
            cash_krw,
            updated_at AS updated_at_utc,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM paper_wallet
    """,
}


def run_lightweight_migrations() -> None:
    """Alembic 없이 SQLite에 필요한 추가 컬럼만 가볍게 반영한다."""
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "orders" in table_names:
            order_cols = {col["name"] for col in inspector.get_columns("orders")}
            if "retry_count" not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN retry_count INTEGER DEFAULT 0"))
            if "last_error" not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN last_error TEXT"))
            if "upbit_identifier" not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN upbit_identifier TEXT"))
            if "error_class" not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN error_class TEXT"))
            if "exchange_response_raw" not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN exchange_response_raw TEXT"))
        if "fills" in table_names:
            fill_cols = {col["name"] for col in inspector.get_columns("fills")}
            if "is_applied" not in fill_cols:
                conn.execute(text("ALTER TABLE fills ADD COLUMN is_applied BOOLEAN DEFAULT 0"))
        if "bot_config" in table_names:
            bot_cols = {col["name"] for col in inspector.get_columns("bot_config")}
            if "target_exposure_pct" not in bot_cols:
                conn.execute(text("ALTER TABLE bot_config ADD COLUMN target_exposure_pct NUMERIC(10,6) DEFAULT 0.10"))
            conn.execute(
                text(
                    "UPDATE bot_config "
                    "SET target_exposure_pct = 0.10 "
                    "WHERE target_exposure_pct IS NULL OR target_exposure_pct <= 0"
                )
            )
        if "timeframe_config" not in table_names:
            conn.execute(
                text(
                    """
                    CREATE TABLE timeframe_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timeframe VARCHAR(16) NOT NULL UNIQUE,
                        is_enabled BOOLEAN DEFAULT 0,
                        updated_at DATETIME
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_timeframe_config_timeframe ON timeframe_config(timeframe)"))
            conn.execute(text("CREATE INDEX ix_timeframe_config_is_enabled ON timeframe_config(is_enabled)"))
        if "daily_equity" not in table_names:
            conn.execute(
                text(
                    """
                    CREATE TABLE daily_equity (
                        date_utc DATE PRIMARY KEY,
                        start_equity NUMERIC(28,8) NOT NULL DEFAULT 0,
                        last_equity NUMERIC(28,8) NOT NULL DEFAULT 0,
                        realized_pnl NUMERIC(28,8) NOT NULL DEFAULT 0,
                        unrealized_pnl NUMERIC(28,8) NOT NULL DEFAULT 0,
                        daily_pnl_abs NUMERIC(28,8) NOT NULL DEFAULT 0,
                        daily_pnl_pct NUMERIC(28,8) NOT NULL DEFAULT 0,
                        updated_at DATETIME
                    )
                    """
                )
            )

        existing = conn.execute(text("SELECT timeframe FROM timeframe_config")).fetchall()
        existing_timeframes = {row[0] for row in existing}
        for timeframe in SUPPORTED_TIMEFRAMES:
            if timeframe not in existing_timeframes:
                conn.execute(
                    text(
                        "INSERT INTO timeframe_config (timeframe, is_enabled, updated_at) "
                        "VALUES (:timeframe, 0, CURRENT_TIMESTAMP)"
                    ),
                    {"timeframe": timeframe},
                )
        conn.execute(text("UPDATE timeframe_config SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))

        enabled_count = conn.execute(text("SELECT COUNT(*) FROM timeframe_config WHERE is_enabled = 1")).scalar_one()
        if enabled_count == 0:
            current = conn.execute(text("SELECT timeframe FROM bot_config WHERE id = 1")).scalar_one_or_none()
            selected = current if current in SUPPORTED_TIMEFRAMES else "15m"
            conn.execute(
                text(
                    "UPDATE timeframe_config "
                    "SET is_enabled = CASE WHEN timeframe = :timeframe THEN 1 ELSE 0 END"
                ),
                {"timeframe": selected},
            )

        _sync_schema_docs(conn)
        _sync_kst_views(conn)


def _sync_schema_docs(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_table_docs (
                table_name TEXT PRIMARY KEY,
                description_en TEXT NOT NULL DEFAULT '',
                description_ko TEXT NOT NULL DEFAULT ''
            )
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_column_docs (
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                description_en TEXT NOT NULL DEFAULT '',
                description_ko TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (table_name, column_name)
            )
            """
        )
    )

    table_doc_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(schema_table_docs)")).fetchall()}
    if "description" in table_doc_cols:
        conn.execute(
            text(
                """
                CREATE TABLE schema_table_docs_new (
                    table_name TEXT PRIMARY KEY,
                    description_en TEXT NOT NULL DEFAULT '',
                    description_ko TEXT NOT NULL DEFAULT ''
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO schema_table_docs_new (table_name, description_en, description_ko)
                SELECT
                    table_name,
                    COALESCE(NULLIF(description_en, ''), COALESCE(description, '')),
                    COALESCE(NULLIF(description_ko, ''), COALESCE(description, ''))
                FROM schema_table_docs
                """
            )
        )
        conn.execute(text("DROP TABLE schema_table_docs"))
        conn.execute(text("ALTER TABLE schema_table_docs_new RENAME TO schema_table_docs"))

    column_doc_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(schema_column_docs)")).fetchall()}
    if "description" in column_doc_cols:
        conn.execute(
            text(
                """
                CREATE TABLE schema_column_docs_new (
                    table_name TEXT NOT NULL,
                    column_name TEXT NOT NULL,
                    description_en TEXT NOT NULL DEFAULT '',
                    description_ko TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (table_name, column_name)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO schema_column_docs_new (table_name, column_name, description_en, description_ko)
                SELECT
                    table_name,
                    column_name,
                    COALESCE(NULLIF(description_en, ''), COALESCE(description, '')),
                    COALESCE(NULLIF(description_ko, ''), COALESCE(description, ''))
                FROM schema_column_docs
                """
            )
        )
        conn.execute(text("DROP TABLE schema_column_docs"))
        conn.execute(text("ALTER TABLE schema_column_docs_new RENAME TO schema_column_docs"))

    for table_name, description_en in TABLE_DOCS_EN.items():
        description_ko = TABLE_DOCS_KO.get(table_name, description_en)
        conn.execute(
            text(
                "INSERT OR REPLACE INTO schema_table_docs (table_name, description_en, description_ko) "
                "VALUES (:table_name, :description_en, :description_ko)"
            ),
            {
                "table_name": table_name,
                "description_en": description_en,
                "description_ko": description_ko,
            },
        )
    for table_name, columns_en in COLUMN_DOCS_EN.items():
        columns_ko = COLUMN_DOCS_KO.get(table_name, {})
        for column_name, description_en in columns_en.items():
            description_ko = columns_ko.get(column_name, description_en)
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO schema_column_docs (table_name, column_name, description_en, description_ko) "
                    "VALUES (:table_name, :column_name, :description_en, :description_ko)"
                ),
                {
                    "table_name": table_name,
                    "column_name": column_name,
                    "description_en": description_en,
                    "description_ko": description_ko,
                },
            )


def _sync_kst_views(conn) -> None:
    for view_name, sql in KST_VIEW_SQL.items():
        conn.execute(text(f"DROP VIEW IF EXISTS {view_name}"))
        conn.execute(text(sql))
