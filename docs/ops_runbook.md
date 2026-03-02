# Ops Runbook

- 작성일: 2026-02-26
- 최종 수정: 2026-03-02
- 대상: 운영/개발 공용

## 1) 관련 문서와 현재 운영 전제

- 인프라 변경 상세: `docs/infra_handover_2026-02-28.md`
- PC 간 PostgreSQL 마이그레이션 런북: `docs/cross_pc_postgres_migration_runbook_2026-03-02.md`
- 현재 운영 기본 경로는 GitHub Actions + self-hosted runner + Docker Compose
- Compose 기본 DB는 PostgreSQL
- 로컬 CLI 직접 실행 시 `DATABASE_URL`이 없으면 여전히 `sqlite:///./trading.db`로 fallback 가능

현재 운영 서비스:

- `qt-caddy`
- `qt-web`
- `qt-ops-api`
- `qt-trader`
- `qt-postgres`

## 2) 배포 후 기본 확인 절차

배포 트리거는 `main` 브랜치 push다. 배포 직후 아래 순서로 확인한다.

1. GitHub Actions `deploy_local` 성공 여부 확인
2. 컨테이너 기동 상태 확인
3. PostgreSQL bootstrap 상태 확인
4. 웹/API 라우팅 확인

운영 호스트에서 확인할 대표 명령:

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

```powershell
docker logs qt-ops-api --tail 200
docker logs qt-trader --tail 200
docker logs qt-web --tail 200
```

```powershell
docker exec qt-postgres pg_isready -U trader -d trading
docker exec qt-postgres psql -U trader -d trading -c "\dt"
```

변경 반영이 의심될 때 추가 확인:

```powershell
docker context show
docker inspect qt-postgres --format "{{json .NetworkSettings.Ports}}"
docker compose --env-file .env.runtime config
```

설정이 실제 컨테이너에 반영되지 않았으면 아래 순서로 재생성한다.

```powershell
docker compose --env-file .env.runtime down
docker compose --env-file .env.runtime up -d --force-recreate
```

라우팅 확인 포인트:

- 외부 대시보드 진입은 `https://qt-dashboard.local` (Caddy `443`, `tls internal`)
- 호스트 OS에서 `qt-dashboard.local -> 127.0.0.1` hosts 설정 및 Caddy 로컬 CA 신뢰 여부 확인
- `/api/logs*`는 `web`으로 전달
- 나머지 `/api/*`는 `ops-api`로 전달
- 그 외 요청은 `web`으로 전달

## 3) 자동 HALT 발생 시 확인 순서

1. 로그에서 HALT 사유 확인
- `scheduler_halt ... reason=daily_loss_limit`
- `scheduler_auto_halt_by_slippage ...`

2. `bot_config` 상태 확인

```sql
SELECT id, is_enabled, daily_loss_basis, max_daily_loss_pct, updated_at
FROM bot_config
WHERE id = 1;
```

3. 당일 손익 스냅샷 확인

```sql
SELECT *
FROM daily_equity
ORDER BY date_utc DESC
LIMIT 3;
```

4. 필요 시 수동 재개

```sql
UPDATE bot_config
SET is_enabled = 1,
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1;
```

5. 재개 전 확인
- 최근 `trade_metrics`에서 슬리피지 급증 여부 확인
- `TRADE_MODE`가 의도한 운영 모드인지 확인
- 복구 직후에는 필요 시 `SHADOW` 또는 `TEST`로 선검증

## 4) ERROR_NEEDS_REVIEW 발생 시

1. 대상 주문 조회

```sql
SELECT id, market, side, state, error_class, last_error, client_order_id, upbit_identifier, upbit_uuid, updated_at
FROM orders
WHERE state = 'ERROR_NEEDS_REVIEW'
ORDER BY updated_at DESC
LIMIT 50;
```

2. 체결 반영 누락 여부 확인

```sql
SELECT f.*
FROM fills f
JOIN orders o ON o.id = f.order_id
WHERE o.state = 'ERROR_NEEDS_REVIEW'
ORDER BY f.executed_at DESC;
```

3. `exchange_response_raw` 확인 후 재시도, 취소, 수동 정리 중 하나로 처리

4. 조치 후 확인
- 동일 `client_order_id`가 중복 제출되지 않았는지 확인
- `fills.is_applied`가 정상 반영되었는지 확인
- 거래소 상태와 로컬 `orders.state`가 다시 일치하는지 확인

