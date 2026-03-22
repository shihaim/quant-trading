# order_attempts Unique Constraint Runbook (2026-03-22)

## Goal

Apply uniqueness hardening for:

- `order_attempts.upbit_identifier` (non-null)
- `order_attempts.upbit_uuid` (non-null)

while keeping existing S6 invariants:

- fill idempotency unchanged
- identifier-based recovery semantics unchanged
- no cross-user mixing

## Preconditions

1. Backup is completed.
2. Consistency check is clean.
3. Apply during a low-traffic window.

## Verified on current prod snapshot

- Consistency report:
  - `backups/prod-order-attempts-consistency-20260322-180618.json`
- Summary:
  - duplicate identifier: `0`
  - duplicate uuid: `0`
  - order/latest-attempt drift: `0`

## Apply

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/sql/order_attempts_unique_constraints_2026-03-22.sql
```

## Post-check

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
    'uq_order_attempts_upbit_identifier_not_null',
    'uq_order_attempts_upbit_uuid_not_null'
  )
ORDER BY indexname;
```

```bash
python scripts/check_order_attempts_consistency.py --max-items 500 --fail-on-issues
```

## Rollback

If rollback is needed:

```sql
DROP INDEX IF EXISTS uq_order_attempts_upbit_identifier_not_null;
DROP INDEX IF EXISTS uq_order_attempts_upbit_uuid_not_null;
```

If data rollback is needed, restore from pre-change backup snapshot.
