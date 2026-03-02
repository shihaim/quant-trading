# Ops Dashboard Web (Next.js)

Ops 대시보드를 위한 Next.js + TypeScript + Tailwind 프런트엔드입니다.

## 구조

- `app/`: Next App Router 페이지 및 전역 스타일
- `components/`: 클라이언트 컴포넌트
- `lib/`: API 클라이언트, 타입, 포맷 헬퍼

## 실행 방법

1. 백엔드 API 실행:

```bash
python -m trader.app.ops_api --host 127.0.0.1 --port 8080
```

2. 프런트엔드 실행:

```bash
cd apps/web
npm install
npm run dev
```

3. 접속:

- `http://127.0.0.1:3000`

## 환경 변수

직접 로컬 개발 시:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080
```

Compose/Caddy 배포 시:

```bash
NEXT_PUBLIC_API_BASE_URL=
```

- `https://qt-dashboard.local`로 접속
- `qt-dashboard.local`이 `127.0.0.1`을 가리키도록 hosts 항목 추가
- 브라우저가 same-origin `/api/*` 경로를 사용하도록 `NEXT_PUBLIC_API_BASE_URL`은 비워둠
- 브라우저가 인증서를 경고하면 호스트 OS에서 Caddy 로컬 CA를 신뢰 처리

프런트엔드 파일 로그(백엔드 로그와 분리 저장):

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
- 프런트엔드/백엔드 로그를 분리하기 위해 백엔드 로그는 저장소 루트의 `logs/` 아래에 유지하는 것을 권장합니다.

## 언어 지원

- 대시보드 UI는 한국어와 영어를 모두 지원합니다.
- 헤더의 언어 토글로 전환할 수 있습니다.
- 선택한 언어는 브라우저 `localStorage`에 저장됩니다.
