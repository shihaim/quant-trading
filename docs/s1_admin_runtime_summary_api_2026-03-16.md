# S1 Admin Runtime Summary API (2026-03-16)

## Purpose
- Provide one-screen admin visibility for per-user runtime, credential, budget, halt, and recent activity state.
- Keep strict multi-user scoping and admin boundary intact.

## Endpoint
- `GET /api/admin/users/runtime-summary`
- Query:
  - `limit` (optional, default `200`, max `1000`)
- Auth:
  - admin token required
  - non-admin returns `403 forbidden`

## Response Shape (high-level)
- `generated_at_utc`, `generated_at_kst`
- `count`
- `items[]` with:
  - user identity: `user_id`, `email`, `display_name`, `role`, `is_active`
  - bot/runtime: `bot.*`, `runtime.*`
  - credential status: `credential.has_credentials`, `credential.is_valid`, `credential.updated_at_utc`
  - budget status: `budget.request_count`, `budget.blocked_count`, `budget.remaining`, `budget.is_limited`
  - halt status: `halt.is_halted`, `halt.reason`, `halt.message`
  - activity timestamps: `recent_order_at_utc`, `recent_audit_at_utc`, `recent_error_at_utc`, `recent_action_at_utc`
  - flags: `is_budget_blocked`, `is_halted`, `is_credential_invalid`, `is_critical`
- Sorting: critical users first (`budget blocked -> halted -> credential invalid -> recent action`)

## Invariant Notes
- No cross-user mixing: every row is computed by `user_id` scope.
- No `/api/me/*` owner bridge behavior is introduced.
- Admin boundary remains enforced on `/api/admin/*`.
