# order_attempts unique 제약 런북 (2026-03-22)

## 목표

아래 column에 unique hardening을 적용한다.

- `order_attempts.upbit_identifier` (null 제외)
- `order_attempts.upbit_uuid` (null 제외)

동시에 기존 S6 불변식을 유지한다.

- fill idempotency 유지
- identifier 기반 recovery semantics 유지
- 사용자 간 데이터 혼합 금지

## 사전 조건

1. 백업을 완료한다.
2. consistency check 결과가 clean이어야 한다.
3. 트래픽이 낮은 시간대에 적용한다.

## 현재 운영 snapshot 검증 결과

- Consistency report:
  - `backups/prod-order-attempts-consistency-20260322-180618.json`
- 요약:
  - duplicate identifier: `0`
  - duplicate uuid: `0`
  - order/latest-attempt drift: `0`

## 적용

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/sql/order_attempts_unique_constraints_2026-03-22.sql
```

## 적용 후 확인

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

## 롤백

롤백이 필요하면 아래 index를 제거한다.

```sql
DROP INDEX IF EXISTS uq_order_attempts_upbit_identifier_not_null;
DROP INDEX IF EXISTS uq_order_attempts_upbit_uuid_not_null;
```

데이터 롤백이 필요하면 변경 전 백업 snapshot에서 복원한다.
