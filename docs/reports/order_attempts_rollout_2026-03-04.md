# order_attempts 운영 DB 반영 기록

- 작성일: 2026-03-04
- 대상: 운영/개발 공용
- 목적: `order_attempts` 스키마의 실제 운영 DB 반영 이력과 검증 결과를 장기 보존

## 1) 반영 대상

- 접속 경로: `127.0.0.1:25432`
- 데이터베이스: `trading`
- 사용자: `trader`

주의:

- 이번 반영은 실제 운영 DB에 대한 스키마 변경이다.
- 이후 운영 앱 재기동 및 로그/점검 쿼리 재확인까지 완료했다.

## 2) 반영 전 백업

반영 전에 아래 dump를 생성했다.

- 파일: `prod_trading_pre_t7_20260304_141652.dump` (환경별 백업 보관 경로 기준)
- 형식: custom format (`pg_dump -Fc`)
- 크기: `44,198 bytes`

## 3) 반영 전 상태

반영 전 확인 결과:

- `orders`: 존재
- `order_attempts`: 없음
- `orders` 건수: `2`

## 4) 반영 내용

최신 코드의 DB 초기화 경로를 사용해 `order_attempts` 스키마를 반영했다.

중요한 주의사항:

- `initialize_database()`를 단독 호출하면 모델 import가 선행되지 않아 `Base.metadata.create_all()`이 원하는 테이블을 만들지 못할 수 있다.
- 실제 반영 시에는 `trader.data.models`를 먼저 import한 뒤 `initialize_database()`를 호출했다.

반영된 항목:

- `order_attempts` 테이블 생성
- 기본 인덱스 생성
  - `ix_order_attempts_order_id`
  - `ix_order_attempts_state`
  - `ix_order_attempts_upbit_identifier`
  - `ix_order_attempts_upbit_uuid`
- 기본 키 생성
  - `order_attempts_pkey`
- 유니크 제약 생성
  - `uq_order_attempt_order_attempt_no`
- 기존 `orders` 2건 기준 백필 수행

## 5) 반영 후 상태

반영 후 확인 결과:

- `orders`: 존재
- `order_attempts`: 존재
- `orders` 건수: `2`
- `order_attempts` 건수: `2`

백필된 행 요약:

- `order_id=1`, `attempt_no=1`, `submit_reason=INITIAL`, `state=CANCELED`
- `order_id=2`, `attempt_no=1`, `submit_reason=INITIAL`, `state=FILLED`

## 6) 검증 결과

### 6.1 시퀀스 무결성

아래 조건 위반 행 없음:

- `COUNT(*) <> MAX(attempt_no)`

즉, 현재 운영 DB 기준 `attempt_no` 시퀀스 무결성은 정상이다.

### 6.2 중복 식별자

아래 중복 결과 모두 없음:

- 중복 `upbit_identifier`
- 중복 `upbit_uuid`

즉, 현재 운영 DB 기준으로 즉시 보이는 식별자 충돌은 없다.

### 6.3 반영 후 운영 앱 확인

확인된 내용:

- 운영 로그에서 `order_attempts` 관련 스키마 오류 없음
- `duplicate identifier` 재발 흔적 없음
- `attempt_no`가 포함된 실제 주문 로그 확인
- 운영 점검 쿼리 재실행 결과:
  - 최신 attempt와 `orders` 요약 상태 불일치 없음
  - 최근 attempt 이력 정상

즉, 현재 확보된 범위에서는 스키마 반영 이후 운영 앱도 정상 동작으로 판단한다.

## 7) 남은 작업

이 문서 범위 기준 남은 필수 작업은 없다.

이후에는 일반 운영 점검 문서에 따라 주기 점검한다.

## 8) 관련 문서

- `docs/ops_runbook.md`
- `docs/runbooks/order_attempts_ops_checks_2026-03-04.md`
- `docs/reports/order_state_consistency_dev_2026-03-04.md`
