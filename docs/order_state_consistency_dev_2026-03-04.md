# 주문 상태 정합성 개발자 문서

- 작성일: 2026-03-04
- 대상: 개발자
- 범위: 주문 상태 정합성 개선 및 `duplicate identifier` 방지를 위한 `order_attempts` 도입

## 1) 변경 요약

이번 변경의 핵심은 "논리 주문"과 "거래소 제출 시도"를 분리한 것입니다.

기존에는 `orders` 한 행에 아래 정보가 함께 들어 있었습니다.

- 논리 주문 의도
- 최신 거래소 identifier
- 최신 거래소 UUID
- 가장 최근 제출 경로의 retry 및 오류 상태

이 구조에서는 재호가(reprice)나 복구(recover)가 발생할 때마다 시도 단위 정보가 계속 덮어써졌고, 아래 문제의 원인 추적이 어려웠습니다.

- `duplicate identifier`
- 제출 타임아웃 후 복구
- `sync` 또는 `cancel` 이후의 오래된 `orders.state`

현재 구조는 아래처럼 나뉩니다.

- `orders`: 논리 주문의 요약 상태
- `order_attempts`: 제출 및 복구 시도 이력

## 2) 현재 코드에 반영된 설계 규칙

### 2.1 `attempt_no`는 주문별 단조 증가 시퀀스

`attempt_no`는 단순 루프 번호가 아닙니다.

항상 아래 규칙으로 발급합니다.

```python
MAX(order_attempts.attempt_no) + 1
```

이 규칙은 다음 두 경로에서 동일하게 사용합니다.

- `execution.py`
- `reconcile.py`

이렇게 해야 `UNIQUE(order_id, attempt_no)`와 충돌하지 않고, "최신 attempt" 판정도 안정적으로 유지됩니다.

### 2.2 거래소 식별자는 attempt 소속

`upbit_identifier`와 `upbit_uuid`는 우선적으로 attempt 단위 필드입니다.

다만 기존 코드와의 호환성을 위해 아래 `orders` 컬럼에도 최신 attempt 값을 미러링합니다.

- `orders.upbit_identifier`
- `orders.upbit_uuid`

### 2.3 `client_order_id`는 논리 주문 키로 유지

정합화 중 거래소에는 있는데 로컬에는 없는 주문을 새로 만들 때는 아래 규칙을 사용합니다.

- `client_order_id = upbit-<uuid>`

즉, `client_order_id`를 거래소 identifier로 직접 재사용하지 않습니다.

### 2.4 `upbit_identifier`, `upbit_uuid`에 DB unique 제약은 아직 없음

현재 단계에서는 두 컬럼에 DB unique 제약을 걸지 않았습니다.

이유:

- 기존 데이터에 중복이 있을 가능성이 있음
- 강한 제약을 바로 넣으면 마이그레이션 실패 위험이 큼

대신 제출 경로에서 새 `upbit_identifier`를 예약할 때, 기존 `order_attempts`를 조회해서 중복 사용을 막습니다.

## 3) 변경된 파일과 역할

### 3.1 데이터 모델 및 DB 초기화

- `trader/data/models.py`
- `trader/data/db.py`

반영 내용:

- `OrderAttempt` 모델 추가
- `Order.attempts` 관계 추가
- 기존 `orders` 데이터용 백필 로직 추가
- 백필 시 기본값:
  - `attempt_no = 1`
  - `submit_reason = 'INITIAL'`

### 3.2 실행 경로

- `trader/trading/execution.py`

반영 내용:

- `_begin_attempt()` 추가
- `_next_attempt_no()` 추가
- `_reserve_unique_upbit_identifier()` 추가
- submit/recover 결과를 현재 `OrderAttempt`에 먼저 기록
- `sync_order()`와 `cancel_order()`도 최신 attempt를 함께 갱신
- `orders`는 계속 요약 상태를 미러링해서 유지

### 3.3 정합화 경로

- `trader/trading/reconcile.py`

반영 내용:

- `OrderAttempt.upbit_uuid`로 1차 매칭
- `OrderAttempt.upbit_identifier`로 2차 매칭
- 로컬 주문이 없으면 새 `Order`와 `RECOVER` attempt 생성
- 로그 카운터 분리:
  - `created_orders`
  - `created_attempts`
  - `updated_attempts`

### 3.4 운영 조회 경로

- `trader/ops/dto.py`
- `trader/ops/service.py`

반영 내용:

- 운영 조회는 기존 `orders` 컬럼보다 최신 attempt를 우선 사용
- 주문 목록 조회 시 `Order.attempts`를 eager load
- DTO 응답에 아래 필드 추가
  - `attempt_no`
  - `attempt_submit_reason`

### 3.5 마이그레이션 도구

