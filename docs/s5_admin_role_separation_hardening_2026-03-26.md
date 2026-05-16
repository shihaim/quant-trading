# S5 후속: 관리자 role 분리 강화 (2026-03-26)

## 스토리 식별자

- Story ID: `S5` 후속 (`Admin 권한 분리/하드닝`)
- 범위 날짜: `2026-03-26`

## 목표

- admin role source를 env allowlist 전용 방식에서 DB 기반 role로 이전한다.
- 명시적인 target-user admin read 계약을 강제한다.
- legacy admin read alias의 owner 대체 해석 의존성을 제거한다.
- role 변경 시 기존 session을 즉시 무효화하는 정책을 정의한다.

## 보존한 불변식

1. 사용자 간 데이터 혼합 금지.
2. `/api/me/*` owner bridge 재도입 금지.
3. admin/non-admin 경계 유지.
4. session revoke는 계속 `users.token_version`을 사용한다.

## Backend 변경

1. DB 기반 admin role
- model과 lightweight migration 경로에 `users.is_admin` column을 추가했다.
- `AdminRoleResolver`(`trader/auth/roles.py`)를 추가했다.
- 최신 F2 정리 이후 resolver 전략: `users.is_admin` DB role만 사용한다. env allowlist 기반 권한 판정은 제거했다.

2. Role 변경 API와 session lifecycle
- `POST /api/admin/users/{user_id}/role` 추가.
- 허용 payload:
  - `{"role":"admin"}` 또는 `{"role":"member"}`
  - `{"is_admin": true|false}`
- Role 변경 시:
  - `users.is_admin` 갱신
  - `users.token_version` 증가
  - 기존 token은 `401 session_revoked`로 무효화

3. Legacy admin alias retired 처리 (`410 legacy_endpoint_retired`)
- `GET /api/ops/summary` -> `/api/admin/users/runtime-summary`
- `GET /api/admin/summary` -> `/api/admin/users/runtime-summary`
- `GET /api/orders`와 `GET /api/admin/orders` -> `/api/admin/users/{user_id}/orders`
- `GET /api/pnl/daily`와 `GET /api/admin/pnl/daily` -> `/api/admin/users/{user_id}/pnl/daily`
- `GET /api/metrics/trade`와 `GET /api/admin/metrics/trade` -> `/api/admin/users/{user_id}/metrics/trade`
- `POST /api/ops/credentials/rotate` -> `/api/admin/credentials/rotate`

4. Owner 대체 해석 축소
- `OpsService(scope_user_id=None)`은 더 이상 owner user를 자동 해석하지 않는다.
- 사용자 scope 읽기 method는 명시적인 `scope_user_id`를 요구한다.

## Frontend 변경

1. Admin page는 더 이상 legacy summary path에 의존하지 않는다.
- `/admin/ops`에서 `OpsDashboard` embedding을 제거했다.
- Admin page는 아래 API를 사용한다:
  - runtime summary table (`/api/admin/users/runtime-summary`)
  - audit log viewer (`/api/admin/audit/logs`)

## Test

1. alias 동작 test를 `410 legacy_endpoint_retired` 기대값으로 갱신했다.
2. DB role + role 변경 revoke test를 추가했다:
- env allowlist 없이 DB 기반 admin grant 검증
- role 변경이 token version을 증가시키는지 검증
- 기존 token이 `401 session_revoked`를 받는지 검증

## Acceptance 매핑

1. `env allowlist 없이도 admin 권한 운영 가능`
- `users.is_admin`과 DB 기반 resolver 경로로 충족.

2. `admin read API target_user_id 명시 스코프`
- legacy unscoped read alias를 retire하고 `/api/admin/users/{user_id}/*`를 유지해 충족.

3. `role 변경 시 세션 동작 예측 가능`
- role 변경 endpoint 정책(`token_version` 증가 + session revoke)으로 충족.
