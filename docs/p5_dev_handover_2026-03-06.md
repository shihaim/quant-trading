# P5 개발 인수인계 2026-03-06 (인증 흐름 + Bot 계약 정렬)

- 작성일: 2026-03-06
- 대상: 개발팀
- 범위: 백엔드 `/api/me/bot/*`, FE6 브리지 제거, 인증 흐름 통합

## 1) 변경 요약

이번 인수인계는 아래 2개 작업 완료분을 다룹니다.

1. 로그인/회원가입 기반 인증 흐름 통합 (수동 토큰 입력 경로 제거)
2. 백엔드 `/api/me/bot/*` 구현 및 FE6의 404 레거시 브리지 fallback 제거

## 2) 백엔드 변경

### 2.1 신규 인증 Bot 엔드포인트

구현 위치: `trader/api/ops_http.py`

- `GET /api/me/bot/status`
- `POST /api/me/bot/start`
- `POST /api/me/bot/stop`

공통 동작:

- `Authorization: Bearer <token>` 필수
- 기존 인증 가드로 사용자 식별
- `MeReadService` 스코프 검증을 통과한 경우에만 처리

### 2.2 서비스 레이어 메서드

구현 위치: `trader/me/read_service.py`

- `get_bot_status(user=...)`
- `start_bot(user=...)`
- `stop_bot(user=...)`

동작:

- 기존 `_assert_read_scope`를 재사용
- 응답에 `source` 필드 포함
  - `/api/me/bot/status`
  - `/api/me/bot/start`
  - `/api/me/bot/stop`

### 2.3 에러 매핑 보완

`do_POST`에서 `UserScopeError`를 `403`으로 매핑하도록 수정했습니다.
(기존 일부 경로에서 `500`으로 누락되던 케이스 보완)

## 3) 프론트엔드 변경

### 3.1 FE6 브리지 제거

수정 파일: `apps/web/lib/api.ts`

- `getMyBotStatus`는 `/api/me/bot/status`만 호출
- `startMyBot`는 `/api/me/bot/start`만 호출
- `stopMyBot`는 `/api/me/bot/stop`만 호출
- 레거시 `/api/bot/enable|disable`로의 404 fallback 제거

### 3.2 Control 페이지 문구 정리

수정 파일: `apps/web/app/control/page.tsx`

- 안내 문구를 `/api/me/bot/*` 전용 흐름 기준으로 업데이트

### 3.3 인증 흐름 상태

현재 반영 상태:

- 로그인/회원가입 성공 시 액세스 토큰 자동 저장
- 보호 경로 접근 시 비인증 사용자는 로그인으로 리다이렉트

## 4) 테스트

수정 테스트:

- `tests/test_ops_http_auth.py`
- `tests/test_me_read_service.py`

추가 검증 범위:

- `/api/me/bot/*`의 `credentials_required`, `no_data_scope` 케이스
- status/start/stop 성공 경로
- 서비스 레벨 Bot 메서드 + 스코프 가드 동작

검증 명령:

```powershell
python -m pytest -q
```

최신 결과:

- `81 passed`

## 5) 호환성 메모

- 레거시 `/api/bot/enable`, `/api/bot/disable`는 기존 경로 호환을 위해 아직 유지됩니다.
- 전용 Bot Control 페이지는 이제 인증 사용자 스코프 계약만 사용하며 레거시 fallback에 의존하지 않습니다.

## 6) 후속 권장 작업

1. Home 대시보드의 레거시 Bot 토글 결합 제거
2. 레거시 엔드포인트 폐기 정책용 명시 테스트 추가
3. Bot 제어 감사 로그 계약 정의 및 구현
