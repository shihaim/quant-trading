# V2 기반 배치 인수인계 문서 (기획 + 개발)

- 기준일: 2026-03-05
- 대상: 기획자, 개발자, 운영자
- 범위: `V2.1`, `V2.2`, `V2.3` 완료 인수인계

## 0) 2026-03-06 업데이트

- `2026-03-03` 프론트 배치(`P1-FE1` ~ `P1-FE6`)가 완료되어 배치가 종료되었습니다.
- Bot Control 인증 계약이 실제 구현/연동 완료되었습니다.
  - `GET /api/me/bot/status`
  - `POST /api/me/bot/start`
  - `POST /api/me/bot/stop`
- FE6의 레거시 404 브리지 fallback이 제거되었습니다.

## 1) 배치 요약

`2026-03-04-v2-foundation` 배치는 완료되었습니다.

핵심 결과:

- 인증/사용자 식별 기반 구축 (`/api/auth/*`, `/api/me`)
- 사용자별 Upbit 자격증명 암호화 저장/상태 조회 경로 확보
- `/api/me/*` 기반 사용자 스코프 조회 API 제공

참고 문서:

- Notion Task index: `https://www.notion.so/31b899b6d7dc80d4af4be0041af7937d`
- Notion archive page (`[ARCHIVE] 2026-03-04 V2 Foundation`): `https://www.notion.so/31b899b6d7dc8133a581ec6797ba021e`

## 2) 확정 API 계약

인증/식별:

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/me` (`Bearer` 토큰 필요)

자격증명 저장/상태:

- `GET /api/me/credentials/upbit` (`Bearer` 토큰 필요)
- `POST /api/me/credentials/upbit` (`Bearer` 토큰 필요)

사용자 스코프 조회:

- `GET /api/me/orders?state=...&limit=...` (`Bearer` 토큰 필요)
- `GET /api/me/pnl/daily?days=...&tz=...` (`Bearer` 토큰 필요)
- `GET /api/me/metrics/trade?limit=...` (`Bearer` 토큰 필요)

사용자 스코프 Bot 제어:

- `GET /api/me/bot/status` (`Bearer` 토큰 필요)
- `POST /api/me/bot/start` (`Bearer` 토큰 필요)
- `POST /api/me/bot/stop` (`Bearer` 토큰 필요)

레거시 운영 호환 경로(참조용):

- `GET /api/orders`
- `GET /api/pnl/daily`
- `GET /api/metrics/trade`
- `GET /api/ops/summary`
- `POST /api/bot/enable`
- `POST /api/bot/disable`

## 3) 권한/보안 동작 메모

- `Bearer` 토큰이 없거나 유효하지 않으면 `401 unauthorized` 반환
- 자격증명 미설정/손상 시 `403 credentials_required` 또는 `403 credentials_invalid` 반환
- 브리지 모드에서 owner scope가 아닌 사용자는 `403 no_data_scope` 반환
- `/api/me/*` 조회 응답은 `scope` 메타데이터를 포함
  - `mode`: `legacy_single_bot_owner_bridge`
  - `user_id`
  - `owner_user_id`

## 4) 프론트 연동 상태

- 지연 프론트 티켓 `P1-FE3` ~ `P1-FE6`는 2026-03-06 기준 모두 완료
- Orders/PnL/Execution은 `/api/me/*` 사용자 스코프 계약 기준으로 동작
- Bot Control(`P1-FE6`)은 `/api/me/bot/*` 계약으로 전환 완료

## 5) 개발 체크리스트

1. 프론트 API 클라이언트가 `Authorization: Bearer <token>`를 포함하는지 확인
2. 로그인/회원가입 성공 후 토큰 저장 및 보호 경로 리다이렉트 확인
3. `/api/me/credentials/upbit` 미설정 상태 에러 처리(`credentials_required`) 확인
4. Bot Control 경로가 `/api/me/bot/*`만 사용하고 레거시 fallback이 없는지 확인

## 6) 필수 환경변수

- `OPS_API_AUTH_SECRET`
- `OPS_API_AUTH_TOKEN_TTL_SECONDS`
- `OPS_API_CREDENTIALS_ENCRYPTION_KEY`

참고:

- `.env.runtime.example`
- `README.md`

## 7) 남은 기술 과제

1. 브리지 모드 조회 범위를 실제 사용자별 데이터 분리 구조로 교체
2. 레거시 Bot 제어 경로(`/api/bot/enable`, `/api/bot/disable`) 폐기 계획 수립
3. 운영 보안 수준에 맞춰 token refresh/rotation 및 세션 정책 강화
4. Bot Control 감사 로그(행위자/시각/액션) 계약 정의 및 구현

## 8) 테스트/검증 스냅샷

- `python -m pytest -q` 통과 (`81 passed`)
- 인증, 자격증명, `/api/me/*`, `/api/me/bot/*` 경로 검증 포함

## 9) 로컬 Docker PAPER 검증 (2026-03-05)

환경:

- Compose: `docker-compose.yml` + `docker-compose.local.override.yml`
- Env: `.env.runtime.paper`
- API 바인드: `http://127.0.0.1:18080`

검증 요약:

1. `POST /api/auth/login`, `GET /api/me` 성공
2. 자격증명 미설정 상태에서 `GET /api/me/orders` -> `403 credentials_required`
3. `POST /api/me/credentials/upbit` 성공
4. `GET /api/me/orders`, `GET /api/me/pnl/daily`, `GET /api/me/metrics/trade` 성공
5. `GET /api/me/bot/status`, `POST /api/me/bot/start`, `POST /api/me/bot/stop` 성공
