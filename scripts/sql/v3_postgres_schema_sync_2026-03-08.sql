-- V3 PostgreSQL schema sync (idempotent)
-- Date: 2026-03-08
-- Scope:
-- - Add missing columns/indexes/tables needed by current V3 runtime
-- - Backfill safe defaults for legacy rows
-- - Add user-scoped uniqueness constraints where required

BEGIN;

-- 1) orders
ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS retry_count INTEGER;
ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS upbit_identifier VARCHAR(64);
ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS error_class VARCHAR(32);
ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS exchange_response_raw TEXT;
ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS intent VARCHAR(16);
ALTER TABLE IF EXISTS orders ADD COLUMN IF NOT EXISTS user_id INTEGER;
UPDATE orders SET retry_count = 0 WHERE retry_count IS NULL;
UPDATE orders SET user_id = COALESCE(user_id, 1) WHERE user_id IS NULL;
ALTER TABLE IF EXISTS orders ALTER COLUMN retry_count SET DEFAULT 0;
ALTER TABLE IF EXISTS orders ALTER COLUMN user_id SET DEFAULT 1;
ALTER TABLE IF EXISTS orders ALTER COLUMN user_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS ix_orders_user_id ON orders(user_id);
DO $$
BEGIN
    IF to_regclass('public.orders') IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_orders_user_client_order_id') THEN
        ALTER TABLE orders
            ADD CONSTRAINT uq_orders_user_client_order_id UNIQUE (user_id, client_order_id);
    END IF;
END $$;

-- 1.1) users token_version for session invalidation baseline
ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 1;
UPDATE users SET token_version = 1 WHERE token_version IS NULL OR token_version <= 0;
ALTER TABLE IF EXISTS users ALTER COLUMN token_version SET DEFAULT 1;
ALTER TABLE IF EXISTS users ALTER COLUMN token_version SET NOT NULL;
CREATE INDEX IF NOT EXISTS ix_users_token_version ON users(token_version);

-- 2) fills
ALTER TABLE IF EXISTS fills ADD COLUMN IF NOT EXISTS is_applied BOOLEAN;
UPDATE fills SET is_applied = FALSE WHERE is_applied IS NULL;
ALTER TABLE IF EXISTS fills ALTER COLUMN is_applied SET DEFAULT FALSE;
ALTER TABLE IF EXISTS fills ALTER COLUMN is_applied SET NOT NULL;
CREATE INDEX IF NOT EXISTS ix_fills_is_applied ON fills(is_applied);

-- 3) user_exchange_credentials key_version
CREATE TABLE IF NOT EXISTS user_exchange_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    exchange VARCHAR(32) NOT NULL DEFAULT 'UPBIT',
    access_key_encrypted TEXT NOT NULL,
    secret_key_encrypted TEXT NOT NULL,
    key_version VARCHAR(32) NOT NULL DEFAULT 'v1',
    access_key_masked VARCHAR(32) NOT NULL,
    access_key_fingerprint VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_exchange_credentials_user_exchange UNIQUE (user_id, exchange)
);
ALTER TABLE IF EXISTS user_exchange_credentials ADD COLUMN IF NOT EXISTS key_version VARCHAR(32);
UPDATE user_exchange_credentials
SET key_version = 'v1'
WHERE key_version IS NULL OR BTRIM(key_version) = '';
ALTER TABLE IF EXISTS user_exchange_credentials ALTER COLUMN key_version SET DEFAULT 'v1';
ALTER TABLE IF EXISTS user_exchange_credentials ALTER COLUMN key_version SET NOT NULL;
CREATE INDEX IF NOT EXISTS ix_user_exchange_credentials_key_version
    ON user_exchange_credentials(key_version);

-- 4) user-scoped state tables
ALTER TABLE IF EXISTS positions ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE IF EXISTS daily_equity ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE IF EXISTS daily_equity ADD COLUMN IF NOT EXISTS start_realized_pnl NUMERIC(28,8);
ALTER TABLE IF EXISTS paper_wallet ADD COLUMN IF NOT EXISTS user_id INTEGER;

