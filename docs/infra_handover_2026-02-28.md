# 인프라 작업 인수인계 문서

- 작성일: 2026-02-28
- 대상: 개발자 / 인프라 담당자
- 기준 문서: `Infra 1차 작업` -> `최종 2` -> `Infra 2차 작업`
- 기준 리비전: `cfdce6df90576874166334b1f3c53f11c3475d41` 이후 ~ 현재 HEAD

## 1) 작업 목적

이번 작업의 목적은 기존 로컬 실행 중심 구조를 다음 상태로 전환하는 것이었다.

1. GitHub Actions 기반 자동 배포 파이프라인 구축
2. Docker Compose 기반 멀티서비스 운영 구조 정리
3. SQLite 기본 구조를 유지하면서 PostgreSQL로 부팅 가능한 경로 확보
4. 런타임 시크릿을 Git 저장소 밖에서 주입하는 운영 패턴 정착
5. 프록시 라우팅과 웹/백엔드 서비스 경계를 운영 관점에서 명확화

문서 초안 기준으로는 "로컬 PC에서 24/7 운영 가능한 VPC 유사 구조"와 "SQLite -> PostgreSQL 전환"이 목표였고, 실제 반영은 "PostgreSQL 부팅 가능 + 자동 배포 가능"까지 완료된 상태다.

## 2) 최종 반영 범위

이번 리비전 구간에서 실제 변경된 파일은 아래와 같다.

- `.github/workflows/ci-cd.yml`
- `docker-compose.yml`
- `infra/caddy/Caddyfile`
- `.dockerignore`
- `.env.runtime.example`
- `.gitignore`
- `Dockerfile.ops-api`
- `Dockerfile.trader`
- `apps/web/Dockerfile.web`
- `pyproject.toml`
- `trader/data/db.py`
- `tests/test_db_bootstrap.py`
- `README.md`
- `README.ko.md`

참고: `apps/web/app/api/logs/route.ts`는 현재 레포에 존재하지만, 이번 리비전 구간에서 새로 추가된 파일은 아니다. 이번 작업에서는 Caddy 라우팅이 해당 엔드포인트와 충돌하지 않도록 정합성을 맞춘 성격이 더 크다.

## 3) 커밋별 작업 내역

### 3.1 `cfdce6d` (2026-02-28 13:35 KST)

초기 인프라/배포 베이스를 한 번에 추가한 커밋이다.

- GitHub Actions CI/CD 파이프라인 추가
- self-hosted runner 기반 `deploy_local` 잡 추가
- 런타임 env 파일 `.env.runtime` 생성 로직 추가
- GHCR 대상 3개 이미지 빌드/푸시 파이프라인 추가
- `Dockerfile.ops-api`, `Dockerfile.trader`, `apps/web/Dockerfile.web` 추가
- `docker-compose.yml` 추가
- `infra/caddy/Caddyfile` 추가
- `.dockerignore`, `.env.runtime.example` 추가

이 시점부터 "main push -> 이미지 빌드 -> 로컬 러너 배포"의 기본 골격이 생겼다.

### 3.2 `956ef2a` (2026-02-28 13:57 KST)

패키징 범위를 정리한 커밋이다.

- `setuptools` 패키지 검색 대상에 `trader*`만 포함
- `apps*`, `infra*`, `tests*` 제외

의도는 Python 이미지 내부 `pip install -e .[dev]` 시 불필요한 디렉터리가 Python 패키지로 잡히지 않게 만드는 것이다.

### 3.3 `7c83fdd` (2026-02-28 14:55 KST)

배포 태그와 GHCR 로그인 방식을 조정한 커밋이다.

- self-hosted 배포 시 `IMAGE_TAG=latest` 사용
- deploy 단계 GHCR 로그인 시 `GHCR_USER` / `GHCR_PAT` 사용
- `docker login` 시 비밀번호를 임시 파일로 저장 후 `--password-stdin` 사용

주의할 점은 build 단계는 여전히 `github.actor` + `GITHUB_TOKEN`으로 GHCR에 로그인하고, deploy 단계만 stable user를 사용한다는 점이다.

### 3.4 `c6b240d` (2026-02-28 16:15 KST)

PostgreSQL 부팅 안정화의 핵심 커밋이다.

- workflow에서 `DATABASE_URL`을 조합해 `.env.runtime`에 명시적으로 기록
- 사용자명/비밀번호를 URL-encode 후 PostgreSQL DSN 생성
- 배포 후 `pg_isready` 및 `psql -c "\dt"`로 부트스트랩 검증 추가
- `pyproject.toml`에 `psycopg[binary]` 의존성 추가
- `README.md`에 "로컬은 SQLite fallback, compose는 Postgres 기본" 전제 추가
- `trader/data/db.py`에 PostgreSQL용 KST view SQL 분기 추가
- `initialize_database()` 후처리 강화
- `tests/test_db_bootstrap.py` 추가

