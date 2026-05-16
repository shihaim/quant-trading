# S5 인증/세션 수명주기 하드닝 2026-03-22

- story_id: S5
- 범위: token 만료 UX, logout baseline, client 저장소 정책

## 결정 사항

1. Access token 저장소는 현행대로 `localStorage`를 유지한다.
2. Refresh token은 이번 배치에서 도입하지 않는다.
3. 401 응답 시 클라이언트는 로컬 인증 상태를 즉시 제거하고 로그인으로 이동한다.
4. 만료 토큰은 서버에서 `expired_token`으로 구분해 반환한다.
5. 강제 무효화는 `users.token_version` 증가 방식으로 처리한다.

## 동작 기준

- 만료 토큰:
  - 서버 응답: `401 {"error":"unauthorized","message":"expired_token"}`
  - 클라이언트: 토큰 제거 후 `/login?reason=expired&next=...` 이동
- 기타 인증 실패:
  - 서버 응답: `401` + 기존 메시지 (`missing_token`, `invalid_token`, `invalid_user`)
  - 클라이언트: 토큰 제거 후 `/login?reason=unauthorized&next=...` 이동
- 서버 강제 무효화:
  - 서버 응답: `401 {"error":"unauthorized","message":"session_revoked"}`
  - 클라이언트: 토큰 제거 후 `/login?reason=revoked&next=...` 이동
- 수동 로그아웃:
  - 클라이언트: 토큰 제거 후 `/login?reason=logged_out&next=...` 이동

## 관리자 강제 무효화 API

- `POST /api/admin/users/{user_id}/sessions/invalidate`
- 요청 본문:
  - `reason` (optional string)
- 응답:
  - `user_id`
  - `invalidated_before_version`
  - `token_version`
  - `source`

## 보안/운영 메모

- 이번 변경은 admin/non-admin 권한 경계를 변경하지 않는다.
- `/api/me/*` 사용자 스코프 계약은 그대로 유지된다.
- 강제 무효화/토큰 버전 관리(refresh 포함)는 후속 작업으로 분리한다.
