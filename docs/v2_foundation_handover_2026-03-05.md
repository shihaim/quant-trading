# V2 기반 배치 인수인계 문서 (기획 + 개발)

- 날짜: 2026-03-05
- 대상: 기획자, 개발자, 운영자
- 범위: `V2.1`, `V2.2`, `V2.3` 완료 인수인계

## 1) 요약

`2026-03-04-v2-foundation` 배치는 완료되었습니다.

주요 산출물:

- 인증/사용자 식별 기반 구축 (`/api/auth/*`, `/api/me`)
- 사용자별 Upbit 자격증명 암호화 저장 및 상태 조회 경로
- `/api/me/*` 기반 인증 사용자 범위 조회 API

배치 상태 참고 문서:

- `ticket/BATCH_MAP.md`
- `ticket/2026-03-04-v2-foundation/README.md`

## 2) 안정 API 계약 (현재)

인증/식별:

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/me` (`Bearer` 토큰 필요)

자격증명 등록/상태:

- `GET /api/me/credentials/upbit` (`Bearer` 토큰 필요)
- `POST /api/me/credentials/upbit` (`Bearer` 토큰 필요)

사용자 범위 조회:

- `GET /api/me/orders?state=...&limit=...` (`Bearer` 토큰 필요)
- `GET /api/me/pnl/daily?days=...&tz=...` (`Bearer` 토큰 필요)
- `GET /api/me/metrics/trade?limit=...` (`Bearer` 토큰 필요)

운영 호환을 위한 레거시 엔드포인트(유지):

- `GET /api/orders`
- `GET /api/pnl/daily`
- `GET /api/metrics/trade`
- `GET /api/ops/summary`

## 3) 보안/동작 메모 (중요)

### 3.1 인증

- `Bearer` 토큰 누락/유효하지 않음은 `401`을 반환합니다.
- 입력값/인증 도메인 오류는 명시적인 JSON 오류 코드로 반환합니다.

### 3.2 자격증명 저장

- 일반 API 응답에 Upbit 원문 키는 반환하지 않습니다.
- 키는 `user_exchange_credentials` 테이블에 암호화된 상태로 저장됩니다.
- 상태 API는 마스킹 값과 fingerprint prefix 메타데이터만 반환합니다.

### 3.3 V2 조회 범위 (브리지 모드)

현재 거래/주문 테이블이 단일 봇(글로벌) 구조이므로, 임시 전환 규칙을 적용합니다.

- 유효한 Upbit 자격증명이 없으면 `403 credentials_required`(또는 `credentials_invalid`)를 반환합니다.
- 조회 데이터는 브리지 owner 사용자만 읽을 수 있습니다(자격증명이 있는 사용자 중 `min(user_id)`).
- owner가 아닌 인증 사용자는 `403 no_data_scope`를 반환합니다.

`/api/me/*` 응답에는 아래 `scope` 메타데이터가 포함됩니다.

- `mode`: `legacy_single_bot_owner_bridge`
- `user_id`
- `owner_user_id`

## 4) 기획 관점: 제품 계획에서 달라진 점

- 백엔드 선행조건이 충족되어, 지연된 프론트 티켓 `P1-FE3` ~ `P1-FE6`를 재개할 수 있습니다.
- Orders/PnL/Execution 화면의 API 기준은 `/api/me/*`로 맞추는 것이 권장됩니다.
- 제어 페이지(`P1-FE6`)는 인증 계약 기준으로 진행 가능하나, 쓰기 가능한 bot control 계약 강화는 후속 과제입니다.

## 5) 개발 관점: 연동 체크리스트

1. 프론트 API 클라이언트가 `Authorization: Bearer <token>`을 지원해야 합니다.
2. 로그인/회원가입 플로우에서 access token을 저장하고 `/api/me/*` 요청에 첨부해야 합니다.
3. 조회 페이지 진입 전, 자격증명 설정 화면에서 `POST /api/me/credentials/upbit`를 호출해야 합니다.
4. 조회 페이지는 아래 오류를 처리해야 합니다.
`401 unauthorized`
`403 credentials_required`
`403 no_data_scope`
5. 전체 사용자 범위 마이그레이션 완료 전까지는 레거시 운영 화면에서 `/api/ops/summary` 호환을 유지합니다.

## 6) 환경변수/설정 변경

신규 런타임 환경변수:

- `OPS_API_AUTH_SECRET`
- `OPS_API_AUTH_TOKEN_TTL_SECONDS`
- `OPS_API_CREDENTIALS_ENCRYPTION_KEY`

참고:

- `.env.runtime.example`
- `README.md`

## 7) 알려진 갭 / 다음 기술 단계

1. 브리지 모드 조회 범위를 실제 사용자별 데이터 분리 구조로 교체
2. 쓰기 가능한 bot control/거래 액션을 사용자 자격증명 경로로 마이그레이션
3. 운영 보안 요구 수준에 맞춰 토큰 refresh/rotation 및 세션 정책 강화
4. `apps/web/lib/api.ts`가 `/api/me/*`로 전환된 뒤 프론트 타입 기준 API 계약 테스트 추가

## 8) 테스트 상태 스냅샷

2026-03-05 기준:

- `python -m pytest -q` 통과 (`81 passed`)
- 인증, 자격증명 암호화, `/api/me/*` 동작, scope 규칙 테스트 포함

## 9) 로컬 Docker PAPER 검증 (2026-03-05)

환경:

- Compose 파일: `docker-compose.yml` + `docker-compose.local.override.yml`
- Env 파일: `.env.runtime.paper`
- 이미지 태그: `paper`
- API 엔드포인트: `http://127.0.0.1:18080`

실행/결과:

1. 로컬 override + paper env로 `ops-api`를 재생성
2. `POST /api/auth/login`, `GET /api/me` 성공
3. 사용자 자격증명 없이 `GET /api/me/orders` 호출 시 기대값인 `403 credentials_required` 반환
4. `POST /api/me/credentials/upbit` 성공 및 마스킹된 자격증명 상태 반환
5. `GET /api/me/orders`, `GET /api/me/pnl/daily`, `GET /api/me/metrics/trade` 모두 성공

기획/개발 참고:

- 신규 사용자 범위에서는 `orders`/`metrics`가 빈 리스트를 반환해도 정상입니다.
- 로컬 검증은 `docker-compose.local.override.yml`의 `18080:8080` 포트 퍼블리시를 사용했습니다.
- 이 환경에서는 override에서 `ops-api`를 `local` 네트워크에 붙였을 때 호스트 접근 확인이 더 안정적이었습니다.
