from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from trader.config.settings import settings
from trader.utils.timeframes import SUPPORTED_TIMEFRAMES


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session_factory():
    """Return the configured SQLAlchemy session factory."""
    return SessionLocal


def create_session():
    """Create a new DB session."""
    return SessionLocal()


def _is_sqlite_bind(bind) -> bool:
    return bind.dialect.name == "sqlite"

TABLE_DOCS_EN = {
    "users": "Authenticated user identities for V2 API access.",
    "audit_log": "User and admin action audit trail.",
    "user_risk_guard": "Per-user risk guard flags (manual halt / emergency kill switch).",
    "user_exchange_credentials": "Per-user exchange API credentials encrypted at rest.",
    "user_api_budget": "Per-user fixed-window API request budget counters.",
    "bot_config": "Runtime control and risk configuration (single active row).",
    "timeframe_config": "Executable timeframe rows with enable flags.",
    "candles": "OHLCV candle history by market and timeframe.",
    "orders": "Order intents and exchange status tracking.",
    "order_attempts": "Per-attempt exchange submission and recovery history for each logical order.",
    "fills": "Trade fills linked to orders (idempotent by trade_id).",
    "trade_metrics": "Per-order execution quality metrics (VWAP, slippage, fill time).",
    "positions": "Current position state per market.",
    "daily_equity": "Daily equity baseline and PnL snapshots (UTC date keyed).",
    "paper_wallet": "Paper-trading cash wallet.",
}

COLUMN_DOCS_EN = {
    "users": {
        "id": "Primary key.",
        "email": "Unique canonical login email (lowercase).",
        "password_hash": "PBKDF2 password hash string.",
        "display_name": "Optional profile display name.",
        "is_active": "Whether login is allowed for this user.",
        "token_version": "Monotonic token version for server-side session invalidation.",
        "created_at": "Creation timestamp.",
        "updated_at": "Last update timestamp.",
    },
    "audit_log": {
        "id": "Primary key.",
        "actor_user_id": "Actor user id (nullable for system events).",
        "action": "Normalized audit action code.",
        "target_type": "Target entity type (credential/runtime/admin/etc).",
        "target_id": "Target entity identifier as string.",
        "metadata_json": "JSON-serialized audit metadata payload.",
        "created_at": "Audit event creation timestamp.",
    },
    "user_risk_guard": {
        "id": "Primary key.",
        "user_id": "User owner id.",
        "manual_halt": "Manual halt flag for this user runtime.",
        "emergency_kill_switch": "Emergency stop flag for this user runtime.",
        "reason": "Operator-entered halt reason text.",
        "updated_by_user_id": "Last operator user id who changed the guard.",
        "created_at": "Creation timestamp.",
        "updated_at": "Last update timestamp.",
    },
    "user_exchange_credentials": {
        "id": "Primary key.",
        "user_id": "Foreign key to users.id.",
        "exchange": "Exchange key (currently UPBIT).",
        "access_key_encrypted": "Encrypted exchange access key value.",
        "secret_key_encrypted": "Encrypted exchange secret key value.",
        "key_version": "Credential key version used for decryption/rotation.",
        "access_key_masked": "Masked access key preview for UI status.",
        "access_key_fingerprint": "SHA-256 fingerprint of the raw access key.",
        "created_at": "Creation timestamp.",
        "updated_at": "Last update timestamp.",
    },
    "user_api_budget": {
        "id": "Primary key.",
        "user_id": "Foreign key to users.id.",
        "scope": "Budget scope (ME or ADMIN).",
        "window_started_at": "UTC start timestamp of the active budget window.",
        "window_seconds": "Window size in seconds.",
        "request_count": "Accepted request count within the active window.",
        "blocked_count": "Blocked request count within the active window.",
        "created_at": "Creation timestamp.",
        "updated_at": "Last update timestamp.",
    },
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
        "max_weekly_loss_pct": "Weekly loss halt threshold ratio.",
        "max_monthly_loss_pct": "Monthly loss halt threshold ratio.",
        "cooldown_hours_on_halt": "Cooldown duration in hours after policy halt.",
        "max_new_orders_per_day": "Maximum number of new orders allowed per UTC day.",
        "max_orders_per_week": "Maximum number of orders allowed per UTC week.",
        "min_edge_pct": "Minimum edge ratio required for BUY-side exposure increase.",
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
        "user_id": "Ownership key for user-scoped order records.",
        "market": "Market code.",
        "side": "bid/ask.",
        "ord_type": "Order type (usually limit).",
        "requested_price": "Requested limit price.",
        "requested_volume": "Requested order volume.",
        "client_order_id": "Local idempotency key scoped by user_id.",
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
    "order_attempts": {
        "id": "Primary key.",
        "order_id": "Foreign key to orders.id.",
        "attempt_no": "Monotonic attempt sequence within an order.",
        "submit_reason": "Attempt reason (INITIAL/REPRICE/RECOVER).",
        "requested_price": "Attempt-level requested limit price.",
        "requested_volume": "Attempt-level requested order volume.",
        "upbit_identifier": "Exchange identifier reserved for this attempt.",
        "upbit_uuid": "Exchange order UUID for this attempt.",
        "state": "Attempt-level local state.",
        "retry_count": "Retry count for this attempt.",
        "error_class": "Normalized attempt error class.",
        "last_error": "Latest attempt error message.",
        "exchange_response_raw": "Raw exchange payload snapshot for this attempt.",
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
        "user_id": "Ownership key; composite primary key with market.",
        "market": "Market code (composite primary key with user_id).",
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
        "user_id": "Primary key and ownership key (1 row per user).",
        "cash_krw": "Paper wallet KRW cash balance.",
        "updated_at": "Last update timestamp.",
    },
}

TABLE_DOCS_KO = {
    "users": "V2 API 인증 접근을 위한 사용자 식별 정보.",
    "audit_log": "사용자/관리자 액션 감사 추적 이력.",
    "user_risk_guard": "사용자별 리스크 가드 플래그(수동 중지/긴급 중지).",
    "user_exchange_credentials": "사용자별 거래소 API 자격증명(저장 시 암호화).",
    "user_api_budget": "사용자별 고정 윈도우 API 요청 예산 카운터.",
    "bot_config": "런타임 제어 및 리스크 설정(단일 활성 행).",
    "timeframe_config": "실행 대상 타임프레임과 활성화 상태.",
    "candles": "마켓/타임프레임별 OHLCV 캔들 이력.",
    "orders": "주문 의도와 거래소 상태 추적.",
    "order_attempts": "논리 주문별 개별 제출/복구 시도 이력.",
    "fills": "주문과 연결된 체결 내역(trade_id 기준 멱등).",
    "trade_metrics": "주문별 집행 품질 지표(VWAP, 슬리피지, 체결 시간).",
    "positions": "마켓별 현재 포지션 상태.",
    "daily_equity": "일별 자산 기준선 및 손익 스냅샷(UTC 날짜 키).",
    "paper_wallet": "페이퍼 트레이딩 현금 지갑.",
}

