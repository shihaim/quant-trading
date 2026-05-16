# F2 V3 호환성 대체 경로 정리 계획 (2026-05-16)

- 스토리 ID: F2
- 출처: Notion `2026-05-16 Post-Hardening Follow-up Backlog`
- 상태: 제안됨
- 범위: 남아 있는 owner 대체 경로를 목록화하고, `/api/me/*` owner bridge 회귀를 막으며, 호환성 대체 경로의 종료 기준을 정의한다.

## 유지해야 할 불변식

1. 주문, 포지션, 손익, 런타임, 자격증명 데이터가 사용자 간에 섞이지 않아야 한다.
2. 인증된 `/api/me/*` 경로에 owner bridge가 다시 들어오면 안 된다.
3. 명시적인 호환성 대체 경로 외에는 global `bot_config(id=1)`을 필수 런타임 의존성으로 만들면 안 된다.
4. 한 사용자의 실패가 다른 사용자의 런타임을 중지하면 안 된다.
5. 일반 사용자는 `/ops` 또는 `/api/admin/*`에 접근할 수 없어야 한다.

## 현재 호환성 경로 목록

### 런타임 owner 해석

- `trader/config/config_repo.py`
  - `ConfigRepo.resolve_owner_user_id()`는 UPBIT 자격증명이 있는 가장 작은 사용자 ID, 그다음 가장 작은 사용자 ID, 마지막으로 기본값 `1`을 legacy owner로 해석한다.
  - 이 helper는 호환성 전용이며, 새 인증 API 읽기/쓰기 경로에서 사용하면 안 된다.

- `trader/trading/scheduler.py`
  - `TradingScheduler(user_id=None)`은 아직 `ConfigRepo.resolve_owner_user_id()`로 대체 해석한다.
  - 목표 상태: 운영 scheduler 생성 경로는 명시적인 `user_id`를 전달한다. 대체 경로는 entrypoint와 테스트가 이전될 때까지만 남긴다.

- `trader/app/p1_rehearsal.py`
  - P1 rehearsal helper는 `--user-id`가 있으면 명시 user id를 우선 사용한다.
  - `--user-id`가 없을 때만 V3 멀티유저 런타임 이전의 legacy owner를 로컬 호환 대체 경로로 해석한다.
  - 다음 목표 상태: 비로컬 실행에서는 `--user-id`를 요구하고, owner 해석을 로컬 전용 경로로만 남긴다.

### 관리자 role 대체 경로

- `OPS_API_ADMIN_EMAILS`
  - 현재 role resolver는 DB role(`users.is_admin`) 또는 env allowlist를 허용한다.
  - 목표 상태: DB role을 주 소스로 삼고, env allowlist는 비상용으로만 유지한 뒤 영구 런타임 설정에서는 제거한다.

### Legacy 응답 형태

- 일부 응답 타입과 호환성 표시 경로에는 `owner_user_id`가 남아 있다.
  - 현재 UI 문구는 이를 지속적인 ownership 모델이 아니라 `compatibility user`로 표현한다.
  - 목표 상태: 이 필드는 versioned response 정리 작업에서 제거하거나 이름을 바꾼다.

## 추가된 보호 장치

- `tests/test_v3_compatibility_guards.py`는 `/api/me/*` read service가 계속 명시적인 사용자 scope를 `OpsService`에 전달하는지 확인한다.
- 같은 테스트는 `resolve_owner_user_id()` 사용을 위에 적은 알려진 호환성 경로로 제한한다.

## 제거 순서

1. 완료: `trader/app/p1_rehearsal.py`에 명시적인 `--user-id` 지원을 추가한다.
2. 완료: 운영 문서를 명시적 user id 기반 rehearsal 흐름으로 갱신한다.
3. 일반 scheduler 경로가 항상 `user_id`를 넘기도록 `TradingScheduler` 생성 테스트와 런타임 entrypoint를 정리한다.
4. `TradingScheduler(user_id=None)` 대체 경로를 hard error 또는 로컬 전용 호환 경로로 바꾼다.
5. DB 기반 admin role 운영이 운영 환경에서 검증된 뒤 `OPS_API_ADMIN_EMAILS` 종료일을 결정한다.
6. 배포 문서에서 영구 `OPS_API_ADMIN_EMAILS` 사용을 제거하고, 비상 시 DB/API role grant 절차만 남긴다.

## Acceptance 매핑

- 남아 있는 호환성 경로와 제거 기준을 문서화했다.
- 새 `/api/me/*` read 경로가 owner 대체 해석을 쓰지 않도록 보호 장치를 추가했다.
- admin allowlist 대체 경로는 비상용 목표 상태와 제거 순서를 갖는다.
