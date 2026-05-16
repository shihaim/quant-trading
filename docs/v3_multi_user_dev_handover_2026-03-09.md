# V3 멀티유저 전환 개발 인수인계 2026-03-09

- 작성일: 2026-03-09
- 대상: 백엔드, 프론트엔드, QA 엔지니어
- 범위: V3.1 ~ V3.8 완료 상태 기준 기술 인수인계

## 1) 상태 요약

- 배치 상태: `overall: completed`
- Story 목록:
  - V3.1 schema/migration/backfill foundation: 완료
  - V3.2 사용자 인식 write path: 완료
  - V3.3 사용자 scope scheduler 실행: 완료
  - V3.4 `/api/me/*` owner bridge 제거: 완료
  - V3.5 사용자별 bot runtime control: 완료
  - V3.6 web route와 role 분리: 완료
  - V3.7 security/risk/audit control: 완료
  - V3.8 multi-user test rewrite와 release gate: 완료

기준 Notion:
- Task index: `https://www.notion.so/31b899b6d7dc80d4af4be0041af7937d`
- V3 batch: `https://www.notion.so/31c899b6d7dc81f5a92bfa159119e6e5`

## 2) 핵심 불변조건 (invariants)

1. 사용자 격리
- order/position/pnl/runtime 데이터는 사용자 경계를 넘지 않는다.

2. 레거시 owner bridge 제거
- `/api/me/*` 읽기/쓰기 경로는 global owner bridge에 의존하지 않는다.

3. 런타임 제어 사용자화
- 전역 단일 `bot_config(id=1)` 전제를 두지 않는다.

4. 실패 격리
- 한 사용자의 credential/실행 오류가 다른 사용자 tick/실행을 중단시키지 않는다.

5. 권한 경계
- non-admin은 `/ops`, `/api/admin/*` 접근 불가.

## 3) Story별 구현 포인트

### 3.1 V3.1 ~ V3.2 (스키마/쓰기 경로)

- 주요 목적:
  - 사용자 식별 컬럼/제약 정합화
  - write path에 `user_id` 전파
  - 사용자 스코프 idempotency 강화
- 관련 문서:
  - `docs/postgres_v3_schema_sync_runbook_2026-03-08.md`

### 3.2 V3.3 ~ V3.5 (스케줄러/런타임)

- 주요 목적:
  - scheduler 실행 단위를 사용자 스코프로 분리
  - 사용자별 봇 런타임 제어
  - 실패 격리 보장
- 확인 포인트:
  - 사용자 A 오류가 사용자 B tick 처리량에 영향을 주지 않는지

### 3.3 V3.6 (웹 라우트/권한)

- 주요 목적:
  - 웹 라우트에서 admin/non-admin 경계 분리
  - 프론트 가드와 서버 권한 검증의 정합 유지

### 3.4 V3.7 (보안/리스크/감사)

- 주요 목적:
  - 감사 이벤트 표준화
  - admin 경계 강화
  - 사용자별 API budget 및 리스크 가드 운영 가능화
- 관련 문서:
  - `docs/credential_key_rotation_runbook_2026-03-08.md`

### 3.5 V3.8 (테스트/릴리즈 게이트)

- 주요 목적:
  - single-owner 가정 테스트 제거
  - A/B 격리/실패 전파 차단/마이그레이션 정합성 자동 검증
  - CI 릴리즈 게이트 편입
- 대표 테스트 영역:
  - `tests/test_me_read_service.py`
  - `tests/test_ops_http_auth.py`
  - multi-user scheduler 관련 테스트
  - migration integrity 관련 테스트

## 4) API/권한 계약 요약

1. 일반 사용자
- `/api/me/*`만 사용

2. 관리자 전용
- `/ops`, `/api/admin/*`

3. 에러 계약
- 인증 실패: `401 unauthorized`
- 자격증명 미설정/무효: `403 credentials_required` / `403 credentials_invalid`

## 5) 릴리즈 게이트 체크리스트 (개발 관점)

- [ ] 사용자 간 데이터 혼합 회귀 테스트 통과
- [ ] scheduler 실패 격리 회귀 테스트 통과
- [ ] admin 경계 deny/allow 테스트 통과
- [ ] migration before/after totals, counts 검증 통과
- [ ] keyring/credential 관련 시크릿 검증 통과

## 6) 운영/배포 시 필수 환경값

- `OPS_API_AUTH_SECRET`
- `OPS_API_AUTH_TOKEN_TTL_SECONDS`
- `OPS_API_CREDENTIALS_ENCRYPTION_KEY`
- `OPS_API_CREDENTIALS_KEYRING_JSON`

## 7) 신규 참여 개발자를 위한 온보딩 순서

1. `docs/context_anchor_v3_transition.md` 우선 숙지
2. `docs/postgres_v3_schema_sync_runbook_2026-03-08.md`로 마이그레이션/검증 절차 이해
3. `tests/test_me_read_service.py`, `tests/test_ops_http_auth.py`부터 회귀 포인트 파악
4. `/api/me/*`와 `/api/admin/*` 권한 경계 테스트를 먼저 실행

## 8) 후속 기술 과제 제안

1. 릴리즈 게이트 결과를 단일 리포트로 집계하는 자동화 출력(artifact) 추가
2. 사용자별 리스크/버짓 상태를 운영 UI에서 즉시 확인 가능한 API 정리
3. 감사 로그 조회 성능 튜닝(인덱스/보존정책/필터링 UX 연계)

## 9) 관련 문서

- `docs/context_anchor_v3_transition.md`
- `docs/postgres_v3_schema_sync_runbook_2026-03-08.md`
- `docs/credential_key_rotation_runbook_2026-03-08.md`
- `docs/ops_runbook.md`
- `docs/v3_multi_user_product_handover_2026-03-09.md`
