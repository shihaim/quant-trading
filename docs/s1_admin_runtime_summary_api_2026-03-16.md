# S1 관리자 런타임 요약 API (2026-03-16)

## 목적

- 관리자에게 사용자별 런타임, 자격증명, API 예산, 중지 상태, 최근 활동을 한 화면에서 볼 수 있는 정보를 제공한다.
- 엄격한 멀티유저 scope와 admin 경계를 유지한다.

## 엔드포인트 경로

- `GET /api/admin/users/runtime-summary`
- 조회 parameter:
  - `limit` (선택, 기본 `200`, 최대 `1000`)
- 인증:
  - admin token 필수
  - non-admin은 `403 forbidden` 반환

## 응답 형태 (상위 수준)

- `generated_at_utc`, `generated_at_kst`
- `count`
- `items[]` 구성:
  - 사용자 식별 정보: `user_id`, `email`, `display_name`, `role`, `is_active`
  - bot/runtime: `bot.*`, `runtime.*`
  - 자격증명 상태: `credential.has_credentials`, `credential.is_valid`, `credential.updated_at_utc`
  - 예산 상태: `budget.request_count`, `budget.blocked_count`, `budget.remaining`, `budget.is_limited`
  - 중지 상태: `halt.is_halted`, `halt.reason`, `halt.message`
  - 활동 시각: `recent_order_at_utc`, `recent_audit_at_utc`, `recent_error_at_utc`, `recent_action_at_utc`
  - flag: `is_budget_blocked`, `is_halted`, `is_credential_invalid`, `is_critical`
- 정렬: 위험 사용자를 먼저 표시한다. 우선순위는 예산 차단, 중지, 자격증명 오류, 최근 활동 순이다.

## 불변식 메모

- 사용자 간 데이터 혼합 금지: 모든 행은 `user_id` scope 기준으로 계산한다.
- `/api/me/*` owner bridge 동작을 새로 만들지 않는다.
- `/api/admin/*`의 admin 경계를 유지한다.
