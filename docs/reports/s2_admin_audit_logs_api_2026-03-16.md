# S2 관리자 감사 로그 API/UI (2026-03-16)

## 스토리 식별자

- `S2 (P0) Audit 조회 API/UI 추가`

## 엔드포인트 경로

- `GET /api/admin/audit/logs`
- admin token 필수 (`/api/admin/*` 경계)

## 조회 parameter

- `actor_user_id`
- `target_user_id`
- `action`
- `target_type`
- `result` (`all|success|failure`)
- `from`, `to` (ISO-8601 UTC)
- `limit` (기본 `50`, 최대 `200`)
- `offset` (기본 `0`)

## 보호 기준

- `from/to`가 없으면 기본 조회 기간은 최근 7일로 제한한다.
- 최대 조회 기간은 31일이며, 초과 시 `400 invalid_date_range`를 반환한다.
- pagination은 최신순(`created_at desc, id desc`)이며 `has_more`를 포함한다.
- 민감 key(`password`, `secret`, `token`, `authorization`, `access_key`, `secret_key`, `credential`)는 metadata에서 redaction 처리한다.

## DB/Index 검토

- 기존 index가 핵심 filter를 지원한다:
  - `ix_audit_log_actor_user_id`
  - `ix_audit_log_action`
  - `ix_audit_log_target_type`
  - `ix_audit_log_target_id`
  - `ix_audit_log_created_at`

## UI 구성

- `/admin/ops`에는 감사 로그 viewer가 포함된다:
  - filter control
  - pagination control
  - metadata 확장 panel
  - redaction 처리된 metadata 표시
