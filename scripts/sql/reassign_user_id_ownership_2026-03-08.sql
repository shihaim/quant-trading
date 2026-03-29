\set old_user_id 1
\set new_user_id 7
\set move_audit 0

-- User ownership reassignment (PostgreSQL, fail-fast)
-- Usage:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--     -v old_user_id=1 -v new_user_id=7 -v move_audit=0 \
--     -f scripts/sql/reassign_user_id_ownership_2026-03-08.sql
--
-- move_audit:
--   0 => keep audit actor ids as-is
--   1 => also move audit_log.actor_user_id and user_risk_guard.updated_by_user_id

BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE TEMP TABLE _user_reassign_params (
    old_id INTEGER NOT NULL,
    new_id INTEGER NOT NULL,
    move_audit_flag INTEGER NOT NULL
) ON COMMIT DROP;

INSERT INTO _user_reassign_params (old_id, new_id, move_audit_flag)
VALUES (:'old_user_id', :'new_user_id', :'move_audit');

DO $$
DECLARE
    old_id INTEGER;
    new_id INTEGER;
    move_audit_flag INTEGER;
    source_user_exists BOOLEAN;
    has_source_rows BOOLEAN := FALSE;
BEGIN
    SELECT p.old_id, p.new_id, p.move_audit_flag
      INTO old_id, new_id, move_audit_flag
      FROM _user_reassign_params p;

    IF old_id <= 0 OR new_id <= 0 THEN
        RAISE EXCEPTION 'old_user_id and new_user_id must be positive integers';
    END IF;
    IF old_id = new_id THEN
        RAISE EXCEPTION 'old_user_id and new_user_id must be different';
    END IF;
    IF move_audit_flag NOT IN (0, 1) THEN
        RAISE EXCEPTION 'move_audit must be 0 or 1';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM users WHERE id = new_id) THEN
        RAISE EXCEPTION 'target user (id=%) does not exist in users table', new_id;
    END IF;
    SELECT EXISTS (SELECT 1 FROM users WHERE id = old_id) INTO source_user_exists;

    IF to_regclass('public.user_exchange_credentials') IS NOT NULL
       AND EXISTS (SELECT 1 FROM user_exchange_credentials WHERE user_id = old_id) THEN
        has_source_rows := TRUE;
    END IF;
    IF to_regclass('public.orders') IS NOT NULL
       AND EXISTS (SELECT 1 FROM orders WHERE user_id = old_id) THEN
        has_source_rows := TRUE;
    END IF;
    IF to_regclass('public.positions') IS NOT NULL
       AND EXISTS (SELECT 1 FROM positions WHERE user_id = old_id) THEN
        has_source_rows := TRUE;
    END IF;
    IF to_regclass('public.daily_equity') IS NOT NULL
       AND EXISTS (SELECT 1 FROM daily_equity WHERE user_id = old_id) THEN
        has_source_rows := TRUE;
    END IF;
    IF to_regclass('public.paper_wallet') IS NOT NULL
       AND EXISTS (SELECT 1 FROM paper_wallet WHERE user_id = old_id) THEN
        has_source_rows := TRUE;
    END IF;
    IF to_regclass('public.user_bot_config') IS NOT NULL
       AND EXISTS (SELECT 1 FROM user_bot_config WHERE user_id = old_id) THEN
        has_source_rows := TRUE;
    END IF;
    IF to_regclass('public.user_bot_runtime') IS NOT NULL
       AND EXISTS (SELECT 1 FROM user_bot_runtime WHERE user_id = old_id) THEN
        has_source_rows := TRUE;
    END IF;
    IF to_regclass('public.user_risk_guard') IS NOT NULL
       AND EXISTS (SELECT 1 FROM user_risk_guard WHERE user_id = old_id) THEN
        has_source_rows := TRUE;
    END IF;
    IF to_regclass('public.user_api_budget') IS NOT NULL
       AND EXISTS (SELECT 1 FROM user_api_budget WHERE user_id = old_id) THEN
        has_source_rows := TRUE;
    END IF;

    IF NOT source_user_exists AND NOT has_source_rows THEN
        RAISE EXCEPTION 'source user (id=%) does not exist and no ownership rows were found', old_id;
    END IF;
    IF NOT source_user_exists AND has_source_rows THEN
        RAISE NOTICE 'source user id % is missing in users, but ownership rows exist and will be reassigned', old_id;
    END IF;

    -- Conflict checks before UPDATE
    IF to_regclass('public.user_exchange_credentials') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM user_exchange_credentials old_row
           JOIN user_exchange_credentials new_row
             ON new_row.exchange = old_row.exchange
            AND new_row.user_id = new_id
          WHERE old_row.user_id = old_id
       ) THEN
        RAISE EXCEPTION 'conflict: user_exchange_credentials has overlapping exchange rows';
    END IF;

    IF to_regclass('public.orders') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM orders old_row
           JOIN orders new_row
             ON new_row.client_order_id = old_row.client_order_id
            AND new_row.user_id = new_id
          WHERE old_row.user_id = old_id
       ) THEN
        RAISE EXCEPTION 'conflict: orders has overlapping client_order_id rows';
    END IF;

    IF to_regclass('public.positions') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM positions old_row
           JOIN positions new_row
             ON new_row.market = old_row.market
            AND new_row.user_id = new_id
          WHERE old_row.user_id = old_id
       ) THEN
        RAISE EXCEPTION 'conflict: positions has overlapping market rows';
    END IF;

    IF to_regclass('public.daily_equity') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM daily_equity old_row
           JOIN daily_equity new_row
             ON new_row.date_utc = old_row.date_utc
            AND new_row.user_id = new_id
          WHERE old_row.user_id = old_id
       ) THEN
        RAISE EXCEPTION 'conflict: daily_equity has overlapping date_utc rows';
    END IF;

    IF to_regclass('public.paper_wallet') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM paper_wallet old_row
           JOIN paper_wallet new_row
             ON new_row.user_id = new_id
          WHERE old_row.user_id = old_id
       ) THEN
        RAISE EXCEPTION 'conflict: paper_wallet already has both old/new user rows';
    END IF;

    IF to_regclass('public.user_bot_config') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM user_bot_config old_row
           JOIN user_bot_config new_row
             ON new_row.user_id = new_id
          WHERE old_row.user_id = old_id
       ) THEN
        RAISE EXCEPTION 'conflict: user_bot_config already has both old/new user rows';
    END IF;

    IF to_regclass('public.user_bot_runtime') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM user_bot_runtime old_row
           JOIN user_bot_runtime new_row
             ON new_row.user_id = new_id
          WHERE old_row.user_id = old_id
       ) THEN
        RAISE EXCEPTION 'conflict: user_bot_runtime already has both old/new user rows';
    END IF;

    IF to_regclass('public.user_risk_guard') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM user_risk_guard old_row
           JOIN user_risk_guard new_row
             ON new_row.user_id = new_id
          WHERE old_row.user_id = old_id
       ) THEN
        RAISE EXCEPTION 'conflict: user_risk_guard already has both old/new user rows';
    END IF;

    IF to_regclass('public.user_api_budget') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM user_api_budget old_row
           JOIN user_api_budget new_row
             ON new_row.scope = old_row.scope
            AND new_row.user_id = new_id
          WHERE old_row.user_id = old_id
       ) THEN
        RAISE EXCEPTION 'conflict: user_api_budget has overlapping scope rows';
    END IF;
