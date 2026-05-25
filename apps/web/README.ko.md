# Don't worry, Be happy Web (Next.js)

사용자 대시보드와 관리자 콘솔을 위한 Next.js + TypeScript + Tailwind 프론트엔드입니다.

## 구조

- `app/`: Next App Router 페이지와 전역 스타일
- `components/`: 클라이언트 컴포넌트
- `lib/`: API 클라이언트, 타입, 포맷 헬퍼

주요 라우트:

- `/`: 서비스 소개와 로그인/회원가입 진입 페이지
- `/dashboard`: 사용자 계정 요약
- `/orders`: 사용자 주문 내역
- `/pnl`: 사용자 손익
- `/execution`: 사용자 체결 품질
- `/control`: 사용자 자동매매 제어
- `/admin/ops`: 관리자 운영 콘솔

## 실행

1. 백엔드 API 실행:

```bash
python -m trader.app.ops_api --host 127.0.0.1 --port 8080
```

2. 프론트엔드 실행:

```bash
cd apps/web
npm install
npm run dev
```

3. 접속:

- `http://127.0.0.1:3000`

## 환경 변수

직접 로컬 개발:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080
```

운영 Compose/Caddy 배포:

```bash
NEXT_PUBLIC_API_BASE_URL=
```

- `https://dont-worry-be-happy.today` 또는 `https://www.dont-worry-be-happy.today`로 접속
- 브라우저가 same-origin `/api/*`를 사용하도록 `NEXT_PUBLIC_API_BASE_URL`은 비움

로컬 Caddy 개발:

- `https://qt-dashboard.local`로 접속
- `qt-dashboard.local`이 `127.0.0.1`을 가리키도록 hosts 항목 추가
- 브라우저가 인증서를 경고하면 호스트 OS에서 Caddy 로컬 CA를 신뢰 처리

## 로컬 Preview 컨테이너

운영 웹 컨테이너를 건드리지 않고 프론트 변경사항을 검토할 때 사용합니다.

- 백엔드 preview API: `http://127.0.0.1:28080`
- 프론트 preview URL: `http://127.0.0.1:3000`
- 프론트 env: `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:28080`
- 로컬 검토 세션에서 사용하는 컨테이너 이름: `qt-web-preview`

preview 계정 비밀번호는 커밋되는 문서에 남기지 않습니다. 필요한 경우 로컬 preview 워크플로에서 계정을 생성하거나 시드합니다.

## 프론트엔드 파일 로그

백엔드 로그와 분리해서 저장합니다.

```bash
WEB_LOG_DIR=./logs
WEB_INFO_LOG_FILE=web-info.log
WEB_ERROR_LOG_FILE=web-error.log
WEB_LOG_LEVEL=INFO
WEB_LOG_ROTATE_MAX_BYTES=10485760
WEB_LOG_ROTATE_BACKUP_COUNT=10
```

- 클라이언트 오류는 `POST /api/logs`를 통해 수집되어 파일로 기록됩니다.
- 기본 실행 방식(`cd apps/web && npm run dev`)에서는 로그가 `apps/web/logs` 아래에 생성됩니다.
- 프론트엔드와 백엔드 로그를 분리하기 위해 백엔드 로그는 저장소 루트의 `logs/` 아래에 유지하는 것을 권장합니다.

## 언어 지원

- 대시보드 UI는 한국어와 영어를 지원합니다.
- 기본 언어는 한국어입니다.
- 헤더의 언어 토글로 전환할 수 있습니다.
- 선택한 언어는 브라우저 `localStorage`에 저장됩니다.

## UX 문구 규칙

- 사용자 페이지에는 `API 401: invalid credentials` 같은 원본 API 오류를 그대로 노출하지 않습니다.
- 기본 한국어에서는 친절하고 다음 행동이 보이는 문구를 사용하고, 영어 문구는 locale toggle을 통해 제공합니다.
- 관리자 페이지는 운영 상세 정보를 보여줄 수 있지만, 먼저 사람이 이해하기 쉬운 요약을 제공합니다.
