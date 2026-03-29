# S5 Follow-up: Admin Role Separation Hardening (2026-03-26)

## Story

- Story ID: `S5` follow-up (`Admin 권한 분리/하드닝`)
- Scope date: `2026-03-26`

## Goal

- Move admin role source from env-only allowlist to DB-backed role.
- Enforce explicit target-user admin read contracts.
- Remove owner-fallback dependency on legacy admin read aliases.
- Define role-change session behavior with immediate token invalidation.

## Invariants Preserved

1. No cross-user data mixing.
2. No owner-bridge reintroduction on `/api/me/*`.
3. Admin/non-admin boundary remains enforced.
4. Session revocation semantics continue to use `users.token_version`.

## Backend Changes

1. DB-backed admin role
- Added `users.is_admin` column in model and lightweight migration path.
- Added `AdminRoleResolver` (`trader/auth/roles.py`).
- Resolver strategy (transition): `users.is_admin` OR `OPS_API_ADMIN_EMAILS` allowlist.

2. Role-change API and session lifecycle
- Added `POST /api/admin/users/{user_id}/role`.
- Accepted payload:
  - `{"role":"admin"}` or `{"role":"member"}`
  - `{"is_admin": true|false}`
- On role change:
  - update `users.is_admin`
  - increment `users.token_version`
  - old token becomes invalid (`401 session_revoked`)

3. Legacy admin alias retirement (`410 legacy_endpoint_retired`)
- `GET /api/ops/summary` -> `/api/admin/users/runtime-summary`
- `GET /api/admin/summary` -> `/api/admin/users/runtime-summary`
- `GET /api/orders` and `GET /api/admin/orders` -> `/api/admin/users/{user_id}/orders`
- `GET /api/pnl/daily` and `GET /api/admin/pnl/daily` -> `/api/admin/users/{user_id}/pnl/daily`
- `GET /api/metrics/trade` and `GET /api/admin/metrics/trade` -> `/api/admin/users/{user_id}/metrics/trade`
- `POST /api/ops/credentials/rotate` -> `/api/admin/credentials/rotate`

4. Owner-fallback reduction
- `OpsService(scope_user_id=None)` no longer auto-resolves owner user.
- User-scoped read methods now require explicit `scope_user_id`.

## Frontend Changes

1. Admin page no longer depends on legacy summary path.
- Removed `OpsDashboard` embedding from `/admin/ops`.
- Admin page now uses:
  - runtime summary table (`/api/admin/users/runtime-summary`)
  - audit log viewer (`/api/admin/audit/logs`)

## Tests

1. Updated alias-behavior tests to expect `410 legacy_endpoint_retired`.
2. Added DB role + role-change revocation test:
- verifies DB-based admin grant without env allowlist
- verifies role change bumps token version
- verifies old token receives `401 session_revoked`

## Acceptance Mapping

1. `env allowlist 없이도 admin 권한 운영 가능`
- satisfied by `users.is_admin` + DB-based resolver path.

2. `admin read API target_user_id 명시 스코프`
- satisfied by retiring legacy unscoped read aliases and keeping `/api/admin/users/{user_id}/*`.

3. `role 변경 시 세션 동작 예측 가능`
- satisfied by role-change endpoint policy (`token_version` bump + session revocation).