COLUMN_DOCS_KO = {
    "users": {
        "id": "기본 키.",
        "email": "고유한 정규화 로그인 이메일(소문자).",
        "password_hash": "PBKDF2 비밀번호 해시 문자열.",
        "display_name": "선택 사용자 표시 이름.",
        "is_active": "해당 사용자의 로그인 허용 여부.",
        "token_version": "서버 측 세션 무효화에 사용하는 단조 증가 토큰 버전.",
        "created_at": "생성 시각.",
        "updated_at": "마지막 수정 시각.",
    },
    "audit_log": {
        "id": "기본 키.",
        "actor_user_id": "행위 사용자 ID(시스템 이벤트는 NULL 허용).",
        "action": "정규화된 감사 액션 코드.",
        "target_type": "대상 엔터티 유형(credential/runtime/admin 등).",
        "target_id": "대상 엔터티 식별자(문자열).",
        "metadata_json": "JSON 직렬화된 감사 메타데이터 페이로드.",
        "created_at": "감사 이벤트 생성 시각.",
    },
    "user_risk_guard": {
        "id": "기본 키.",
        "user_id": "소유 사용자 ID.",
        "manual_halt": "해당 사용자 런타임 수동 중지 플래그.",
        "emergency_kill_switch": "해당 사용자 런타임 긴급 중지 플래그.",
        "reason": "운영자 입력 중지 사유 텍스트.",
        "updated_by_user_id": "마지막 변경 수행 사용자 ID.",
        "created_at": "생성 시각.",
        "updated_at": "마지막 수정 시각.",
    },
    "user_exchange_credentials": {
        "id": "기본 키.",
        "user_id": "users.id 외래 키.",
        "exchange": "거래소 식별 키(현재 UPBIT).",
        "access_key_encrypted": "암호화된 거래소 access key 값.",
        "secret_key_encrypted": "암호화된 거래소 secret key 값.",
        "key_version": "복호화/로테이션에 사용하는 자격증명 키 버전.",
        "access_key_masked": "UI 상태 표시용 마스킹 access key.",
        "access_key_fingerprint": "원본 access key의 SHA-256 fingerprint.",
        "created_at": "생성 시각.",
        "updated_at": "마지막 수정 시각.",
    },
    "user_api_budget": {
        "id": "기본 키.",
        "user_id": "users.id 외래 키.",
        "scope": "예산 스코프(ME 또는 ADMIN).",
        "window_started_at": "현재 예산 윈도우의 UTC 시작 시각.",
        "window_seconds": "윈도우 길이(초).",
        "request_count": "현재 윈도우 내 허용된 요청 수.",
        "blocked_count": "현재 윈도우 내 차단된 요청 수.",
        "created_at": "생성 시각.",
        "updated_at": "마지막 수정 시각.",
    },
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
        "max_weekly_loss_pct": "주간 손실 중지 임계 비율.",
        "max_monthly_loss_pct": "월간 손실 중지 임계 비율.",
        "cooldown_hours_on_halt": "정책 중지 후 재진입 제한 쿨다운 시간(시).",
        "max_new_orders_per_day": "UTC 일자 기준 신규 주문 허용 최대 건수.",
        "max_orders_per_week": "UTC 주차 기준 주문 허용 최대 건수.",
        "min_edge_pct": "BUY 노출 확대 전 요구되는 최소 엣지 비율.",
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
        "user_id": "사용자 스코프 주문 소유 키.",
        "market": "마켓 코드.",
        "side": "매수/매도(bid/ask).",
        "ord_type": "주문 유형(일반적으로 limit).",
        "requested_price": "요청한 지정가 가격.",
        "requested_volume": "요청한 주문 수량.",
        "client_order_id": "user_id 스코프 기준 로컬 멱등 키.",
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
    "order_attempts": {
        "id": "기본 키.",
        "order_id": "orders.id 외래 키.",
        "attempt_no": "주문 내 단조 증가 시도 순번.",
        "submit_reason": "시도 사유(INITIAL/REPRICE/RECOVER).",
        "requested_price": "시도 단위 요청 지정가 가격.",
        "requested_volume": "시도 단위 요청 주문 수량.",
        "upbit_identifier": "이 시도에 예약된 거래소 식별자.",
        "upbit_uuid": "이 시도에 대응하는 거래소 주문 UUID.",
        "state": "시도 단위 로컬 상태.",
        "retry_count": "이 시도의 재시도 횟수.",
        "error_class": "정규화된 시도 오류 클래스.",
        "last_error": "최신 시도 오류 메시지.",
        "exchange_response_raw": "이 시도의 거래소 원본 응답 스냅샷.",
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
        "user_id": "소유 사용자 키(시장 코드와 함께 복합 기본 키).",
        "market": "마켓 코드(user_id와 함께 복합 기본 키).",
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
        "user_id": "기본 키이자 소유 키(사용자별 1행).",
        "cash_krw": "페이퍼 지갑 KRW 현금 잔액.",
        "updated_at": "마지막 수정 시각.",
    },
}