이 커밋 이후부터는 빈 PostgreSQL에서도 앱이 최소 스키마를 만들고 부팅 가능한 구조가 되었다.

### 3.5 `0d7a446` (2026-02-28 16:27 KST)

PostgreSQL 운영 접근성을 조정한 커밋이다.

- `POSTGRES_DB`, `POSTGRES_USER` 환경변수 명시
- PostgreSQL host 바인딩 포트 추가 (`127.0.0.1:5432:5432`)

초기에는 운영자 로컬에서 DB 접속을 쉽게 하기 위한 설정이었다.

### 3.6 `a895698` (2026-02-28 17:11 KST)

PostgreSQL 포트 충돌 회피 및 네트워크 세분화 커밋이다.

- PostgreSQL host 바인딩 포트를 `5432`에서 `15432`로 변경
- `local` 네트워크 추가
- Postgres를 `local` + `data` 네트워크에 연결

최종적으로 DB는 외부 공개 포트가 아니라 `127.0.0.1:15432`로만 로컬 호스트에서 접근 가능하다.

### 3.7 `09637f8` (2026-02-28 18:06 KST)

문서 정리 커밋이다.

- `README.ko.md` 추가
- `README.md` 상단에 한국어 README 링크 추가
- PostgreSQL/SQLite 운영 전제 문서화 보강

## 4) 현재 운영 구조

### 4.1 배포 파이프라인

GitHub Actions는 현재 3단계로 동작한다.

1. `ci`
2. `build_and_push`
3. `deploy_local`

세부 동작은 아래와 같다.

- `ci`: Python 3.12 기준 `pip install -e ".[dev]"` 후 `pytest -q`
- `build_and_push`: `ops-api`, `trader`, `web` 이미지를 GHCR에 push
- `deploy_local`: self-hosted runner에서 `.env.runtime` 생성 후 `docker compose pull && up -d`

운영 특성:

- 배포 트리거는 `main` 브랜치 push
- 이미지 태그는 build 시 `sha`와 `latest` 둘 다 push
- 실제 배포 소비 태그는 `latest`
- 배포 후 불필요 이미지 정리를 위해 `docker image prune -f` 실행

### 4.2 서비스 토폴로지

현재 `docker-compose.yml` 기준 구성은 아래와 같다.

- `caddy`: 외부 80 포트 진입점
- `web`: Next.js 운영 프론트
- `ops-api`: 운영용 API
- `trader`: 메인 트레이딩 런타임
- `postgres`: 상태 저장 DB

네트워크 구성:

- `public`: 외부 진입용
- `private`: 내부 앱 통신용 (`internal: true`)
- `data`: 데이터 계층용 (`internal: true`)
- `local`: 운영자 로컬 DB 접근용

실제 연결:

- `caddy` -> `public`, `private`
- `web` -> `private`
- `ops-api` -> `private`, `data`
- `trader` -> `private`, `data`
- `postgres` -> `local`, `data`

### 4.3 프록시 라우팅

`infra/caddy/Caddyfile` 기준 라우팅은 다음과 같다.

- `/api/logs*` -> `web:3000`
- `/api/*` -> `ops-api:8080`
- 그 외 전체 -> `web:3000`

핵심 포인트:

- `handle_path`가 아니라 `handle`을 사용해 `/api` prefix strip을 방지
- 클라이언트 로그 수집 엔드포인트를 ops-api가 아니라 Next 앱으로 유지
- 프론트 코드의 `/api/...` prefix 사용 방식과 프록시 동작을 맞춤

## 5) PostgreSQL 전환 관련 실제 구현 상태

### 5.1 완료된 부분

현재는 "SQLite에서 PostgreSQL로 실제 부팅" 경로가 구현되어 있다.

- `ops-api`, `trader` 모두 `DATABASE_URL`을 env에서 받아 사용
- workflow가 `.env.runtime` 생성 시 Postgres DSN을 명시적으로 주입
- `initialize_database()`가 애플리케이션 시작 시 호출됨
- `Base.metadata.create_all()` 후 후속 시드/문서/뷰 동기화 수행

실제 호출 위치:

- `trader/app/main.py`
- `trader/app/ops_api.py`

즉, PostgreSQL 빈 DB에서도 애플리케이션이 기동되면 기본 테이블과 보조 메타데이터를 생성할 수 있다.

### 5.2 `trader/data/db.py`에서 추가된 부트스트랩 로직

이번 작업에서 DB 초기화 로직은 아래 방향으로 보강되었다.

