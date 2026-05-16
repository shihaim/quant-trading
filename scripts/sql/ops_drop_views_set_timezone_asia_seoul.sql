-- Ops helper: remove repo-managed KST helper views and set timezone to Asia/Seoul.
-- Usage:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/sql/ops_drop_views_set_timezone_asia_seoul.sql
--
-- Safety:
--   This script intentionally drops only views managed by trader.data.db.
--   It does not enumerate or cascade-drop arbitrary public views.
--   ALTER DATABASE/ROLE targets the current connection database and user.

BEGIN;

DO $$
DECLARE
    view_name TEXT;
    view_names TEXT[] := ARRAY[
        'bot_config_kst',
        'timeframe_config_kst',
        'candles_kst',
        'orders_kst',
        'audit_log_kst',
        'user_risk_guard_kst',
        'user_api_budget_kst',
        'fills_kst',
        'trade_metrics_kst',
        'positions_kst',
        'daily_equity_kst',
        'paper_wallet_kst',
        'schema_table_docs_kst',
        'schema_column_docs_kst'
    ];
BEGIN
    FOREACH view_name IN ARRAY view_names
    LOOP
        EXECUTE format('DROP VIEW IF EXISTS public.%I', view_name);
    END LOOP;
END $$;

DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'Asia/Seoul');
    EXECUTE format('ALTER ROLE %I SET timezone TO %L', current_user, 'Asia/Seoul');
END $$;

SET timezone TO 'Asia/Seoul';

COMMIT;