SQLITE_KST_VIEW_SQL = {
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
            max_weekly_loss_pct,
            max_monthly_loss_pct,
            cooldown_hours_on_halt,
            max_new_orders_per_day,
            max_orders_per_week,
            min_edge_pct,
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
            user_id,
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
    "audit_log_kst": """
        CREATE VIEW audit_log_kst AS
        SELECT
            id,
            actor_user_id,
            action,
            target_type,
            target_id,
            metadata_json,
            datetime(created_at, '+9 hours') AS created_at_kst
        FROM audit_log
    """,
    "user_risk_guard_kst": """
        CREATE VIEW user_risk_guard_kst AS
        SELECT
            id,
            user_id,
            manual_halt,
            emergency_kill_switch,
            reason,
            updated_by_user_id,
            datetime(created_at, '+9 hours') AS created_at_kst,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM user_risk_guard
    """,
    "user_api_budget_kst": """
        CREATE VIEW user_api_budget_kst AS
        SELECT
            id,
            user_id,
            scope,
            datetime(window_started_at, '+9 hours') AS window_started_at_kst,
            window_seconds,
            request_count,
            blocked_count,
            datetime(created_at, '+9 hours') AS created_at_kst,
            datetime(updated_at, '+9 hours') AS updated_at_kst
        FROM user_api_budget
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
            user_id,
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
            user_id,
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
            user_id,
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

POSTGRES_KST_VIEW_SQL = {
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
            max_weekly_loss_pct,
            max_monthly_loss_pct,
            cooldown_hours_on_halt,
            max_new_orders_per_day,
            max_orders_per_week,
            min_edge_pct,
            max_total_exposure_pct,
            max_per_market_exposure_pct,
            updated_at AT TIME ZONE 'Asia/Seoul' AS updated_at_kst
        FROM bot_config
    """,
    "timeframe_config_kst": """
        CREATE VIEW timeframe_config_kst AS
        SELECT
            id,
            timeframe,
            is_enabled,
            updated_at AT TIME ZONE 'Asia/Seoul' AS updated_at_kst
        FROM timeframe_config
    """,
    "candles_kst": """
        CREATE VIEW candles_kst AS
        SELECT
            id,
            market,
            timeframe,
            candle_time_utc AT TIME ZONE 'Asia/Seoul' AS candle_time_kst,
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
            user_id,
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
            created_at AT TIME ZONE 'Asia/Seoul' AS created_at_kst,
            updated_at AT TIME ZONE 'Asia/Seoul' AS updated_at_kst
        FROM orders
    """,
    "audit_log_kst": """
        CREATE VIEW audit_log_kst AS
        SELECT
            id,
            actor_user_id,
            action,
            target_type,
            target_id,
            metadata_json,
            created_at AT TIME ZONE 'Asia/Seoul' AS created_at_kst
        FROM audit_log
    """,
    "user_risk_guard_kst": """
        CREATE VIEW user_risk_guard_kst AS
        SELECT
            id,
            user_id,
            manual_halt,
            emergency_kill_switch,
            reason,
            updated_by_user_id,
            created_at AT TIME ZONE 'Asia/Seoul' AS created_at_kst,
            updated_at AT TIME ZONE 'Asia/Seoul' AS updated_at_kst
        FROM user_risk_guard
    """,
    "user_api_budget_kst": """
        CREATE VIEW user_api_budget_kst AS
        SELECT
            id,
            user_id,
            scope,
            window_started_at AT TIME ZONE 'Asia/Seoul' AS window_started_at_kst,
            window_seconds,
            request_count,
            blocked_count,
            created_at AT TIME ZONE 'Asia/Seoul' AS created_at_kst,
            updated_at AT TIME ZONE 'Asia/Seoul' AS updated_at_kst
        FROM user_api_budget
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
            executed_at AT TIME ZONE 'Asia/Seoul' AS executed_at_kst
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
            created_at AT TIME ZONE 'Asia/Seoul' AS created_at_kst
        FROM trade_metrics
    """,
    "positions_kst": """
        CREATE VIEW positions_kst AS
        SELECT
            user_id,
            market,
            qty,
            avg_price,
            realized_pnl,
            unrealized_pnl,
            updated_at AT TIME ZONE 'Asia/Seoul' AS updated_at_kst
        FROM positions
    """,
    "daily_equity_kst": """
        CREATE VIEW daily_equity_kst AS
        SELECT
            user_id,
            (date_utc::timestamp + INTERVAL '9 hours') AS date_kst,
            start_equity,
            start_realized_pnl,
            last_equity,
            realized_pnl,
            unrealized_pnl,
            daily_pnl_abs,
            daily_pnl_pct,
            updated_at AT TIME ZONE 'Asia/Seoul' AS updated_at_kst
        FROM daily_equity
    """,
    "paper_wallet_kst": """
        CREATE VIEW paper_wallet_kst AS
        SELECT
            user_id,
            cash_krw,
            updated_at AT TIME ZONE 'Asia/Seoul' AS updated_at_kst
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


def _get_kst_view_sql(bind) -> dict[str, str]:
    if bind.dialect.name == "postgresql":
        return POSTGRES_KST_VIEW_SQL
    return SQLITE_KST_VIEW_SQL


def _resolve_legacy_owner_user_id(conn) -> int:
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    owner_user_id = None
    if "user_exchange_credentials" in table_names:
        owner_user_id = conn.execute(text("SELECT MIN(user_id) FROM user_exchange_credentials")).scalar_one_or_none()
    if owner_user_id is None and "users" in table_names:
        owner_user_id = conn.execute(text("SELECT MIN(id) FROM users")).scalar_one_or_none()
    return int(owner_user_id or 1)


def _ensure_user_scope_column(conn, *, table_name: str, owner_user_id: int) -> None:
    cols = {col["name"] for col in inspect(conn).get_columns(table_name)}
    if "user_id" not in cols:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN user_id INTEGER DEFAULT 1"))
    conn.execute(text(f"UPDATE {table_name} SET user_id = COALESCE(user_id, :owner_user_id)"), {"owner_user_id": owner_user_id})


def _pk_columns(conn, table_name: str) -> list[str]:
    return list((inspect(conn).get_pk_constraint(table_name) or {}).get("constrained_columns") or [])


def _pk_matches(conn, table_name: str, expected: tuple[str, ...]) -> bool:
    actual = _pk_columns(conn, table_name)
    return len(actual) == len(expected) and set(actual) == set(expected)


def _quote_ident(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def _postgres_ensure_daily_equity_user_scope(conn, *, owner_user_id: int) -> None:
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "daily_equity" not in table_names:
        return

    daily_cols = {col["name"] for col in inspector.get_columns("daily_equity")}
    if "user_id" not in daily_cols:
        conn.execute(text("ALTER TABLE daily_equity ADD COLUMN user_id INTEGER"))
    conn.execute(
        text("UPDATE daily_equity SET user_id = COALESCE(user_id, :owner_user_id) WHERE user_id IS NULL"),
        {"owner_user_id": owner_user_id},
    )
    conn.execute(text("ALTER TABLE daily_equity ALTER COLUMN user_id SET DEFAULT 1"))
    conn.execute(text("ALTER TABLE daily_equity ALTER COLUMN user_id SET NOT NULL"))

    if "start_realized_pnl" not in daily_cols:
        conn.execute(text("ALTER TABLE daily_equity ADD COLUMN start_realized_pnl NUMERIC(28,8)"))
    conn.execute(
        text(
            "UPDATE daily_equity "
            "SET start_realized_pnl = COALESCE(start_realized_pnl, realized_pnl, 0) "
            "WHERE start_realized_pnl IS NULL"
        )
    )
    conn.execute(text("ALTER TABLE daily_equity ALTER COLUMN start_realized_pnl SET DEFAULT 0"))
    conn.execute(text("ALTER TABLE daily_equity ALTER COLUMN start_realized_pnl SET NOT NULL"))

    if not _pk_matches(conn, "daily_equity", ("user_id", "date_utc")):
        duplicate_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT user_id, date_utc
                    FROM daily_equity
                    GROUP BY user_id, date_utc
                    HAVING COUNT(*) > 1
                ) dup
                """
            )
        ).scalar_one()
        if int(duplicate_count or 0) > 0:
            raise RuntimeError(
                "daily_equity contains duplicate (user_id, date_utc) rows; cannot rebuild primary key safely"
            )
        pk_name = (inspect(conn).get_pk_constraint("daily_equity") or {}).get("name")
        if pk_name:
            conn.execute(text(f"ALTER TABLE daily_equity DROP CONSTRAINT {_quote_ident(pk_name)}"))
        conn.execute(text("ALTER TABLE daily_equity ADD PRIMARY KEY (user_id, date_utc)"))

    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_daily_equity_user_id ON daily_equity(user_id)"))


