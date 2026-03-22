# S6 order_attempts 정합성 하드닝 2026-03-22

- story_id: S6
- scope: latest-attempt 해석 공용화, 정합성 점검 스크립트 추가

## 이번 반영

1. `next_attempt_no` 계산 로직을 공용화했습니다.
2. `latest attempt` 선택 로직을 공용화했습니다.
3. `orders` 요약 컬럼과 `latest attempt` 간 드리프트를 점검하는 스크립트를 추가했습니다.

## 코드 변경 요약

- 신규 모듈: `trader/trading/order_attempts.py`
  - `next_attempt_no_for_order(session, order_id)`
  - `latest_attempt_from_rows(attempts)`
  - `load_latest_attempt_for_order(session, order_id, upbit_uuid, upbit_identifier)`
- 적용 경로:
  - `trader/trading/execution.py`
  - `trader/trading/reconcile.py`
  - `trader/ops/dto.py`

## 점검 스크립트

- 파일: `scripts/check_order_attempts_consistency.py`
- 점검 항목:
  - `order_attempts.upbit_identifier` 중복
  - `order_attempts.upbit_uuid` 중복
  - `orders` 요약 필드와 latest attempt 필드 간 불일치(drift)

예시:

```powershell
python -m scripts.check_order_attempts_consistency --max-items 200
python -m scripts.check_order_attempts_consistency --json-output logs/order_attempts_consistency.json
python -m scripts.check_order_attempts_consistency --fail-on-issues
```

## 후속 권장

1. 운영 데이터에서 중복/드리프트 0건 확인 후 unique 제약 적용 여부 결정
2. 제약 적용 전 클린업 SQL과 롤백 절차 문서화
