# P1 구현 보고서 (End-to-End 실계정 리허설: 초소액/통제 환경)

- 작성일: 2026-02-24
- 대상: 기획/개발 공용
- 기준 문서: `P1._end-to-end(실계정)_리허설__단_초소액통제된_환경에서.pdf`

## 1) 목적

P1의 목적은 실계정 환경에서 바로 수익을 내는 것이 아니라, 아래를 안전하게 검증하는 것이다.

- 조회/리컨실 안정성
- 주문 생애주기(주문 -> 미체결 -> 취소 -> 상태 반영)
- 통제 환경(소액, 단일 마켓, 강한 제한)에서 사고 방지

## 2) 이번 반영 범위 요약

이번 작업은 P1 문서 기준으로 우선순위 높은 초기 범위를 구현했다.

- `P1-00` 통제 프로파일의 코드 레일 반영
- `P1-01` 조회-only 스모크 리허설 실행 경로 제공
- `P1-02` 체결 없는 주문 -> 취소 E2E 실행 경로 제공

## 3) 구현 상세

### 3.1 통제 프로파일(리허설 가드레일)

- 설정 추가:
  - `ENFORCE_MARKET_ALLOWLIST` (기본 `false`)
  - `ALLOWLIST_MARKETS` (기본 `["KRW-BTC"]`)
  - `REHEARSAL_ORDER_NOTIONAL_KRW` (기본 `6000`)
- allowlist 활성화 시:
  - 허용 마켓 외 주문은 즉시 `REJECTED`
  - `error_class=VALIDATION_ERROR`로 기록

반영 파일:

- `trader/config/settings.py`
- `trader/trading/execution.py`
- `trader/trading/scheduler.py`

### 3.2 주문 취소 API 및 생애주기 검증 경로

- Upbit 취소 API 래퍼 추가:
  - `UpbitClient.cancel_order(order_uuid)`
- 실행 엔진에 취소 기능 추가:
  - `ExecutionEngine.cancel_order(order)`
  - `ExecutionEngine.cancel_open_orders(...)`

반영 파일:

- `trader/exchange/upbit_client.py`
- `trader/trading/execution.py`

### 3.3 P1 리허설 CLI 추가

새 엔트리포인트:

- `python -m trader.app.p1_rehearsal --scenario smoke --user-id <user_id>`
- `python -m trader.app.p1_rehearsal --scenario order-cancel --user-id <user_id>`

시나리오:

- `smoke`: 조회-only 리컨실 반복 점검 (accounts/open orders/reconcile)
- `order-cancel`: 원거리 지정가 주문 -> 미체결 확인 -> 취소 -> 상태 반영 확인

반영 파일:

- `trader/app/p1_rehearsal.py`

### 3.4 문서 업데이트

- P1 실행 명령과 신규 환경변수 반영

반영 파일:

- `README.md`

## 4) 테스트/검증

- 단위 테스트 추가:
  - allowlist 차단 동작 테스트
  - 취소 상태 전이(`CANCELED`) 테스트
- 전체 테스트 결과:
  - `python -m pytest -q` -> `12 passed`

반영 파일:

- `tests/test_execution_and_paper.py`

## 5) P1 체크리스트 대비 상태

### 완료

- P1-00: 리허설 통제 레일(allowlist/소액 설정) 반영
- P1-01: 조회-only 스모크 시나리오 실행 경로 제공
- P1-02: 체결 없는 주문 -> 취소 E2E 실행 경로 제공

### 진행 필요(다음 단계)

- P1-03: 초소액 1회 체결 시나리오 운영 리허설 강화
- P1-04: 강제 재시작 복구 시나리오 자동화
- P1-05: 장애 주입(Timeout/429) 실환경 리허설 자동화

## 6) 운영 가이드(권장)

- 리허설 전:
  - `TRADE_MODE=REAL` 사용 시 API 키 권한/보안 확인
  - `ENFORCE_MARKET_ALLOWLIST=true`
  - `ALLOWLIST_MARKETS=["KRW-BTC"]`
  - `REHEARSAL_ORDER_NOTIONAL_KRW=6000` 또는 더 작은 값

- 실행 순서:
  1. `smoke`로 조회 안정성 점검
  2. `order-cancel`로 주문 생애주기 점검
  3. 이후 초소액 체결 리허설(P1-03) 진행

## 7) 핵심 파일 인덱스

- `trader/config/settings.py`
- `trader/exchange/upbit_client.py`
- `trader/trading/execution.py`
- `trader/trading/scheduler.py`
- `trader/app/p1_rehearsal.py`
- `tests/test_execution_and_paper.py`
- `README.md`
