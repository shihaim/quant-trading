# P4 개발 인수인계 문서 (Ops API/Next 웹)

- 작성일: 2026-02-26
- 대상: 개발자
- 범위: 백엔드 모듈 분리 리팩터링 + Next.js 마이그레이션 + i18n

## 1) 변경 개요

이번 변경은 아래 3개를 동시에 수행:

1. 운영 API 백엔드 계층 분리
2. 웹 프론트 정적 페이지 -> Next.js 전환
3. 대시보드 한/영 UI 지원 추가

## 2) 백엔드 아키텍처

### 2.1 계층 분리

- 엔트리포인트: `trader/app/ops_api.py`
- HTTP 어댑터: `trader/api/ops_http.py`
- 애플리케이션 서비스: `trader/ops/service.py`
- DTO/직렬화: `trader/ops/dto.py`
- DB 초기화/세션 팩토리: `trader/data/db.py`

핵심 의도:

- 엔트리포인트는 부팅/의존성 주입만 담당
- HTTP 구현(`BaseHTTPRequestHandler`)을 독립 모듈로 격리
- 서비스는 비즈니스 집계 중심, 표현 포맷은 DTO로 분리

### 2.2 DB 유틸 추가

`trader/data/db.py`:

- `get_session_factory()`
- `create_session()`
- `initialize_database()`

`trader/app/main.py`도 `initialize_database()`를 사용하도록 통일.

### 2.3 API 목록

- `GET /api/ops/summary`
- `GET /api/orders`
- `GET /api/pnl/daily`
- `GET /api/metrics/trade`
- `POST /api/bot/enable`
- `POST /api/bot/disable`
- `OPTIONS` preflight 대응

## 3) 프론트엔드 (Next.js)

### 3.1 구조

- `apps/web/app/*`: App Router
- `apps/web/components/ops-dashboard.tsx`: 메인 화면/폴링/조작
- `apps/web/lib/api.ts`: API 호출
- `apps/web/lib/types.ts`: 응답 타입
- `apps/web/lib/format.ts`: 숫자/시간 포맷
- `apps/web/lib/i18n.ts`: 한/영 문구 사전

### 3.2 사용 스택

- Next.js 14.2.35
- React 18
- TypeScript
- Tailwind CSS

### 3.3 i18n 방식

- 런타임 로컬 i18n(`en`, `ko`) 사전 기반
- 헤더 토글로 언어 전환
- 선택값 `localStorage(ops_locale)` 저장
- 숫자/시간 `en-US`, `ko-KR` locale 포맷 적용

## 4) 실행 방법

### 4.1 백엔드

`python -m trader.app.ops_api --host 127.0.0.1 --port 8080`

### 4.2 프론트

`cd apps/web`

- 설치: `npm.cmd install`
- 개발: `npm.cmd run dev`
- 빌드: `npm.cmd run build`
- 린트: `npm.cmd run lint`

PowerShell 정책으로 `npm`이 막히면 `npm.cmd` 사용.

### 4.3 환경변수

- 백엔드: `OPS_API_ALLOW_ORIGIN`
- 프론트: `NEXT_PUBLIC_API_BASE_URL` (기본 `http://127.0.0.1:8080`)

## 5) 검증 결과

- Python 테스트: `python -m pytest -q` -> `42 passed`
- Next lint: `npm.cmd --prefix apps/web run lint` -> 통과
- Next build: `npm.cmd --prefix apps/web run build` -> 통과

## 6) 알려진 이슈 / 메모

1. `npm audit`에서 dev 체인 중심 취약점(high) 일부 잔존.
2. 운영 API 인증/인가 미적용 상태.
3. 웹에서 실시간은 polling 기반(웹소켓 미적용).

## 7) 후속 개발 권장

1. 인증 계층 추가(최소 토큰 기반 보호)
2. Bot Control 고도화(2단계 확인 + 변경 diff 표시)
3. Orders 상세 페이지 확장(필터/정렬/액션)
4. 국제화 프레임워크(next-intl) 도입 여부 검토

