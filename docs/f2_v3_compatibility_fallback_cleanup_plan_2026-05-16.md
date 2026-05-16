# F2 V3 호환성 대체 경로 정리 계획 (2026-05-16)

- 스토리 ID: F2
- 출처: Notion `2026-05-16 Post-Hardening Follow-up Backlog`
- 상태: 진행 중
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
  - 완료: `TradingScheduler(user_id=None)`은 `user_id_required` hard error를 발생시킨다.
  - 운영 scheduler 생성 경로는 명시적인 `user_id`를 전달한다.

- `trader/app/p1_rehearsal.py`
  - P1 rehearsal helper는 `--user-id`가 있으면 명시 user id를 우선 사용한다.
  - 완료: `--user-id`가 없을 때의 legacy owner 해석은 `PAPER` 모드에서만 허용한다.
  - 완료: `REAL`, `TEST`, `SHADOW`에서는 `--user-id`가 없으면 `user_id_required` hard error를 발생시킨다.

### 관리자 role 대체 경로

- `OPS_API_ADMIN_EMAILS`
  - 완료: role resolver는 DB role(`users.is_admin`)만 권한 소스로 사용한다.
  - 완료: `OPS_API_ADMIN_EMAILS`는 런타임 설정에서 제거했다. 비상 권한 부여/회수는 DB/API role grant 절차를 사용한다.

### Legacy 응답 형태

- 완료: `apps/web` 타입과 화면 표시에서는 `owner_user_id` 및 `compatibility user` 문구를 제거했다.
- 백엔드 응답 필드 자체 제거는 API shape 변경이므로 versioned response 정리 작업에서 별도로 처리한다.

## 추가된 보호 장치

- `tests/test_v3_compatibility_guards.py`는 `/api/me/*` read service가 계속 명시적인 사용자 scope를 `OpsService`에 전달하는지 확인한다.
- 같은 테스트는 `resolve_owner_user_id()` 사용을 위에 적은 알려진 호환성 경로로 제한한다.

## 제거 순서

1. 완료: `trader/app/p1_rehearsal.py`에 명시적인 `--user-id` 지원을 추가한다.
2. 완료: 운영 문서를 명시적 user id 기반 rehearsal 흐름으로 갱신한다.
3. 완료: 일반 scheduler 경로가 항상 `user_id`를 넘기도록 `TradingScheduler` 생성 테스트와 런타임 entrypoint를 정리한다.
4. 완료: `TradingScheduler(user_id=None)` 대체 경로를 `user_id_required` hard error로 바꾼다.
5. 완료: DB 기반 admin role 운영 기준을 운영 문서에 남기고 `OPS_API_ADMIN_EMAILS` 대체 권한 판정을 제거했다.
6. 완료: 배포 문서에서 영구 `OPS_API_ADMIN_EMAILS` 사용을 제거하고, 비상 시 DB/API role grant 절차만 남겼다.
7. 완료: P1 rehearsal owner fallback을 `PAPER` 전용으로 제한하고 비-PAPER 실행에서는 명시적인 `--user-id`를 요구한다.
8. 완료: 프론트 타입과 사용자 화면에서 `owner_user_id` 호환성 표시를 제거한다.

## Acceptance 매핑

- 남아 있는 호환성 경로와 제거 기준을 문서화했다.
- 새 `/api/me/*` read 경로가 owner 대체 해석을 쓰지 않도록 보호 장치를 추가했다.
- admin allowlist 대체 경로는 제거되었고, admin 권한은 DB role로만 판정된다.
- 프론트는 `scope.user_id`만 표시하고, legacy owner scope 용어를 사용자 화면에 노출하지 않는다.
