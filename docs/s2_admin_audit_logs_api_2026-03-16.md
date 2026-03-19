# S2 Admin Audit Logs API/UI (2026-03-16)

## Story
- `S2 (P0) Audit 조회 API/UI 추가`

## Endpoint
- `GET /api/admin/audit/logs`
- Admin token required (`/api/admin/*` boundary).

## Query Params
- `actor_user_id`
- `target_user_id`
- `action`
- `target_type`
- `result` (`all|success|failure`)
- `from`, `to` (ISO-8601 UTC)
- `limit` (default `50`, max `200`)
- `offset` (default `0`)

## Guardrails
- Default time window is bounded to last 7 days when `from/to` omitted.
- Max date range is 31 days (`400 invalid_date_range` when exceeded).
- Pagination is latest-first (`created_at desc, id desc`), with `has_more`.
- Metadata is redacted for sensitive keys (`password`, `secret`, `token`, `authorization`, `access_key`, `secret_key`, `credential`).

## DB/Index Review
- Existing indexes already cover core filters:
  - `ix_audit_log_actor_user_id`
  - `ix_audit_log_action`
  - `ix_audit_log_target_type`
  - `ix_audit_log_target_id`
  - `ix_audit_log_created_at`

## UI
- `/admin/ops` includes Audit Logs viewer:
  - filter controls
  - pagination controls
  - metadata expansion panel
  - redacted metadata display only
