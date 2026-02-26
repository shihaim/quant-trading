from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from trader.config.settings import settings
from trader.utils.timeframes import SUPPORTED_TIMEFRAMES


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

TABLE_DOCS_EN = {
    "bot_config": "Runtime control and risk configuration (single active row).",
    "timeframe_config": "Executable timeframe rows with enable flags.",
    "candles": "OHLCV candle history by market and timeframe.",
    "orders": "Order intents and exchange status tracking.",
    "fills": "Trade fills linked to orders (idempotent by trade_id).",
    "trade_metrics": "Per-order execution quality metrics (VWAP, slippage, fill time).",
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
        "daily_loss_basis": "Daily loss basis (TOTAL or REALIZED_ONLY).",
        "min_rebalance_threshold_pct": "Skip order if exposure delta is below this threshold.",
        "min_order_krw_buffer": "Extra KRW buffer above minimum order notional.",
        "fill_timeout_sec_entry": "Fill timeout in seconds for ENTRY intent.",
        "fill_timeout_sec_exit": "Fill timeout in seconds for EXIT intent.",
        "fill_timeout_sec_rebalance": "Fill timeout in seconds for REBALANCE intent.",
        "max_reprice_attempts_entry": "Maximum reprice attempts for ENTRY intent.",
        "max_reprice_attempts_exit": "Maximum reprice attempts for EXIT intent.",
        "max_reprice_attempts_rebalance": "Maximum reprice attempts for REBALANCE intent.",
        "reprice_step_bps": "Reprice step size in basis points.",
        "slippage_budget_entry_pct": "Slippage budget ratio for ENTRY.",
        "slippage_budget_exit_pct": "Slippage budget ratio for EXIT.",
        "slippage_budget_breach_halt_count": "Auto-halt when breaches reach this count.",
        "status_notify_interval_seconds": "Periodic status notification interval.",
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
        "intent": "ENTRY/EXIT/REBALANCE intent.",
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
    "trade_metrics": {
        "id": "Primary key.",
        "order_id": "Foreign key to orders.id (1 row per order).",
        "intent": "ENTRY/EXIT/REBALANCE.",
        "intended_price": "Intended order price at submit.",
        "filled_vwap_price": "VWAP of fills.",
        "slippage_abs": "Absolute slippage (unfavorable positive).",
        "slippage_pct": "Slippage ratio.",
        "fee_abs": "Total fee amount.",
        "time_to_fill_ms": "Milliseconds from order create to last fill.",
        "partial_fill_count": "Number of fills for this order.",
        "created_at": "Metric creation time.",
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
        "start_realized_pnl": "Start-of-day realized PnL baseline.",
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
    "bot_config": "런타임 제어 및 리스크 설정(단일 활성 행).",
    "timeframe_config": "실행 대상 타임프레임과 활성화 상태.",
    "candles": "마켓/타임프레임별 OHLCV 캔들 이력.",
    "orders": "주문 의도와 거래소 상태 추적.",
    "fills": "주문과 연결된 체결 내역(trade_id 기준 멱등).",
    "trade_metrics": "주문별 집행 품질 지표(VWAP, 슬리피지, 체결 시간).",
    "positions": "마켓별 현재 포지션 상태.",
    "daily_equity": "일별 자산 기준선 및 손익 스냅샷(UTC 날짜 키).",
    "paper_wallet": "페이퍼 트레이딩 현금 지갑.",
}

COLUMN_DOCS_KO = {
    "bot_config": {
        "id": "기본 키. 일반적으로 1.",
        "is_enabled": "봇 전역 on/off 스위치.",
        "timeframe": "활성 타임프레임 행이 없을 때 사용하는 레거시 기본 타임프레임.",
        "markets_json": "대상 마켓 목록(JSON 배열 문자열).",
        "target_exposure_pct": "기본 BUY 목표 노출 비율(0-1).",
        "daily_loss_basis": "일일 손실 기준(TOTAL 또는 REALIZED_ONLY).",
        "min_rebalance_threshold_pct": "노출 비율 차이가 이 값보다 작으면 주문을 생략.",
        "min_order_krw_buffer": "최소 주문 금액에 추가로 요구하는 KRW 버퍼.",
        "fill_timeout_sec_entry": "ENTRY 의도 주문의 체결 대기 제한 시간(초).",
        "fill_timeout_sec_exit": "EXIT 의도 주문의 체결 대기 제한 시간(초).",
        "fill_timeout_sec_rebalance": "REBALANCE 의도 주문의 체결 대기 제한 시간(초).",
        "max_reprice_attempts_entry": "ENTRY 의도 주문의 최대 재호가 횟수.",
        "max_reprice_attempts_exit": "EXIT 의도 주문의 최대 재호가 횟수.",
        "max_reprice_attempts_rebalance": "REBALANCE 의도 주문의 최대 재호가 횟수.",
        "reprice_step_bps": "재호가 스텝 크기(bps).",
        "slippage_budget_entry_pct": "ENTRY 슬리피지 예산 비율.",
        "slippage_budget_exit_pct": "EXIT 슬리피지 예산 비율.",
        "slippage_budget_breach_halt_count": "예산 위반 횟수가 이 값에 도달하면 자동 중지.",
        "status_notify_interval_seconds": "주기 상태 알림 간격(초).",
        "max_daily_loss_pct": "일일 손실 중지 임계 비율.",
        "max_total_exposure_pct": "총 노출 최대 비율.",
        "max_per_market_exposure_pct": "마켓별 노출 최대 비율.",
        "updated_at": "마지막 수정 시각.",
    },
    "timeframe_config": {
        "id": "기본 키.",
        "timeframe": "타임프레임 키(1m/3m/5m/15m/30m/60m/240m/day).",
        "is_enabled": "해당 타임프레임 활성화 여부(1/0).",
        "updated_at": "마지막 수정 시각.",
    },
    "candles": {
        "id": "기본 키.",
        "market": "마켓 코드(예: KRW-BTC).",
        "timeframe": "타임프레임 키.",
        "candle_time_utc": "UTC 기준 캔들 시가 시각.",
        "open": "시가.",
        "high": "고가.",
        "low": "저가.",
        "close": "종가.",
        "volume": "거래량.",
    },
    "orders": {
        "id": "기본 키.",
        "market": "마켓 코드.",
        "side": "매수/매도(bid/ask).",
        "ord_type": "주문 유형(일반적으로 limit).",
        "requested_price": "요청한 지정가 가격.",
        "requested_volume": "요청한 주문 수량.",
        "client_order_id": "로컬 멱등 키.",
        "intent": "주문 의도(ENTRY/EXIT/REBALANCE).",
        "upbit_identifier": "복구 조회에 사용하는 거래소 식별자.",
        "upbit_uuid": "거래소 주문 UUID.",
        "state": "로컬 주문 상태.",
        "retry_count": "제출/복구 재시도 횟수.",
        "error_class": "정규화된 오류 클래스.",
        "last_error": "최신 오류 메시지.",
        "exchange_response_raw": "거래소 원본 응답 스냅샷.",
        "created_at": "생성 시각.",
        "updated_at": "마지막 수정 시각.",
    },
    "fills": {
        "id": "기본 키.",
        "order_id": "orders.id 외래 키.",
        "trade_id": "거래소 체결 고유 ID.",
        "price": "체결 가격.",
        "volume": "체결 수량.",
        "fee": "수수료 금액.",
        "is_applied": "포트폴리오 반영 여부.",
        "executed_at": "체결 시각.",
    },
    "trade_metrics": {
        "id": "기본 키.",
        "order_id": "orders.id 외래 키(주문당 1행).",
        "intent": "주문 의도(ENTRY/EXIT/REBALANCE).",
        "intended_price": "주문 제출 시 의도 가격.",
        "filled_vwap_price": "체결 VWAP 가격.",
        "slippage_abs": "절대 슬리피지(불리한 방향 양수).",
        "slippage_pct": "슬리피지 비율.",
        "fee_abs": "총 수수료 금액.",
        "time_to_fill_ms": "주문 생성부터 최종 체결까지 소요 시간(ms).",
        "partial_fill_count": "해당 주문의 체결 건수.",
        "created_at": "지표 생성 시각.",
    },
    "positions": {
        "market": "기본 키 마켓 코드.",
        "qty": "현재 보유 수량.",
        "avg_price": "평균 매입 단가.",
        "realized_pnl": "누적 실현 손익.",
        "unrealized_pnl": "현재 미실현 손익 스냅샷.",
        "updated_at": "마지막 수정 시각.",
    },
    "daily_equity": {
        "date_utc": "UTC 날짜 키.",
        "start_equity": "일 시작 시점 자산 기준선.",
        "start_realized_pnl": "일 시작 시점 실현 손익 기준선.",
        "last_equity": "당일 최신 자산 스냅샷.",
        "realized_pnl": "누적 실현 손익 스냅샷.",
        "unrealized_pnl": "현재 미실현 손익 스냅샷.",
        "daily_pnl_abs": "기준선 대비 당일 절대 손익.",
        "daily_pnl_pct": "기준선 대비 당일 손익 비율.",
        "updated_at": "마지막 수정 시각.",
    },
    "paper_wallet": {
        "id": "기본 키(단일 행).",
        "cash_krw": "페이퍼 지갑 KRW 현금 잔액.",
        "updated_at": "마지막 수정 시각.",
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
            daily_loss_basis,
            min_rebalance_threshold_pct,
            min_order_krw_buffer,
            fill_timeout_sec_entry,
            fill_timeout_sec_exit,
            fill_timeout_sec_rebalance,
            max_reprice_attempts_entry,
            max_reprice_attempts_exit,
            max_reprice_attempts_rebalance,
            reprice_step_bps,
            slippage_budget_entry_pct,
            slippage_budget_exit_pct,
            slippage_budget_breach_halt_count,
            status_notify_interval_seconds,
            max_daily_loss_pct,
            max_total_exposure_pct,
            max_per_market_exposure_pct,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM bot_config
    """,
    "timeframe_config_kst": """
        CREATE VIEW timeframe_config_kst AS
        SELECT
            id,
            timeframe,
            is_enabled,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM timeframe_config
    """,
    "candles_kst": """
        CREATE VIEW candles_kst AS
        SELECT
            id,
            market,
            timeframe,
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
            intent,
            upbit_identifier,
            upbit_uuid,
            state,
            retry_count,
            error_class,
            last_error,
            exchange_response_raw,
            datetime(created_at, '+9 hours') AS created_at_kst,
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
            datetime(executed_at, '+9 hours') AS executed_at_kst
        FROM fills
    """,
    "trade_metrics_kst": """
        CREATE VIEW trade_metrics_kst AS
        SELECT
            id,
            order_id,
            intent,
            intended_price,
            filled_vwap_price,
            slippage_abs,
            slippage_pct,
            fee_abs,
            time_to_fill_ms,
            partial_fill_count,
            datetime(created_at, '+9 hours') AS created_at_kst
        FROM trade_metrics
    """,
    "positions_kst": """
        CREATE VIEW positions_kst AS
        SELECT
            market,
            qty,
            avg_price,
            realized_pnl,
            unrealized_pnl,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM positions
    """,
    "daily_equity_kst": """
        CREATE VIEW daily_equity_kst AS
        SELECT
            datetime(date_utc || ' 00:00:00', '+9 hours') AS date_kst,
            start_equity,
            start_realized_pnl,
            last_equity,
            realized_pnl,
            unrealized_pnl,
            daily_pnl_abs,
            daily_pnl_pct,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM daily_equity
    """,
    "paper_wallet_kst": """
        CREATE VIEW paper_wallet_kst AS
        SELECT
            id,
            cash_krw,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM paper_wallet
    """,
    "schema_table_docs_kst": """
        CREATE VIEW schema_table_docs_kst AS
        SELECT
            table_name,
            description_en,
            description_ko
        FROM schema_table_docs
    """,
    "schema_column_docs_kst": """
        CREATE VIEW schema_column_docs_kst AS
        SELECT
            table_name,
            column_name,
            description_en,
            description_ko
        FROM schema_column_docs
    """,
}


def run_lightweight_migrations() -> None:
    """Apply lightweight SQLite migrations without alembic."""
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
            if "intent" not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN intent VARCHAR(16)"))

        if "fills" in table_names:
            fill_cols = {col["name"] for col in inspector.get_columns("fills")}
            if "is_applied" not in fill_cols:
                conn.execute(text("ALTER TABLE fills ADD COLUMN is_applied BOOLEAN DEFAULT 0"))

        if "bot_config" in table_names:
            bot_cols = {col["name"] for col in inspector.get_columns("bot_config")}
            columns_to_add = [
                ("target_exposure_pct", "NUMERIC(10,6) DEFAULT 0.10"),
                ("daily_loss_basis", "VARCHAR(32) DEFAULT 'TOTAL'"),
                ("min_rebalance_threshold_pct", "NUMERIC(10,6) DEFAULT 0.05"),
                ("min_order_krw_buffer", "NUMERIC(18,8) DEFAULT 0"),
                ("fill_timeout_sec_entry", "INTEGER DEFAULT 10"),
                ("fill_timeout_sec_exit", "INTEGER DEFAULT 4"),
                ("fill_timeout_sec_rebalance", "INTEGER DEFAULT 10"),
                ("max_reprice_attempts_entry", "INTEGER DEFAULT 2"),
                ("max_reprice_attempts_exit", "INTEGER DEFAULT 1"),
                ("max_reprice_attempts_rebalance", "INTEGER DEFAULT 1"),
                ("reprice_step_bps", "INTEGER DEFAULT 10"),
                ("slippage_budget_entry_pct", "NUMERIC(10,6) DEFAULT 0.0005"),
                ("slippage_budget_exit_pct", "NUMERIC(10,6) DEFAULT 0.0020"),
                ("slippage_budget_breach_halt_count", "INTEGER DEFAULT 0"),
                ("status_notify_interval_seconds", "INTEGER DEFAULT 14400"),
            ]
            for col_name, ddl in columns_to_add:
                if col_name not in bot_cols:
                    conn.execute(text(f"ALTER TABLE bot_config ADD COLUMN {col_name} {ddl}"))

            conn.execute(text("UPDATE bot_config SET target_exposure_pct = 0.10 WHERE target_exposure_pct IS NULL OR target_exposure_pct <= 0"))
            conn.execute(text("UPDATE bot_config SET daily_loss_basis = 'TOTAL' WHERE daily_loss_basis IS NULL OR TRIM(daily_loss_basis) = ''"))
            conn.execute(text("UPDATE bot_config SET min_rebalance_threshold_pct = 0.05 WHERE min_rebalance_threshold_pct IS NULL OR min_rebalance_threshold_pct < 0"))
            conn.execute(text("UPDATE bot_config SET min_order_krw_buffer = 0 WHERE min_order_krw_buffer IS NULL OR min_order_krw_buffer < 0"))
            conn.execute(text("UPDATE bot_config SET fill_timeout_sec_entry = 10 WHERE fill_timeout_sec_entry IS NULL OR fill_timeout_sec_entry <= 0"))
            conn.execute(text("UPDATE bot_config SET fill_timeout_sec_exit = 4 WHERE fill_timeout_sec_exit IS NULL OR fill_timeout_sec_exit <= 0"))
            conn.execute(text("UPDATE bot_config SET fill_timeout_sec_rebalance = 10 WHERE fill_timeout_sec_rebalance IS NULL OR fill_timeout_sec_rebalance <= 0"))
            conn.execute(text("UPDATE bot_config SET max_reprice_attempts_entry = 2 WHERE max_reprice_attempts_entry IS NULL OR max_reprice_attempts_entry <= 0"))
            conn.execute(text("UPDATE bot_config SET max_reprice_attempts_exit = 1 WHERE max_reprice_attempts_exit IS NULL OR max_reprice_attempts_exit <= 0"))
            conn.execute(text("UPDATE bot_config SET max_reprice_attempts_rebalance = 1 WHERE max_reprice_attempts_rebalance IS NULL OR max_reprice_attempts_rebalance <= 0"))
            conn.execute(text("UPDATE bot_config SET reprice_step_bps = 10 WHERE reprice_step_bps IS NULL OR reprice_step_bps <= 0"))
            conn.execute(text("UPDATE bot_config SET slippage_budget_entry_pct = 0.0005 WHERE slippage_budget_entry_pct IS NULL OR slippage_budget_entry_pct < 0"))
            conn.execute(text("UPDATE bot_config SET slippage_budget_exit_pct = 0.0020 WHERE slippage_budget_exit_pct IS NULL OR slippage_budget_exit_pct < 0"))
            conn.execute(text("UPDATE bot_config SET slippage_budget_breach_halt_count = 0 WHERE slippage_budget_breach_halt_count IS NULL OR slippage_budget_breach_halt_count < 0"))
            conn.execute(text("UPDATE bot_config SET status_notify_interval_seconds = 14400 WHERE status_notify_interval_seconds IS NULL OR status_notify_interval_seconds < 300"))

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
                        start_realized_pnl NUMERIC(28,8) NOT NULL DEFAULT 0,
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
        else:
            daily_cols = {col["name"] for col in inspector.get_columns("daily_equity")}
            if "start_realized_pnl" not in daily_cols:
                conn.execute(text("ALTER TABLE daily_equity ADD COLUMN start_realized_pnl NUMERIC(28,8) DEFAULT 0"))
                conn.execute(text("UPDATE daily_equity SET start_realized_pnl = COALESCE(realized_pnl, 0) WHERE start_realized_pnl IS NULL"))

        if "trade_metrics" not in table_names:
            conn.execute(
                text(
                    """
                    CREATE TABLE trade_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id INTEGER NOT NULL,
                        intent VARCHAR(16),
                        intended_price NUMERIC(24,8),
                        filled_vwap_price NUMERIC(24,8),
                        slippage_abs NUMERIC(24,8),
                        slippage_pct NUMERIC(24,8),
                        fee_abs NUMERIC(24,8) NOT NULL DEFAULT 0,
                        time_to_fill_ms INTEGER,
                        partial_fill_count INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME,
                        FOREIGN KEY(order_id) REFERENCES orders(id),
                        UNIQUE(order_id)
                    )
                    """
                )
            )

        conn.execute(text("DROP INDEX IF EXISTS ix_trade_metrics_order_id"))

        existing = conn.execute(text("SELECT timeframe FROM timeframe_config")).fetchall()
        existing_timeframes = {row[0] for row in existing}
        for timeframe in SUPPORTED_TIMEFRAMES:
            if timeframe not in existing_timeframes:
                conn.execute(
                    text("INSERT INTO timeframe_config (timeframe, is_enabled, updated_at) VALUES (:timeframe, 0, CURRENT_TIMESTAMP)"),
                    {"timeframe": timeframe},
                )
        conn.execute(text("UPDATE timeframe_config SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))

        enabled_count = conn.execute(text("SELECT COUNT(*) FROM timeframe_config WHERE is_enabled = 1")).scalar_one()
        if enabled_count == 0:
            current = conn.execute(text("SELECT timeframe FROM bot_config WHERE id = 1")).scalar_one_or_none()
            selected = current if current in SUPPORTED_TIMEFRAMES else "15m"
            conn.execute(text("UPDATE timeframe_config SET is_enabled = CASE WHEN timeframe = :timeframe THEN 1 ELSE 0 END"), {"timeframe": selected})

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
        conn.execute(text("CREATE TABLE schema_table_docs_new (table_name TEXT PRIMARY KEY, description_en TEXT NOT NULL DEFAULT '', description_ko TEXT NOT NULL DEFAULT '')"))
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
            {"table_name": table_name, "description_en": description_en, "description_ko": description_ko},
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