def _postgres_ensure_positions_user_scope(conn, *, owner_user_id: int) -> None:
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "positions" not in table_names:
        return

    position_cols = {col["name"] for col in inspector.get_columns("positions")}
    if "user_id" not in position_cols:
        conn.execute(text("ALTER TABLE positions ADD COLUMN user_id INTEGER"))
    conn.execute(
        text("UPDATE positions SET user_id = COALESCE(user_id, :owner_user_id) WHERE user_id IS NULL"),
        {"owner_user_id": owner_user_id},
    )
    conn.execute(text("ALTER TABLE positions ALTER COLUMN user_id SET DEFAULT 1"))
    conn.execute(text("ALTER TABLE positions ALTER COLUMN user_id SET NOT NULL"))

    if not _pk_matches(conn, "positions", ("user_id", "market")):
        duplicate_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT user_id, market
                    FROM positions
                    GROUP BY user_id, market
                    HAVING COUNT(*) > 1
                ) dup
                """
            )
        ).scalar_one()
        if int(duplicate_count or 0) > 0:
            raise RuntimeError(
                "positions contains duplicate (user_id, market) rows; cannot rebuild primary key safely"
            )
        pk_name = (inspect(conn).get_pk_constraint("positions") or {}).get("name")
        if pk_name:
            conn.execute(text(f"ALTER TABLE positions DROP CONSTRAINT {_quote_ident(pk_name)}"))
        conn.execute(text("ALTER TABLE positions ADD PRIMARY KEY (user_id, market)"))

    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_positions_user_id ON positions(user_id)"))


def _sqlite_rebuild_positions_user_scope(conn, *, owner_user_id: int) -> None:
    cols = {col["name"] for col in inspect(conn).get_columns("positions")}
    user_expr = "COALESCE(user_id, :owner_user_id)" if "user_id" in cols else ":owner_user_id"
    conn.execute(text("ALTER TABLE positions RENAME TO positions_v3_old"))
    conn.execute(
        text(
            """
            CREATE TABLE positions (
                user_id INTEGER NOT NULL,
                market VARCHAR(32) NOT NULL,
                qty NUMERIC(24,8) NOT NULL DEFAULT 0,
                avg_price NUMERIC(24,8) NOT NULL DEFAULT 0,
                realized_pnl NUMERIC(24,8) NOT NULL DEFAULT 0,
                unrealized_pnl NUMERIC(24,8) NOT NULL DEFAULT 0,
                updated_at DATETIME,
                PRIMARY KEY (user_id, market),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
    )
    conn.execute(
        text(
            f"""
            INSERT INTO positions (
                user_id,
                market,
                qty,
                avg_price,
                realized_pnl,
                unrealized_pnl,
                updated_at
            )
            SELECT
                {user_expr},
                market,
                COALESCE(qty, 0),
                COALESCE(avg_price, 0),
                COALESCE(realized_pnl, 0),
                COALESCE(unrealized_pnl, 0),
                updated_at
            FROM positions_v3_old
            """
        ),
        {"owner_user_id": owner_user_id},
    )
    conn.execute(text("DROP TABLE positions_v3_old"))


