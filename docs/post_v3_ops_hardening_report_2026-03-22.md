# Post-V3 Ops Hardening 작업 정리 (347f67c..HEAD)

- 작성일: 2026-03-22
- 대상: 기획, 개발, 운영
- 기준 범위: `347f67c93f401133189aa0da8c71d3c9d1bfa006` 이후 `HEAD(c3e47ae)`까지
- 기준 티켓: `2026-03-10 Post-V3 Ops Hardening Backlog (Story-Task-Sub-task)`
  - URL: `https://www.notion.so/31f899b6d7dc81cb897deda764f70769`

## 1) 한눈에 보는 결과

이번 구간은 Notion 배치 기준으로 **B1(P0) + B2(P1) + B3(P2)가 모두 완료**된 상태입니다.

- overall: `completed`
- B1(S1~S3): `completed`
- B2(S4~S6): `completed`
- B3(S7): `completed`

코드 변경 규모:

- `45 files changed, 1893 insertions(+), 75 deletions(-)`
- 주요 커밋 4건:
  - `f0f90ff` (릴리즈 게이트/자격증명 감사 스크립트)
  - `6cfb7c6` (context anchor 최신화)
  - `9c3c26b` (S4~S6 하드닝)
  - `c3e47ae` (S7 리스크 정책 확장)

## 2) Story 기준 완료 항목 (Notion 매핑)

### S1 (P0) 사용자별 운영 상태 가시화

- Admin runtime summary API + 운영 테이블 UI 반영
- blocked/halted/credential-invalid 사용자 식별 가능
- non-admin 접근 차단 정책 유지

### S2 (P0) Audit 조회 API/UI

- admin audit 조회 API + 필터/페이징 + UI 반영
- 최신순 조회 및 운영 조사 흐름 개선
- 권한 경계 유지

### S3 (P0) 릴리즈 게이트 자동화

- 단일 실행 경로로 점검 결과 산출물 생성
- `scripts/run_release_gate.py`
- `scripts/audit_upbit_credential_coverage.py`
- 실패 원인 확인 가능한 리포트 형식 정리

### S4 (P1) Legacy Bot API 정리

- `POST /api/bot/enable|disable`를 retired 응답(`410 legacy_endpoint_retired`)으로 고정
- 공식 계약을 `/api/me/bot/*`로 단일화
- 문서/테스트/운영 가이드 정렬

### S5 (P1) 인증/세션 수명주기 하드닝

- `users.token_version` 기반 세션 강제 만료 경로 반영
- 관리자 강제 세션 종료 API 추가:
  - `POST /api/admin/users/{user_id}/sessions/invalidate`
- `expired_token` / `session_revoked` 분기 처리로 UX 일관성 강화

### S6 (P1) order_attempts 정합성 하드닝

- latest-attempt / next-attempt 계산 로직 공용화
- 중복/드리프트 점검 경로 보강
- 운영 제약 적용 전 점검/런북 정리

### S7 (P2) 리스크 정책 확장

- 신규 정책 키 반영:
  - `max_weekly_loss_pct`, `max_monthly_loss_pct`
  - `cooldown_hours_on_halt`
  - `max_new_orders_per_day`, `max_orders_per_week`
  - `min_edge_pct`
- 신규 중단 사유 노출:
  - `weekly_loss_limit`, `monthly_loss_limit`
  - `new_orders_daily_limit`, `orders_weekly_limit`
  - `cooldown_active`
- `/api/me`, admin/ops 응답, 대시보드에서 halt reason/cooldown 관측 가능

## 3) 기획/운영 관점 변화

1. 운영자가 한 화면에서 위험 사용자(중단/차단/자격증명 문제)를 빠르게 식별할 수 있습니다.
2. 레거시 bot 제어 경로가 사실상 종료되어 계약 혼선이 줄었습니다.
3. 세션 강제 종료가 가능해 보안 이벤트 대응이 단순해졌습니다.
4. 일간 중심 리스크에서 주간/월간/주문 빈도/재진입 제어까지 정책 범위가 확장됐습니다.

## 4) 개발 관점 변화

- 인증/세션:
  - `trader/auth/guard.py`, `trader/auth/tokens.py`, `trader/api/ops_http.py`
- 리스크/스케줄러:
  - `trader/trading/risk.py`, `trader/trading/scheduler.py`, `trader/config/config_repo.py`
- 데이터/스키마:
  - `trader/data/models.py`, `trader/data/db.py`, `trader/migration/v3_user_scope.py`
- 프론트:
  - `apps/web/components/ops-dashboard.tsx`, `apps/web/app/control/page.tsx`, `apps/web/components/admin-users-runtime-table.tsx`

## 5) 검증 요약

- B2 반영 시 테스트 결과:
  - `tests/test_auth_tokens.py tests/test_auth_guard.py tests/test_ops_http_auth.py` -> `17 passed`
  - `tests/test_db_bootstrap.py tests/test_auth_service.py tests/test_order_attempts_utils.py tests/test_execution_and_paper.py tests/test_reconcile_service.py tests/test_ops_service.py` -> `30 passed`
- B3 반영 시 확장 테스트 범위:
  - `tests/test_risk.py`
  - `tests/test_scheduler_pnl.py`
  - `tests/test_scheduler_min_order_gate.py`
  - `tests/test_config_repo.py`
  - `tests/test_db_bootstrap.py`
  - `tests/test_me_read_service.py`

## 6) 관련 문서

- [S5 세션 하드닝](./s5_auth_session_lifecycle_hardening_2026-03-22.md)
- [S6 정합성 하드닝](./s6_order_attempts_consistency_hardening_2026-03-22.md)
- [S6 운영 런북](./order_attempts_unique_constraints_runbook_2026-03-22.md)
- [S7 리스크 확장](./s7_risk_policy_expansion_2026-03-22.md)
- [P5 개발 인수인계](./p5_dev_handover_2026-03-06.md)
- [P5 제품 보고서](./p5_product_report_2026-03-06.md)

## 7) 현재 결론

Notion backlog 기준으로 이번 배치의 필수 Story(S1~S7)는 모두 완료 상태입니다.
추가 개선 항목은 별도 트랙(후속 제안/운영 개선)으로 관리하는 것이 적절합니다.