- DB dialect 감지 함수 추가 (`sqlite` / `postgresql`)
- KST view SQL을 dialect 별로 분기
- SQLite 전용 lightweight migration은 SQLite에서만 실행
- `timeframe_config` 자동 시드
- `schema_table_docs`, `schema_column_docs` 자동 동기화
- KST 조회용 view 재생성

결과적으로:

- SQLite: 기존 경량 마이그레이션 유지
- PostgreSQL: `create_all()` 중심으로 신규 스키마 부팅 가능

### 5.3 테스트 보강

`tests/test_db_bootstrap.py`가 추가되어 아래를 검증한다.

- `SUPPORTED_TIMEFRAMES` 기준 `timeframe_config` 시드 여부
- schema docs 참조 데이터 입력 여부
- dialect에 따라 KST view SQL이 올바르게 분기되는지 여부

이 테스트는 PostgreSQL 전체 통합테스트는 아니지만, DB 부트스트랩 로직 회귀를 막는 최소 안전장치 역할을 한다.

## 6) 시크릿 / 환경변수 운영 방식

이번 작업에서는 `.env`, `.env.runtime`, DB 파일을 Git에 올리지 않는 운영 원칙을 유지했다.

적용 방식:

- GitHub Secrets를 source of truth로 사용
- self-hosted runner가 배포 시 `.env.runtime`를 생성
- Compose는 `env_file: ./.env.runtime`로 각 서비스에 주입

주요 변수:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `TRADE_MODE`
- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `NEXT_PUBLIC_API_BASE_URL`

### 6.1 변수 중요도 분류(운영 기준)

운영 중 가장 자주 발생하는 장애는 "값이 아예 없어서 실패"보다 "workflow가 빈 값을 `.env.runtime`에 써서 컨테이너가 부팅 직후 죽는 경우"다. 따라서 아래 분류는 "현재 `deploy_local` 구현 기준으로 비면 안 되는 값"과 "기능 조건부 값"을 나눠서 본다.

- 배포 인증 필수: `GHCR_USER`, `GHCR_PAT`
- 현재 `deploy_local` 기준 사실상 필수: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `TRADE_MODE`
- 조건부 필수: `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY` (`REAL/TEST/SHADOW` 모드)
- 선택: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (알림 정책에 따라 필수화 가능)
- 선택: tuning / logging / allowlist 계열 값들

주의:

- `TRADE_MODE`는 코드상 기본값이 `PAPER`이지만, 현재 workflow가 `.env.runtime`에 `TRADE_MODE=`를 직접 기록하므로 secrets 값이 비면 기본값 fallback 대신 빈 문자열 검증 실패가 발생할 수 있다.
- `POSTGRES_DB`, `POSTGRES_USER`도 Compose 자체에는 기본값이 있지만, 현재 workflow가 이 값을 사용해 `DATABASE_URL`을 직접 조합하므로 운영상 필수처럼 취급하는 것이 안전하다.

### 6.2 `deploy_local` fail-fast 가드 권장

현재 workflow는 secrets가 비어 있어도 `.env.runtime`를 생성한다. 이 경우 `KEY=` 형태의 빈 값이 들어가서 앱이 부팅 직후 종료될 수 있다.

운영 가이드 기준으로는 아래 값은 `.env.runtime` 작성 전에 즉시 검증하고, 비어 있으면 deploy를 실패시키는 것이 맞다.

- `POSTGRES_PASSWORD`
- `TRADE_MODE`
- 필요 시 `POSTGRES_DB`
- 필요 시 `POSTGRES_USER`
- `GHCR_USER`
- `GHCR_PAT`

권장 구현 예시:

```powershell
if ([string]::IsNullOrWhiteSpace("${{ secrets.POSTGRES_PASSWORD }}")) { throw "POSTGRES_PASSWORD is required" }
if ([string]::IsNullOrWhiteSpace("${{ secrets.TRADE_MODE }}")) { throw "TRADE_MODE is required" }
```

추가 포인트:

- `.env.runtime.example`를 두어 수동 배포/로컬 검증 시 참조 가능
- `.gitignore`는 `.env.*`를 제외하되 `.env.example`, `.env.runtime.example`은 예외 허용
- `.dockerignore`는 런타임 산출물과 시크릿 파일이 이미지 빌드 컨텍스트에 포함되지 않도록 차단

## 7) 문서 초안 대비 실제 반영 차이

문서 초안(`최종 2`, `Infra 2차 작업`)에서 제안한 항목과 실제 상태는 일부 차이가 있다.

### 7.1 완료

