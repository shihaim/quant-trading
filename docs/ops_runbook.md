# Ops Runbook

- 작성일: 2026-02-26
- 대상: 운영/개발 공용

## 1) 자동 HALT 발생 시 확인 순서

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

## 2) ERROR_NEEDS_REVIEW 발생 시

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

## 3) 인증(Auth) 오류(키 권한, IP) 발생 시

1. 로그에서 오류 코드 확인
- 인증 실패(401/403)
- 권한 부족(scope)
- IP 화이트리스트 불일치

2. 점검 항목
- `.env`의 `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY`
- 업비트 API 키 권한(주문 조회, 주문, 자산 조회)
- 허용 IP 등록 여부
- 시스템 시간 동기화(NTP)

3. 복구 후 점검
- `TRADE_MODE=TEST` 또는 `SHADOW`로 선검증
- 정상 확인 후 REAL 재개

## 4) 미체결 주문 누적 시

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

## 5) DB 백업, 복원, 롤백

1. 백업
- 앱 중지 후 `trading.db` 파일 복사
- 예: `trading-YYYYMMDD-HHMM.db`

2. 복원
- 앱 중지
- 백업 파일을 `trading.db`로 교체
- 앱 재시작 후 마이그레이션 로그 확인

3. 롤백 원칙
- 코드 롤백과 DB 복원을 한 세트로 수행
- 롤백 후 첫 구동은 `SHADOW` 또는 `TEST`로 검증

## 6) 일상 운영 체크리스트

- 최근 24시간 HALT, ERROR 이벤트 유무
- `trade_metrics` 슬리피지 분포 추이
- OPEN 주문 누적 여부
- `bot_config` 파라미터 변경 이력
