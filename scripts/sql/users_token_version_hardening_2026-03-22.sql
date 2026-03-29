-- users token_version hardening (draft)
-- Date: 2026-03-22
-- Scope:
-- - Add token_version for server-side session invalidation
-- - Backfill/normalize values
-- - Add index for guard lookups

BEGIN;

ALTER TABLE IF EXISTS users
    ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 1;

UPDATE users
SET token_version = 1
WHERE token_version IS NULL OR token_version <= 0;

ALTER TABLE IF EXISTS users
    ALTER COLUMN token_version SET DEFAULT 1;

ALTER TABLE IF EXISTS users
    ALTER COLUMN token_version SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_users_token_version ON users(token_version);

COMMIT;