END $$;

DO $$
DECLARE
    old_id INTEGER;
    new_id INTEGER;
BEGIN
    SELECT p.old_id, p.new_id
      INTO old_id, new_id
      FROM _user_reassign_params p;

    IF to_regclass('public.user_exchange_credentials') IS NOT NULL THEN
        UPDATE user_exchange_credentials SET user_id = new_id WHERE user_id = old_id;
    END IF;
    IF to_regclass('public.orders') IS NOT NULL THEN
        UPDATE orders SET user_id = new_id WHERE user_id = old_id;
    END IF;
    IF to_regclass('public.positions') IS NOT NULL THEN
        UPDATE positions SET user_id = new_id WHERE user_id = old_id;
    END IF;
    IF to_regclass('public.daily_equity') IS NOT NULL THEN
        UPDATE daily_equity SET user_id = new_id WHERE user_id = old_id;
    END IF;
    IF to_regclass('public.paper_wallet') IS NOT NULL THEN
        UPDATE paper_wallet SET user_id = new_id WHERE user_id = old_id;
    END IF;
    IF to_regclass('public.user_bot_config') IS NOT NULL THEN
        UPDATE user_bot_config SET user_id = new_id WHERE user_id = old_id;
    END IF;
    IF to_regclass('public.user_bot_runtime') IS NOT NULL THEN
        UPDATE user_bot_runtime SET user_id = new_id WHERE user_id = old_id;
    END IF;
    IF to_regclass('public.user_risk_guard') IS NOT NULL THEN
        UPDATE user_risk_guard SET user_id = new_id WHERE user_id = old_id;
    END IF;
    IF to_regclass('public.user_api_budget') IS NOT NULL THEN
        UPDATE user_api_budget SET user_id = new_id WHERE user_id = old_id;
    END IF;
END $$;

DO $$
DECLARE
    old_id INTEGER;
    new_id INTEGER;
    move_audit_flag INTEGER;
BEGIN
    SELECT p.old_id, p.new_id, p.move_audit_flag
      INTO old_id, new_id, move_audit_flag
      FROM _user_reassign_params p;

    IF move_audit_flag = 1 THEN
        IF to_regclass('public.audit_log') IS NOT NULL THEN
            UPDATE audit_log
               SET actor_user_id = new_id
             WHERE actor_user_id = old_id;
        END IF;
        IF to_regclass('public.user_risk_guard') IS NOT NULL THEN
            UPDATE user_risk_guard
               SET updated_by_user_id = new_id
             WHERE updated_by_user_id = old_id;
        END IF;
    END IF;
END $$;

COMMIT;

-- Post-check summary
SELECT 'users' AS table_name, id AS key, email AS info
FROM users
WHERE id IN (:old_user_id, :new_user_id)
ORDER BY id;

SELECT 'user_exchange_credentials' AS table_name, user_id, COUNT(*) AS row_count
FROM user_exchange_credentials
WHERE user_id IN (:old_user_id, :new_user_id)
GROUP BY user_id
ORDER BY user_id;

SELECT 'orders' AS table_name, user_id, COUNT(*) AS row_count
FROM orders
WHERE user_id IN (:old_user_id, :new_user_id)
GROUP BY user_id
ORDER BY user_id;

SELECT 'positions' AS table_name, user_id, COUNT(*) AS row_count
FROM positions
WHERE user_id IN (:old_user_id, :new_user_id)
GROUP BY user_id
ORDER BY user_id;

SELECT 'daily_equity' AS table_name, user_id, COUNT(*) AS row_count
FROM daily_equity
WHERE user_id IN (:old_user_id, :new_user_id)
GROUP BY user_id
ORDER BY user_id;

SELECT 'paper_wallet' AS table_name, user_id, COUNT(*) AS row_count
FROM paper_wallet
WHERE user_id IN (:old_user_id, :new_user_id)
GROUP BY user_id
ORDER BY user_id;