UPDATE positions SET user_id = COALESCE(user_id, 1) WHERE user_id IS NULL;
UPDATE daily_equity SET user_id = COALESCE(user_id, 1) WHERE user_id IS NULL;
UPDATE daily_equity
SET start_realized_pnl = COALESCE(start_realized_pnl, realized_pnl, 0)
WHERE start_realized_pnl IS NULL;
UPDATE paper_wallet SET user_id = COALESCE(user_id, 1) WHERE user_id IS NULL;

ALTER TABLE IF EXISTS positions ALTER COLUMN user_id SET DEFAULT 1;
ALTER TABLE IF EXISTS daily_equity ALTER COLUMN user_id SET DEFAULT 1;
ALTER TABLE IF EXISTS paper_wallet ALTER COLUMN user_id SET DEFAULT 1;
ALTER TABLE IF EXISTS positions ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE IF EXISTS daily_equity ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE IF EXISTS paper_wallet ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE IF EXISTS daily_equity ALTER COLUMN start_realized_pnl SET DEFAULT 0;
ALTER TABLE IF EXISTS daily_equity ALTER COLUMN start_realized_pnl SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_positions_user_id ON positions(user_id);
CREATE INDEX IF NOT EXISTS ix_daily_equity_user_id ON daily_equity(user_id);
CREATE INDEX IF NOT EXISTS ix_paper_wallet_user_id ON paper_wallet(user_id);

-- Fail fast if duplicate rows exist (no automatic delete in production sync).
DO $$
BEGIN
    IF to_regclass('public.paper_wallet') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM (
               SELECT user_id
               FROM paper_wallet
               GROUP BY user_id
               HAVING COUNT(*) > 1
           ) dup
       ) THEN
        RAISE EXCEPTION 'Duplicate paper_wallet rows by user_id detected. Resolve manually before schema sync.';
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('public.orders') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM (
               SELECT user_id, client_order_id
               FROM orders
               GROUP BY user_id, client_order_id
               HAVING COUNT(*) > 1
           ) dup
       ) THEN
        RAISE EXCEPTION 'Duplicate orders rows by (user_id, client_order_id) detected.';
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('public.positions') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM (
               SELECT user_id, market
               FROM positions
               GROUP BY user_id, market
               HAVING COUNT(*) > 1
           ) dup
       ) THEN
        RAISE EXCEPTION 'Duplicate positions rows by (user_id, market) detected.';
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('public.daily_equity') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM (
               SELECT user_id, date_utc
               FROM daily_equity
               GROUP BY user_id, date_utc
               HAVING COUNT(*) > 1
           ) dup
       ) THEN
        RAISE EXCEPTION 'Duplicate daily_equity rows by (user_id, date_utc) detected.';
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('public.positions') IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_positions_user_market') THEN
        ALTER TABLE positions
            ADD CONSTRAINT uq_positions_user_market UNIQUE (user_id, market);
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('public.daily_equity') IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_daily_equity_user_date') THEN
        ALTER TABLE daily_equity
            ADD CONSTRAINT uq_daily_equity_user_date UNIQUE (user_id, date_utc);
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('public.paper_wallet') IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_paper_wallet_user') THEN
        ALTER TABLE paper_wallet
            ADD CONSTRAINT uq_paper_wallet_user UNIQUE (user_id);
    END IF;
END $$;