- `trader/migration/contracts.py`
- `trader/migration/merge.py`

반영 내용:

- `order_attempts`를 마이그레이션 대상 primary table에 추가
- merge 매칭 순서:
  1. `(mapped_order_id, attempt_no)`
  2. `upbit_uuid`
  3. `upbit_identifier`
- `submit_reason`가 달라도 기본적으로 hard skip하지 않고 warning 기반으로 처리

### 3.6 테스트

- `tests/test_execution_and_paper.py`
- `tests/test_ops_service.py`
- `tests/test_migration_conflicts.py`
- `tests/test_reconcile_service.py`

## 4) 하위 호환 전략

이번 변경은 단계적 전환을 전제로 합니다.

기존 읽기 경로를 깨지 않기 위해 최신 attempt 값을 다시 `orders`로 미러링합니다.

- `requested_price`
- `requested_volume`
- `upbit_identifier`
- `upbit_uuid`
- `state`
- `retry_count`
- `error_class`
- `last_error`
- `exchange_response_raw`

즉, 새로운 소스 오브 트루스는 `order_attempts`이지만, 기존 소비 경로는 당분간 `orders`만 읽어도 동작하도록 유지합니다.

## 5) 검증 결과

타깃 테스트:

```powershell
python -m pytest -q tests/test_execution_and_paper.py tests/test_ops_service.py tests/test_migration_conflicts.py tests/test_reconcile_service.py
```

결과:

- `19 passed`

전체 테스트:

```powershell
python -m pytest -q
```

결과:

- `62 passed`

## 6) 현재 남아 있는 주의사항

### 6.1 `upbit_identifier` 고유성은 코드에서만 소프트하게 보장

현재는 제출 시점 조회로 중복 사용을 막고 있지만, DB가 직접 unique 제약으로 막아주지는 않습니다.

운영 점검 쿼리는 아래 문서에 정리했습니다.

- `docs/order_attempts_ops_checks_2026-03-04.md`

### 6.2 앞으로 `orders`만 직접 갱신하면 요약 상태가 다시 어긋날 수 있음

새로운 쓰기 경로에서는 `OrderAttempt`를 기준으로 업데이트해야 합니다.

특히 아래 값을 `orders`에만 쓰고 attempt를 갱신하지 않으면 운영 조회 결과가 틀어질 수 있습니다.

- `orders.state`
- `orders.error_class`
- `orders.upbit_uuid`

### 6.3 기존 데이터의 첫 attempt는 "합성(synthetic) 행"

백필된 첫 행은 운영 호환성을 위한 placeholder입니다.

따라서 롤아웃 이전 주문에 대해서는:

- `attempt_no = 1`이 실제 첫 거래소 제출을 뜻하지 않을 수 있음
- `submit_reason = 'INITIAL'`도 추정값이 아닌 호환용 기본값임

### 6.4 `initialize_database()` 단독 호출만으로는 스키마가 안 생길 수 있음

운영 DB 반영 과정에서 확인한 주의사항이다.

`initialize_database()`는 내부에서 `Base.metadata.create_all()`을 호출하지만, 실행 전에 모델 모듈이 import되지 않으면 `Base.metadata`가 비어 있을 수 있다.

이 경우 함수가 정상 종료돼도 원하는 테이블이 실제로 생성되지 않을 수 있다.

따라서 별도 스크립트나 단발성 커맨드로 스키마를 반영할 때는 아래 순서를 지키는 것이 안전하다.

1. 먼저 `trader.data.models`를 import한다.
2. 그 다음 `initialize_database()`를 호출한다.

이 주의사항은 `order_attempts`뿐 아니라, 향후 다른 신규 테이블 롤아웃에도 동일하게 적용된다.

## 7) 다음 권장 작업

1. 중복 `upbit_identifier` 탐지 쿼리를 주기 점검 또는 대시보드 카드로 노출
2. 운영 데이터가 정리되면 `order_attempts.upbit_identifier`, `order_attempts.upbit_uuid`에 DB unique 제약 검토
3. "최신 attempt 선택" 로직을 공용 helper로 묶어서 모듈별 드리프트 방지
4. `docs/ops_runbook.md`의 `duplicate identifier` 대응 절차와 실제 운영 절차가 계속 일치하는지 유지 보수

## 8) 이후 개발 시 체크리스트

- 새 submit 경로를 추가할 때는 항상 먼저 `OrderAttempt`를 생성할 것
- 거래소 상태 반영 시에는 관련 attempt를 갱신한 뒤 `orders`로 미러링할 것
- `client_order_id`를 거래소 identifier처럼 재사용하지 말 것
- 로컬 루프 카운터를 `attempt_no`로 쓰지 말 것
- 새 운영 조회를 추가할 때는 최신 attempt를 우선 표시 기준으로 사용할 것