## 5) 인증(Auth) 오류(키 권한, IP) 발생 시

1. 로그에서 오류 코드 확인
- 인증 실패(401/403)
- 권한 부족(scope)
- IP 화이트리스트 불일치

2. 점검 항목
- 배포에 사용된 `.env.runtime`의 `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY`
- 업비트 API 키 권한(주문 조회, 주문, 자산 조회)
- 허용 IP 등록 여부
- 시스템 시간 동기화(NTP)

3. 복구 후 점검
- `TRADE_MODE=TEST` 또는 `SHADOW`로 선검증
- 정상 확인 후 REAL 재개

## 6) 미체결 주문 누적 시

1. 누적 상태 확인

```sql
SELECT id, market, side, state, requested_price, requested_volume, upbit_uuid, updated_at
FROM orders
WHERE state IN ('NEW','SENT','OPEN','PARTIAL','WAIT')
ORDER BY updated_at DESC;
```

2. 정책 점검
- `fill_timeout_sec_*`
- `max_reprice_attempts_*`
- `reprice_step_bps`
- OPEN 충돌 정책 로그(반대 방향 선취소) 확인

3. 필요 시 취소 실행
- 앱 내부 `cancel_open_orders` 흐름 사용 권장
- 수동 취소 시 거래소와 로컬 상태 동기화 여부를 함께 확인

4. 반복 발생 시 추가 확인
- 최근 `ops-api`, `trader` 재기동 여부
- 거래소 응답 지연 또는 rate limit 여부
- 특정 마켓만 집중 발생하는지 여부

## 7) PostgreSQL 운영 점검

현재 Compose 기본 DB는 PostgreSQL이며, 빈 볼륨에서도 앱이 부팅 시 스키마를 생성하는 구조다.

1. 기본 헬스 확인

```powershell
docker exec qt-postgres pg_isready -U trader -d trading
```

2. 테이블 생성 여부 확인

```powershell
docker exec qt-postgres psql -U trader -d trading -c "\dt"
```

3. 주요 테이블 확인

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

4. 초기 bootstrap 이상 징후
- `qt-ops-api` 또는 `qt-trader`가 시작 직후 종료됨
- `\dt` 결과가 비어 있음
- `DATABASE_URL` 오설정
- `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD` 불일치

5. 장애 시 우선 확인 로그

```powershell
docker logs qt-postgres --tail 200
docker logs qt-ops-api --tail 200
docker logs qt-trader --tail 200
```

## 8) DB 백업, 복원, 롤백

### 8.1 PostgreSQL (현재 기본 운영 경로)

1. 백업
- 운영 중에도 논리 백업 가능
- 권장: `pg_dump` 사용

```powershell
docker exec qt-postgres pg_dump -U trader -d trading > trading-YYYYMMDD-HHMM.sql
```

2. 복원
- 가능하면 `qt-ops-api`, `qt-trader` 중지 후 수행
- 대상 DB 초기화 후 `psql`로 복원

```powershell
Get-Content .\trading-YYYYMMDD-HHMM.sql | docker exec -i qt-postgres psql -U trader -d trading
```

3. 롤백 원칙
- 코드 롤백과 DB 복원을 한 세트로 수행
- 롤백 후 첫 구동은 `SHADOW` 또는 `TEST`로 검증
- 복원 직후 `\dt` 및 핵심 테이블 row 수 확인

### 8.2 SQLite (로컬 CLI fallback)

1. 백업
- 앱 중지 후 `trading.db` 파일 복사
- 예: `trading-YYYYMMDD-HHMM.db`

2. 복원
- 앱 중지
- 백업 파일을 `trading.db`로 교체
- 앱 재시작 후 마이그레이션 로그 확인

주의: 현재 운영 표준은 PostgreSQL이며, SQLite는 로컬 개발/임시 실행 fallback 용도로만 본다.

## 9) 일상 운영 체크리스트

- 최근 24시간 HALT, ERROR 이벤트 유무
- `trade_metrics` 슬리피지 분포 추이
- OPEN 주문 누적 여부
- `bot_config` 파라미터 변경 이력
- `qt-postgres` health 상태
- 배포 이후 `qt-ops-api`, `qt-trader` 재시작 루프 여부
- 필요 시 `docker image prune -f` 이후 디스크 사용량 점검