-- 5) V3 support tables
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    actor_user_id INTEGER NULL REFERENCES users(id),
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(64) NOT NULL,
    target_id VARCHAR(128) NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_log_actor_user_id ON audit_log(actor_user_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS ix_audit_log_target_type ON audit_log(target_type);
CREATE INDEX IF NOT EXISTS ix_audit_log_target_id ON audit_log(target_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_created_at ON audit_log(created_at);

CREATE TABLE IF NOT EXISTS user_risk_guard (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    manual_halt BOOLEAN NOT NULL DEFAULT FALSE,
    emergency_kill_switch BOOLEAN NOT NULL DEFAULT FALSE,
    reason TEXT NULL,
    updated_by_user_id INTEGER NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_user_risk_guard_user_id ON user_risk_guard(user_id);
CREATE INDEX IF NOT EXISTS ix_user_risk_guard_manual_halt ON user_risk_guard(manual_halt);
CREATE INDEX IF NOT EXISTS ix_user_risk_guard_emergency_kill_switch ON user_risk_guard(emergency_kill_switch);

CREATE TABLE IF NOT EXISTS user_api_budget (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    scope VARCHAR(16) NOT NULL,
    window_started_at TIMESTAMPTZ,
    window_seconds INTEGER NOT NULL DEFAULT 60,
    request_count INTEGER NOT NULL DEFAULT 0,
    blocked_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_api_budget_user_scope UNIQUE (user_id, scope)
);
CREATE INDEX IF NOT EXISTS ix_user_api_budget_user_id ON user_api_budget(user_id);
CREATE INDEX IF NOT EXISTS ix_user_api_budget_scope ON user_api_budget(scope);
CREATE INDEX IF NOT EXISTS ix_user_api_budget_window_started_at ON user_api_budget(window_started_at);

CREATE TABLE IF NOT EXISTS user_bot_config (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    is_enabled BOOLEAN DEFAULT TRUE,
    timeframe VARCHAR(16) DEFAULT '15m',
    markets_json TEXT DEFAULT '["KRW-BTC"]',
    target_exposure_pct NUMERIC(10,6) DEFAULT 0.10,
    daily_loss_basis VARCHAR(32) DEFAULT 'TOTAL',
    min_rebalance_threshold_pct NUMERIC(10,6) DEFAULT 0.05,
    min_order_krw_buffer NUMERIC(18,8) DEFAULT 0,
    fill_timeout_sec_entry INTEGER DEFAULT 10,
    fill_timeout_sec_exit INTEGER DEFAULT 4,
    fill_timeout_sec_rebalance INTEGER DEFAULT 10,
    max_reprice_attempts_entry INTEGER DEFAULT 2,
    max_reprice_attempts_exit INTEGER DEFAULT 1,
    max_reprice_attempts_rebalance INTEGER DEFAULT 1,
    reprice_step_bps INTEGER DEFAULT 10,
    slippage_budget_entry_pct NUMERIC(10,6) DEFAULT 0.0005,
    slippage_budget_exit_pct NUMERIC(10,6) DEFAULT 0.0020,
    slippage_budget_breach_halt_count INTEGER DEFAULT 0,
    status_notify_interval_seconds INTEGER DEFAULT 14400,
    max_daily_loss_pct NUMERIC(10,6) DEFAULT 0.02,
    max_total_exposure_pct NUMERIC(10,6) DEFAULT 0.30,
    max_per_market_exposure_pct NUMERIC(10,6) DEFAULT 0.10,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_user_bot_config_user_id ON user_bot_config(user_id);

CREATE TABLE IF NOT EXISTS user_bot_runtime (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    is_enabled BOOLEAN DEFAULT TRUE,
    status VARCHAR(32) DEFAULT 'IDLE',
    last_tick_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    consecutive_failures INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_user_bot_runtime_user_id ON user_bot_runtime(user_id);

-- 6) timeframe_config (seed rows are handled by app bootstrap)
CREATE TABLE IF NOT EXISTS timeframe_config (
    id SERIAL PRIMARY KEY,
    timeframe VARCHAR(16) NOT NULL UNIQUE,
    is_enabled BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_timeframe_config_timeframe ON timeframe_config(timeframe);
CREATE INDEX IF NOT EXISTS ix_timeframe_config_is_enabled ON timeframe_config(is_enabled);

COMMIT;

-- 7) post-check hints
-- SELECT COUNT(*) AS null_orders_user_id FROM orders WHERE user_id IS NULL;
-- SELECT COUNT(*) AS null_positions_user_id FROM positions WHERE user_id IS NULL;
-- SELECT COUNT(*) AS null_daily_equity_user_id FROM daily_equity WHERE user_id IS NULL;
-- SELECT COUNT(*) AS null_paper_wallet_user_id FROM paper_wallet WHERE user_id IS NULL;
-- SELECT COUNT(*) AS missing_key_version FROM user_exchange_credentials WHERE key_version IS NULL OR BTRIM(key_version) = '';
