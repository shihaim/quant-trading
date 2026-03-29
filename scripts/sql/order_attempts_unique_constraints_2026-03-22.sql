-- order_attempts uniqueness hardening (draft)
-- Date: 2026-03-22
-- Scope:
-- - Normalize blank refs to NULL
-- - Fail fast when duplicate refs exist
-- - Add partial unique indexes for non-null exchange references

BEGIN;

-- 1) Normalize blank strings so partial unique indexes can ignore missing refs.
UPDATE order_attempts
SET upbit_identifier = NULL
WHERE upbit_identifier IS NOT NULL AND BTRIM(upbit_identifier) = '';

UPDATE order_attempts
SET upbit_uuid = NULL
WHERE upbit_uuid IS NOT NULL AND BTRIM(upbit_uuid) = '';

-- 2) Guard: fail before index creation if duplicates exist.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT upbit_identifier
            FROM order_attempts
            WHERE upbit_identifier IS NOT NULL AND BTRIM(upbit_identifier) <> ''
            GROUP BY upbit_identifier
            HAVING COUNT(*) > 1
        ) dup
    ) THEN
        RAISE EXCEPTION 'Duplicate order_attempts.upbit_identifier detected. Cleanup required before unique index.';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT upbit_uuid
            FROM order_attempts
            WHERE upbit_uuid IS NOT NULL AND BTRIM(upbit_uuid) <> ''
            GROUP BY upbit_uuid
            HAVING COUNT(*) > 1
        ) dup
    ) THEN
        RAISE EXCEPTION 'Duplicate order_attempts.upbit_uuid detected. Cleanup required before unique index.';
    END IF;
END $$;

-- 3) Add uniqueness for non-null refs.
CREATE UNIQUE INDEX IF NOT EXISTS uq_order_attempts_upbit_identifier_not_null
    ON order_attempts (upbit_identifier)
    WHERE upbit_identifier IS NOT NULL AND BTRIM(upbit_identifier) <> '';

CREATE UNIQUE INDEX IF NOT EXISTS uq_order_attempts_upbit_uuid_not_null
    ON order_attempts (upbit_uuid)
    WHERE upbit_uuid IS NOT NULL AND BTRIM(upbit_uuid) <> '';

COMMIT;