def _sqlite_rebuild_daily_equity_user_scope(conn, *, owner_user_id: int) -> None:
    cols = {col["name"] for col in inspect(conn).get_columns("daily_equity")}
    user_expr = "COALESCE(user_id, :owner_user_id)" if "user_id" in cols else ":owner_user_id"
    conn.execute(text("ALTER TABLE daily_equity RENAME TO daily_equity_v3_old"))
    conn.execute(
        text(
            """
            CREATE TABLE daily_equity (
                user_id INTEGER NOT NULL,
                date_utc DATE NOT NULL,
                start_equity NUMERIC(28,8) NOT NULL DEFAULT 0,
                start_realized_pnl NUMERIC(28,8) NOT NULL DEFAULT 0,
                last_equity NUMERIC(28,8) NOT NULL DEFAULT 0,
                realized_pnl NUMERIC(28,8) NOT NULL DEFAULT 0,
                unrealized_pnl NUMERIC(28,8) NOT NULL DEFAULT 0,
                daily_pnl_abs NUMERIC(28,8) NOT NULL DEFAULT 0,
                daily_pnl_pct NUMERIC(28,8) NOT NULL DEFAULT 0,
                updated_at DATETIME,
                PRIMARY KEY (user_id, date_utc),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
    )
    conn.execute(
        text(
            f"""
            INSERT INTO daily_equity (
                user_id,
                date_utc,
                start_equity,
                start_realized_pnl,
                last_equity,
                realized_pnl,
                unrealized_pnl,
                daily_pnl_abs,
                daily_pnl_pct,
                updated_at
            )
            SELECT
                {user_expr},
                date_utc,
                COALESCE(start_equity, 0),
                COALESCE(start_realized_pnl, COALESCE(realized_pnl, 0)),
                COALESCE(last_equity, 0),
                COALESCE(realized_pnl, 0),
                COALESCE(unrealized_pnl, 0),
                COALESCE(daily_pnl_abs, 0),
                COALESCE(daily_pnl_pct, 0),
                updated_at
            FROM daily_equity_v3_old
            """
        ),
        {"owner_user_id": owner_user_id},
    )
    conn.execute(text("DROP TABLE daily_equity_v3_old"))


def _sqlite_rebuild_paper_wallet_user_scope(conn, *, owner_user_id: int) -> None:
    cols = {col["name"] for col in inspect(conn).get_columns("paper_wallet")}
    user_expr = "COALESCE(user_id, :owner_user_id)" if "user_id" in cols else ":owner_user_id"
    conn.execute(text("ALTER TABLE paper_wallet RENAME TO paper_wallet_v3_old"))
    conn.execute(
        text(
            """
            CREATE TABLE paper_wallet (
                user_id INTEGER NOT NULL PRIMARY KEY,
                cash_krw NUMERIC(24,8) NOT NULL DEFAULT 1000000,
                updated_at DATETIME,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
    )
    conn.execute(
        text(
            f"""
            INSERT OR REPLACE INTO paper_wallet (
                user_id,
                cash_krw,
                updated_at
            )
            SELECT
                {user_expr},
                COALESCE(cash_krw, 1000000),
                updated_at
            FROM paper_wallet_v3_old
            """
        ),
        {"owner_user_id": owner_user_id},
    )
    conn.execute(text("DROP TABLE paper_wallet_v3_old"))


def _seed_user_bot_scope(conn, *, owner_user_id: int) -> None:
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "user_bot_config" not in table_names:
        return

    if "bot_config" in table_names:
        conn.execute(
            text(
                """
                INSERT INTO user_bot_config (
                    user_id,
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
                    max_weekly_loss_pct,
                    max_monthly_loss_pct,
                    cooldown_hours_on_halt,
                    max_new_orders_per_day,
                    max_orders_per_week,
                    min_edge_pct,
                    max_total_exposure_pct,
                    max_per_market_exposure_pct,
                    created_at,
                    updated_at
                )
                SELECT
                    :owner_user_id,
                    b.is_enabled,
                    b.timeframe,
                    b.markets_json,
                    b.target_exposure_pct,
                    b.daily_loss_basis,
                    b.min_rebalance_threshold_pct,
                    b.min_order_krw_buffer,
                    b.fill_timeout_sec_entry,
                    b.fill_timeout_sec_exit,
                    b.fill_timeout_sec_rebalance,
                    b.max_reprice_attempts_entry,
                    b.max_reprice_attempts_exit,
                    b.max_reprice_attempts_rebalance,
                    b.reprice_step_bps,
                    b.slippage_budget_entry_pct,
                    b.slippage_budget_exit_pct,
                    b.slippage_budget_breach_halt_count,
                    b.status_notify_interval_seconds,
                    b.max_daily_loss_pct,
                    b.max_weekly_loss_pct,
                    b.max_monthly_loss_pct,
                    b.cooldown_hours_on_halt,
                    b.max_new_orders_per_day,
                    b.max_orders_per_week,
                    b.min_edge_pct,
                    b.max_total_exposure_pct,
                    b.max_per_market_exposure_pct,
                    COALESCE(b.updated_at, CURRENT_TIMESTAMP),
                    COALESCE(b.updated_at, CURRENT_TIMESTAMP)
                FROM bot_config b
                WHERE b.id = 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM user_bot_config ubc
                      WHERE ubc.user_id = :owner_user_id
                  )
                """
            ),
            {"owner_user_id": owner_user_id},
        )

    if "user_bot_runtime" in table_names:
        conn.execute(
            text(
                """
                INSERT INTO user_bot_runtime (
                    user_id,
                    is_enabled,
                    status,
                    consecutive_failures,
                    halt_reason,
                    cooldown_until,
                    halted_at,
                    created_at,
                    updated_at
                )
                SELECT
                    :owner_user_id,
                    COALESCE(
                        (SELECT ubc.is_enabled FROM user_bot_config ubc WHERE ubc.user_id = :owner_user_id),
                        :default_is_enabled
                    ),
                    'IDLE',
                    0,
                    NULL,
                    NULL,
                    NULL,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM user_bot_runtime ubr
                    WHERE ubr.user_id = :owner_user_id
                )
                """
            ),
            {"owner_user_id": owner_user_id, "default_is_enabled": True},
        )


def _ensure_users_token_version(conn) -> None:
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    user_cols = {col["name"] for col in inspector.get_columns("users")}
    if "token_version" not in user_cols:
        conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 1"))

    if conn.dialect.name == "postgresql":
        conn.execute(text("UPDATE users SET token_version = 1 WHERE token_version IS NULL OR token_version <= 0"))
        conn.execute(text("ALTER TABLE users ALTER COLUMN token_version SET DEFAULT 1"))
        conn.execute(text("ALTER TABLE users ALTER COLUMN token_version SET NOT NULL"))
    else:
        conn.execute(text("UPDATE users SET token_version = CASE WHEN token_version IS NULL OR token_version <= 0 THEN 1 ELSE token_version END"))

    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_token_version ON users(token_version)"))


def _ensure_s7_policy_columns(conn) -> None:
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    policy_columns = [
        ("max_weekly_loss_pct", "NUMERIC(10,6) DEFAULT 0"),
        ("max_monthly_loss_pct", "NUMERIC(10,6) DEFAULT 0"),
        ("cooldown_hours_on_halt", "INTEGER DEFAULT 0"),
        ("max_new_orders_per_day", "INTEGER DEFAULT 0"),
        ("max_orders_per_week", "INTEGER DEFAULT 0"),
        ("min_edge_pct", "NUMERIC(10,6) DEFAULT 0"),
    ]

    for table_name in ("bot_config", "user_bot_config"):
        if table_name not in table_names:
            continue
        existing = {col["name"] for col in inspector.get_columns(table_name)}
        for col_name, ddl in policy_columns:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {ddl}"))
        conn.execute(
            text(
                f"""
                UPDATE {table_name}
                SET max_weekly_loss_pct = 0
                WHERE max_weekly_loss_pct IS NULL OR max_weekly_loss_pct < 0
                """
            )
        )
        conn.execute(
            text(
                f"""
                UPDATE {table_name}
                SET max_monthly_loss_pct = 0
                WHERE max_monthly_loss_pct IS NULL OR max_monthly_loss_pct < 0
                """
            )
        )
        conn.execute(
            text(
                f"""
                UPDATE {table_name}
                SET cooldown_hours_on_halt = 0
                WHERE cooldown_hours_on_halt IS NULL OR cooldown_hours_on_halt < 0
                """
            )
        )
        conn.execute(
            text(
                f"""
                UPDATE {table_name}
                SET max_new_orders_per_day = 0
                WHERE max_new_orders_per_day IS NULL OR max_new_orders_per_day < 0
                """
            )
        )
        conn.execute(
            text(
                f"""
                UPDATE {table_name}
                SET max_orders_per_week = 0
                WHERE max_orders_per_week IS NULL OR max_orders_per_week < 0
                """
            )
        )
        conn.execute(
            text(
                f"""
                UPDATE {table_name}
                SET min_edge_pct = 0
                WHERE min_edge_pct IS NULL OR min_edge_pct < 0
                """
            )
        )

    if "user_bot_runtime" not in table_names:
        return

    existing_runtime = {col["name"] for col in inspector.get_columns("user_bot_runtime")}
    dt_type = "TIMESTAMP WITH TIME ZONE" if conn.dialect.name == "postgresql" else "DATETIME"
    runtime_columns = [
        ("halt_reason", "VARCHAR(64)"),
        ("cooldown_until", dt_type),
        ("halted_at", dt_type),
    ]
    for col_name, ddl in runtime_columns:
        if col_name not in existing_runtime:
            conn.execute(text(f"ALTER TABLE user_bot_runtime ADD COLUMN {col_name} {ddl}"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_bot_runtime_halt_reason ON user_bot_runtime(halt_reason)"))


def run_lightweight_migrations() -> None:
    """Apply lightweight bootstrap migrations without alembic."""
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            _ensure_users_token_version(conn)
            owner_user_id = _resolve_legacy_owner_user_id(conn)
            _postgres_ensure_positions_user_scope(conn, owner_user_id=owner_user_id)
            _postgres_ensure_daily_equity_user_scope(conn, owner_user_id=owner_user_id)
            _ensure_s7_policy_columns(conn)
            _seed_user_bot_scope(conn, owner_user_id=owner_user_id)
            return

        if not _is_sqlite_bind(conn):
            return

        inspector = inspect(conn)
        table_names = set(inspector.get_table_names())
        owner_user_id = _resolve_legacy_owner_user_id(conn)
        _ensure_users_token_version(conn)

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
            if "user_id" not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN user_id INTEGER DEFAULT 1"))
            conn.execute(text("UPDATE orders SET user_id = COALESCE(user_id, :owner_user_id)"), {"owner_user_id": owner_user_id})
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_user_id ON orders(user_id)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_user_client_order_id ON orders(user_id, client_order_id)"))

        if "fills" in table_names:
            fill_cols = {col["name"] for col in inspector.get_columns("fills")}
            if "is_applied" not in fill_cols:
                conn.execute(text("ALTER TABLE fills ADD COLUMN is_applied BOOLEAN DEFAULT 0"))

        if "audit_log" not in table_names:
            conn.execute(
                text(
                    """
                    CREATE TABLE audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        actor_user_id INTEGER NULL,
                        action VARCHAR(64) NOT NULL,
                        target_type VARCHAR(64) NOT NULL,
                        target_id VARCHAR(128) NULL,
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        created_at DATETIME,
                        FOREIGN KEY(actor_user_id) REFERENCES users(id)
                    )
                    """
                )
            )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_actor_user_id ON audit_log(actor_user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_action ON audit_log(action)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_target_type ON audit_log(target_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_target_id ON audit_log(target_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_created_at ON audit_log(created_at)"))

        if "user_risk_guard" not in table_names:
            conn.execute(
                text(
                    """
                    CREATE TABLE user_risk_guard (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL UNIQUE,
                        manual_halt BOOLEAN NOT NULL DEFAULT 0,
                        emergency_kill_switch BOOLEAN NOT NULL DEFAULT 0,
                        reason TEXT NULL,
                        updated_by_user_id INTEGER NULL,
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY(user_id) REFERENCES users(id),
                        FOREIGN KEY(updated_by_user_id) REFERENCES users(id)
                    )
                    """
                )
            )
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_risk_guard_user_id ON user_risk_guard(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_risk_guard_user_id ON user_risk_guard(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_risk_guard_manual_halt ON user_risk_guard(manual_halt)"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_user_risk_guard_emergency_kill_switch ON user_risk_guard(emergency_kill_switch)")
        )

        if "user_exchange_credentials" in table_names:
            credential_cols = {col["name"] for col in inspector.get_columns("user_exchange_credentials")}
            if "key_version" not in credential_cols:
                conn.execute(text("ALTER TABLE user_exchange_credentials ADD COLUMN key_version VARCHAR(32) DEFAULT 'v1'"))
            conn.execute(text("UPDATE user_exchange_credentials SET key_version = 'v1' WHERE key_version IS NULL OR TRIM(key_version) = ''"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_exchange_credentials_key_version ON user_exchange_credentials(key_version)"))

        if "user_api_budget" not in table_names:
            conn.execute(
                text(
                    """
                    CREATE TABLE user_api_budget (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        scope VARCHAR(16) NOT NULL,
                        window_started_at DATETIME,
                        window_seconds INTEGER NOT NULL DEFAULT 60,
                        request_count INTEGER NOT NULL DEFAULT 0,
                        blocked_count INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY(user_id) REFERENCES users(id),
                        UNIQUE(user_id, scope)
                    )
                    """
                )
            )
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_api_budget_user_scope ON user_api_budget(user_id, scope)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_api_budget_user_id ON user_api_budget(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_api_budget_scope ON user_api_budget(scope)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_api_budget_window_started_at ON user_api_budget(window_started_at)"))

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
                ("max_weekly_loss_pct", "NUMERIC(10,6) DEFAULT 0"),
                ("max_monthly_loss_pct", "NUMERIC(10,6) DEFAULT 0"),
                ("cooldown_hours_on_halt", "INTEGER DEFAULT 0"),
                ("max_new_orders_per_day", "INTEGER DEFAULT 0"),
                ("max_orders_per_week", "INTEGER DEFAULT 0"),
                ("min_edge_pct", "NUMERIC(10,6) DEFAULT 0"),
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
            conn.execute(text("UPDATE bot_config SET max_weekly_loss_pct = 0 WHERE max_weekly_loss_pct IS NULL OR max_weekly_loss_pct < 0"))
            conn.execute(text("UPDATE bot_config SET max_monthly_loss_pct = 0 WHERE max_monthly_loss_pct IS NULL OR max_monthly_loss_pct < 0"))
            conn.execute(text("UPDATE bot_config SET cooldown_hours_on_halt = 0 WHERE cooldown_hours_on_halt IS NULL OR cooldown_hours_on_halt < 0"))
            conn.execute(text("UPDATE bot_config SET max_new_orders_per_day = 0 WHERE max_new_orders_per_day IS NULL OR max_new_orders_per_day < 0"))
            conn.execute(text("UPDATE bot_config SET max_orders_per_week = 0 WHERE max_orders_per_week IS NULL OR max_orders_per_week < 0"))
            conn.execute(text("UPDATE bot_config SET min_edge_pct = 0 WHERE min_edge_pct IS NULL OR min_edge_pct < 0"))

        if "user_bot_config" in table_names:
            user_bot_cols = {col["name"] for col in inspector.get_columns("user_bot_config")}
            user_policy_cols = [
                ("max_weekly_loss_pct", "NUMERIC(10,6) DEFAULT 0"),
                ("max_monthly_loss_pct", "NUMERIC(10,6) DEFAULT 0"),
                ("cooldown_hours_on_halt", "INTEGER DEFAULT 0"),
                ("max_new_orders_per_day", "INTEGER DEFAULT 0"),
                ("max_orders_per_week", "INTEGER DEFAULT 0"),
                ("min_edge_pct", "NUMERIC(10,6) DEFAULT 0"),
            ]
            for col_name, ddl in user_policy_cols:
                if col_name not in user_bot_cols:
                    conn.execute(text(f"ALTER TABLE user_bot_config ADD COLUMN {col_name} {ddl}"))
            conn.execute(text("UPDATE user_bot_config SET max_weekly_loss_pct = 0 WHERE max_weekly_loss_pct IS NULL OR max_weekly_loss_pct < 0"))
            conn.execute(text("UPDATE user_bot_config SET max_monthly_loss_pct = 0 WHERE max_monthly_loss_pct IS NULL OR max_monthly_loss_pct < 0"))
            conn.execute(text("UPDATE user_bot_config SET cooldown_hours_on_halt = 0 WHERE cooldown_hours_on_halt IS NULL OR cooldown_hours_on_halt < 0"))
            conn.execute(text("UPDATE user_bot_config SET max_new_orders_per_day = 0 WHERE max_new_orders_per_day IS NULL OR max_new_orders_per_day < 0"))
            conn.execute(text("UPDATE user_bot_config SET max_orders_per_week = 0 WHERE max_orders_per_week IS NULL OR max_orders_per_week < 0"))
            conn.execute(text("UPDATE user_bot_config SET min_edge_pct = 0 WHERE min_edge_pct IS NULL OR min_edge_pct < 0"))

        if "user_bot_runtime" in table_names:
            runtime_cols = {col["name"] for col in inspector.get_columns("user_bot_runtime")}
            if "halt_reason" not in runtime_cols:
                conn.execute(text("ALTER TABLE user_bot_runtime ADD COLUMN halt_reason VARCHAR(64)"))
            if "cooldown_until" not in runtime_cols:
                conn.execute(text("ALTER TABLE user_bot_runtime ADD COLUMN cooldown_until DATETIME"))
            if "halted_at" not in runtime_cols:
                conn.execute(text("ALTER TABLE user_bot_runtime ADD COLUMN halted_at DATETIME"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_bot_runtime_halt_reason ON user_bot_runtime(halt_reason)"))
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
                        user_id INTEGER NOT NULL,
                        date_utc DATE NOT NULL,
                        start_equity NUMERIC(28,8) NOT NULL DEFAULT 0,
                        start_realized_pnl NUMERIC(28,8) NOT NULL DEFAULT 0,
                        last_equity NUMERIC(28,8) NOT NULL DEFAULT 0,
                        realized_pnl NUMERIC(28,8) NOT NULL DEFAULT 0,
                        unrealized_pnl NUMERIC(28,8) NOT NULL DEFAULT 0,
                        daily_pnl_abs NUMERIC(28,8) NOT NULL DEFAULT 0,
                        daily_pnl_pct NUMERIC(28,8) NOT NULL DEFAULT 0,
                        updated_at DATETIME,
                        PRIMARY KEY (user_id, date_utc)
                    )
                    """
                )
            )
        else:
            daily_cols = {col["name"] for col in inspector.get_columns("daily_equity")}
            if "start_realized_pnl" not in daily_cols:
                conn.execute(text("ALTER TABLE daily_equity ADD COLUMN start_realized_pnl NUMERIC(28,8) DEFAULT 0"))
                conn.execute(text("UPDATE daily_equity SET start_realized_pnl = COALESCE(realized_pnl, 0) WHERE start_realized_pnl IS NULL"))
            if not _pk_matches(conn, "daily_equity", ("user_id", "date_utc")):
                _sqlite_rebuild_daily_equity_user_scope(conn, owner_user_id=owner_user_id)
            else:
                _ensure_user_scope_column(conn, table_name="daily_equity", owner_user_id=owner_user_id)
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_daily_equity_user_id ON daily_equity(user_id)"))

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

        if "positions" in table_names:
            if not _pk_matches(conn, "positions", ("user_id", "market")):
                _sqlite_rebuild_positions_user_scope(conn, owner_user_id=owner_user_id)
            else:
                _ensure_user_scope_column(conn, table_name="positions", owner_user_id=owner_user_id)
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_positions_user_id ON positions(user_id)"))

        if "paper_wallet" in table_names:
            if not _pk_matches(conn, "paper_wallet", ("user_id",)):
                _sqlite_rebuild_paper_wallet_user_scope(conn, owner_user_id=owner_user_id)
            else:
                _ensure_user_scope_column(conn, table_name="paper_wallet", owner_user_id=owner_user_id)
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_paper_wallet_user_id ON paper_wallet(user_id)"))

        refreshed_table_names = set(inspect(conn).get_table_names())
        if "user_bot_config" in refreshed_table_names:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_bot_config_user_id ON user_bot_config(user_id)"))
        if "user_bot_runtime" in refreshed_table_names:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_bot_runtime_user_id ON user_bot_runtime(user_id)"))

        _seed_user_bot_scope(conn, owner_user_id=owner_user_id)

        conn.execute(text("DROP INDEX IF EXISTS ix_trade_metrics_order_id"))


def _backfill_order_attempts(conn) -> None:
    """Backfill one synthetic attempt row per legacy order when no attempts exist."""
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())
    if "orders" not in table_names or "order_attempts" not in table_names:
        return

    attempt_cols = {col["name"] for col in inspector.get_columns("order_attempts")}
    required = {
        "order_id",
        "attempt_no",
        "submit_reason",
        "requested_price",
        "requested_volume",
        "upbit_identifier",
        "upbit_uuid",
        "state",
        "retry_count",
        "error_class",
        "last_error",
        "exchange_response_raw",
        "created_at",
        "updated_at",
    }
    if not required.issubset(attempt_cols):
        return

    conn.execute(
        text(
            """
            INSERT INTO order_attempts (
                order_id,
                attempt_no,
                submit_reason,
                requested_price,
                requested_volume,
                upbit_identifier,
                upbit_uuid,
                state,
                retry_count,
                error_class,
                last_error,
                exchange_response_raw,
                created_at,
                updated_at
            )
            SELECT
                o.id,
                1,
                'INITIAL',
                o.requested_price,
                o.requested_volume,
                o.upbit_identifier,
                o.upbit_uuid,
                COALESCE(o.state, 'NEW'),
                COALESCE(o.retry_count, 0),
                o.error_class,
                o.last_error,
                o.exchange_response_raw,
                o.created_at,
                o.updated_at
            FROM orders o
            WHERE NOT EXISTS (
                SELECT 1
                FROM order_attempts a
                WHERE a.order_id = o.id
            )
            """
        )
    )


def _seed_timeframe_config(conn) -> None:
    table_names = set(inspect(conn).get_table_names())
    if "timeframe_config" not in table_names:
        return

    existing = conn.execute(text("SELECT timeframe FROM timeframe_config")).fetchall()
    existing_timeframes = {row[0] for row in existing}
    for timeframe in SUPPORTED_TIMEFRAMES:
        if timeframe not in existing_timeframes:
            conn.execute(
                text("INSERT INTO timeframe_config (timeframe, is_enabled, updated_at) VALUES (:timeframe, false, CURRENT_TIMESTAMP)"),
                {"timeframe": timeframe},
            )
    conn.execute(text("UPDATE timeframe_config SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))

    enabled_count = conn.execute(text("SELECT COUNT(*) FROM timeframe_config WHERE is_enabled = true")).scalar_one()
    if enabled_count == 0:
        current = None
        if "bot_config" in table_names:
            current = conn.execute(text("SELECT timeframe FROM bot_config WHERE id = 1")).scalar_one_or_none()
        selected = current if current in SUPPORTED_TIMEFRAMES else "15m"
        conn.execute(
            text("UPDATE timeframe_config SET is_enabled = CASE WHEN timeframe = :timeframe THEN true ELSE false END"),
            {"timeframe": selected},
        )


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

    table_doc_cols = {col["name"] for col in inspect(conn).get_columns("schema_table_docs")}
    table_desc_en_expr = "COALESCE(description, '')"
    table_desc_ko_expr = "COALESCE(description, '')"
    if "description_en" in table_doc_cols:
        table_desc_en_expr = "COALESCE(NULLIF(description_en, ''), COALESCE(description, ''))"
    if "description_ko" in table_doc_cols:
        table_desc_ko_expr = "COALESCE(NULLIF(description_ko, ''), COALESCE(description, ''))"
    if "description" in table_doc_cols:
        conn.execute(text("CREATE TABLE schema_table_docs_new (table_name TEXT PRIMARY KEY, description_en TEXT NOT NULL DEFAULT '', description_ko TEXT NOT NULL DEFAULT '')"))
        conn.execute(
            text(
                f"""
                INSERT INTO schema_table_docs_new (table_name, description_en, description_ko)
                SELECT
                    table_name,
                    {table_desc_en_expr},
                    {table_desc_ko_expr}
                FROM schema_table_docs
                """
            )
        )
        conn.execute(text("DROP TABLE schema_table_docs"))
        conn.execute(text("ALTER TABLE schema_table_docs_new RENAME TO schema_table_docs"))

    column_doc_cols = {col["name"] for col in inspect(conn).get_columns("schema_column_docs")}
    column_desc_en_expr = "COALESCE(description, '')"
    column_desc_ko_expr = "COALESCE(description, '')"
    if "description_en" in column_doc_cols:
        column_desc_en_expr = "COALESCE(NULLIF(description_en, ''), COALESCE(description, ''))"
    if "description_ko" in column_doc_cols:
        column_desc_ko_expr = "COALESCE(NULLIF(description_ko, ''), COALESCE(description, ''))"
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
                f"""
                INSERT INTO schema_column_docs_new (table_name, column_name, description_en, description_ko)
                SELECT
                    table_name,
                    column_name,
                    {column_desc_en_expr},
                    {column_desc_ko_expr}
                FROM schema_column_docs
                """
            )
        )
        conn.execute(text("DROP TABLE schema_column_docs"))
        conn.execute(text("ALTER TABLE schema_column_docs_new RENAME TO schema_column_docs"))

    for table_name, description_en in TABLE_DOCS_EN.items():
        description_ko = TABLE_DOCS_KO.get(table_name, description_en)
        updated = conn.execute(
            text(
                "UPDATE schema_table_docs "
                "SET description_en = :description_en, description_ko = :description_ko "
                "WHERE table_name = :table_name"
            ),
            {"table_name": table_name, "description_en": description_en, "description_ko": description_ko},
        )
        if updated.rowcount == 0:
            conn.execute(
                text(
                    "INSERT INTO schema_table_docs (table_name, description_en, description_ko) "
                    "VALUES (:table_name, :description_en, :description_ko)"
                ),
                {"table_name": table_name, "description_en": description_en, "description_ko": description_ko},
            )

    for table_name, columns_en in COLUMN_DOCS_EN.items():
        columns_ko = COLUMN_DOCS_KO.get(table_name, {})
        for column_name, description_en in columns_en.items():
            description_ko = columns_ko.get(column_name, description_en)
            updated = conn.execute(
                text(
                    "UPDATE schema_column_docs "
                    "SET description_en = :description_en, description_ko = :description_ko "
                    "WHERE table_name = :table_name AND column_name = :column_name"
                ),
                {
                    "table_name": table_name,
                    "column_name": column_name,
                    "description_en": description_en,
                    "description_ko": description_ko,
                },
            )
            if updated.rowcount == 0:
                conn.execute(
                    text(
                        "INSERT INTO schema_column_docs (table_name, column_name, description_en, description_ko) "
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
    required_tables = set(TABLE_DOCS_EN) | {"schema_table_docs", "schema_column_docs"}
    existing_tables = set(inspect(conn).get_table_names())
    if not required_tables.issubset(existing_tables):
        return

    for view_name, sql in _get_kst_view_sql(conn).items():
        conn.execute(text(f"DROP VIEW IF EXISTS {view_name}"))
        conn.execute(text(sql))


def _drop_kst_views(conn) -> None:
    for view_name in _get_kst_view_sql(conn).keys():
        conn.execute(text(f"DROP VIEW IF EXISTS {view_name}"))


def initialize_database() -> None:
    """Create base schema and apply lightweight migrations."""
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()
    with engine.begin() as conn:
        _backfill_order_attempts(conn)
        _seed_timeframe_config(conn)
        _sync_schema_docs(conn)
        _drop_kst_views(conn)
