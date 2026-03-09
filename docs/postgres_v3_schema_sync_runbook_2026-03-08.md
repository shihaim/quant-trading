# PostgreSQL V3 Schema Sync Runbook (2026-03-08)

## 목적

운영 PostgreSQL이 기존 스키마(구버전)인 상태에서, 현재 V3 코드 배포 전에 필요한 최소 스키마 싱크를 안전하게 맞춘다.

핵심 포인트:
- 앱 시작 시 `Base.metadata.create_all()`은 신규 테이블 생성 중심이다.
- 기존 테이블 컬럼/제약 보강은 자동으로 모두 맞춰주지 않는다.
- 앱 bootstrap의 `run_lightweight_migrations()`는 PostgreSQL에서 `positions`, `daily_equity`의 `user_id`/PK 보정 일부를 수행할 수 있지만, 운영 스키마 전체 싱크를 대체하지는 않는다.

## 대상 파일

- 실행 SQL: `scripts/sql/v3_postgres_schema_sync_2026-03-08.sql`

## 언제 실행하나

- 운영 배포 직전(maintenance window 권장)
- 신규 빈 DB에는 필수는 아니지만, 재실행 안전(idempotent)하게 작성되어 있어 실행해도 무방

## 사전 조건

1. 운영 DB 백업 완료 (`pg_dump -Fc`)
2. 앱 쓰기 트래픽 일시 정지 권장 (`qt-trader`, `qt-ops-api`)
3. 운영 `DATABASE_URL` 확인

## 적용 절차

1. 백업

```bash
pg_dump -Fc "$DATABASE_URL" > backup_before_v3_schema_sync_2026-03-08.dump
```

2. 실행 전 빠른 확인

```sql
SELECT version();
SELECT current_database(), current_user;
```

3. 스키마 싱크 SQL 실행

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/sql/v3_postgres_schema_sync_2026-03-08.sql
```

4. 적용 후 검증

```sql
-- user_id / key_version 누락 여부
SELECT COUNT(*) AS null_orders_user_id FROM orders WHERE user_id IS NULL;
SELECT COUNT(*) AS null_positions_user_id FROM positions WHERE user_id IS NULL;
SELECT COUNT(*) AS null_daily_equity_user_id FROM daily_equity WHERE user_id IS NULL;
SELECT COUNT(*) AS null_paper_wallet_user_id FROM paper_wallet WHERE user_id IS NULL;
SELECT COUNT(*) AS missing_key_version
FROM user_exchange_credentials
WHERE key_version IS NULL OR BTRIM(key_version) = '';

-- 핵심 제약 생성 여부
SELECT conname
FROM pg_constraint
WHERE conname IN (
  'uq_orders_user_client_order_id',
  'uq_daily_equity_user_date',
  'uq_paper_wallet_user',
  'uq_user_exchange_credentials_user_exchange',
  'uq_user_api_budget_user_scope'
)
ORDER BY conname;

-- positions PK 확인
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'positions'::regclass AND contype = 'p';
```

5. 앱 재기동 후 앱 레벨 확인

- `/api/me/credentials/upbit`에서 `has_credentials`, `is_valid` 확인
- 멀티유저 실행 경로에서 사용자별 주문/상태 조회 확인

## 이 SQL이 맞추는 범위

- `orders`: V3 관련 누락 컬럼(`user_id`, `intent`, `retry_count`, 오류/응답 컬럼) 보강
- `fills`: `is_applied` 보강
- `user_exchange_credentials`: `key_version` 보강 및 기본값/인덱스
- `positions`: `user_id` 보강 + PK를 `(user_id, market)`로 정합
- `daily_equity`, `paper_wallet`: `user_id` 보강 + 사용자 스코프 unique 제약
- `daily_equity`: `start_realized_pnl` 보강
- V3 부가 테이블 생성:
  - `audit_log`
  - `user_risk_guard`
  - `user_api_budget`
  - `user_bot_config`
  - `user_bot_runtime`
  - `timeframe_config`

## 주의사항

- 기존 데이터 품질 이슈(중복, 잘못된 NULL)가 있으면 스크립트가 `RAISE EXCEPTION`으로 즉시 중단되도록 되어 있다.
- 자동 삭제 로직은 포함하지 않았다. 중복 데이터는 수동 확인/정리 후 재실행해야 한다.
- `ON_ERROR_STOP=1` 기준으로 실패 즉시 중단되므로, 에러 메시지 기준으로 데이터 정리 후 재실행한다.

## 롤백

가장 안전한 롤백은 사전 백업 복원이다.

```bash
pg_restore -d "$DATABASE_URL" --clean --if-exists backup_before_v3_schema_sync_2026-03-08.dump
```