- 자동 배포 파이프라인 구축
- GHCR 기반 이미지 운영
- Caddy 리버스 프록시 라우팅 정리
- `.env.runtime` 기반 시크릿 주입
- PostgreSQL 기본 부팅 경로 확보
- DB bootstrap 검증 단계 추가

### 7.2 부분 반영

- GHCR stable user 사용
  - deploy 단계만 반영
  - build 단계는 여전히 `github.actor` + `GITHUB_TOKEN`

- PostgreSQL 외부 노출 차단
  - 완전 비노출은 아님
  - 현재는 `127.0.0.1:15432`로 로컬 호스트에만 노출
  - 운영 권장 정책은 "기본 비공개, 운영자 점검이 필요할 때만 임시 publish"다
  - 현재 설정은 운영 편의상 로컬 전용 publish를 유지하는 절충안이다

### 7.3 미반영

- SQLite 기존 데이터의 실제 이관 (`pgloader`, ETL 스크립트 등)
- Alembic 같은 정식 마이그레이션 체계
- ops-api용 실제 `/health` 엔드포인트 구현
- Caddy TLS(443) 운영
- Basic Auth 등 대시보드 보호 설정 활성화

즉 현재 상태는 "운영 베이스 1차 완성"이며, "데이터 이관 / 보안 강화 / 정식 마이그레이션"은 후속 범위다.

## 8) 운영 시 확인 포인트

배포 후 최소 확인 항목은 아래와 같다.

1. GitHub Actions `deploy_local`가 정상 종료되었는지
2. `qt-postgres` 컨테이너 healthcheck가 통과했는지
3. `qt-ops-api`, `qt-trader`, `qt-web`, `qt-caddy`가 모두 재기동되었는지
4. `docker exec qt-postgres pg_isready ...`가 성공하는지
5. `docker exec qt-postgres psql ... -c "\dt"`에서 기본 테이블이 생성되었는지
6. 웹 요청 시 `/api/logs`와 `/api/*`가 올바른 백엔드로 라우팅되는지

특히 PostgreSQL은 빈 볼륨에서 최초 기동 시 `initialize_database()` 호출 경로가 정상 동작해야 하므로, `ops-api` 또는 `trader` 중 하나라도 초기에 예외 없이 떠야 한다.

### 8.1 Docker context / 재생성 이슈 체크리스트

이번 작업 중 실제로 "compose config에는 ports가 보이는데 inspect에는 반영되지 않는" 유형의 문제가 있었다. 운영 중 compose 변경이 반영되지 않는 것처럼 보이면 아래 순서로 확인한다.

1. `docker context show`
2. `docker inspect qt-postgres --format "{{json .NetworkSettings.Ports}}"`
3. `docker compose --env-file .env.runtime config`
4. 필요 시 `docker compose --env-file .env.runtime down`
5. 필요 시 `docker compose --env-file .env.runtime up -d --force-recreate`

핵심은 "compose 파일 내용"과 "실제 떠 있는 컨테이너 설정"을 분리해서 확인하는 것이다.

## 9) 후속 권장 작업

운영 안정성 기준 우선순위는 아래 순서가 더 적절하다.

### 9.1 P0: 장애 방지 가드 + 헬스체크

1. `ops-api /health` 구현 후 compose healthcheck 활성화
2. `deploy_local`에서 필수 값 누락 시 fail-fast 처리

### 9.2 P1: 보안 최소선

1. Caddy Basic Auth 또는 IP allowlist 적용

### 9.3 P2: DB 운영 정책 확정

1. PostgreSQL host 바인딩 정책 결정 (`15432` 유지 vs 완전 내부화)
2. 기본 정책을 "비공개", 예외 정책을 "임시 localhost publish"로 문서화

### 9.4 P3: 데이터 이관 / 정식 마이그레이션

1. SQLite -> PostgreSQL 실제 데이터 이관 절차 수립
2. 정식 스키마 마이그레이션 도구(Alembic 등) 도입 검토

### 9.5 P4: 권한 정책 정리

1. GHCR 인증 정책 통일 (build/deploy 동일 계정 또는 동일 원칙)

## 10) 결론

이번 작업은 단순 설정 변경이 아니라, 다음 세 가지를 실제 운영 가능 상태로 만든 작업이다.

1. GitHub Actions + self-hosted runner 기반 자동 배포
2. Caddy + Compose 기반 멀티서비스 운영 구조
3. PostgreSQL을 기본 런타임 DB로 사용하는 초기 부팅 경로

다만 이는 "완전한 운영 고도화 완료"가 아니라, 인프라 1차 작업에서 제안한 방향을 실제 배포 가능한 수준으로 구현한 1차 운영화 단계로 보는 것이 맞다. 이후 단계에서는 데이터 이관, 접근통제, 정식 마이그레이션 체계가 이어져야 한다.
