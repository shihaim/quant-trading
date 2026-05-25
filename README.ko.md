# Quant Trading MVP

[English README](./README.md)

안전성을 최우선으로 설계한 Upbit 현물 자동매매 MVP입니다.

- 단일 서비스 아키텍처
- 동적 타임프레임 리로드가 가능한 봉 마감 트리거
- 주문/체결/포지션 상태 영속화
- 시작 시점 및 런타임 중 정합성(reconcile) 점검
- 멱등 주문 키 + 재시도/복구 흐름
- 모의투자(PAPER) 모드와 로컬 백테스트 CLI

## 빠른 시작

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m trader.app.main
```

로컬 CLI/개발 실행은 `DATABASE_URL`이 없으면 기본값 `sqlite:///./trading.db`를 사용합니다.
`docker-compose.yml`은 기본으로 번들 PostgreSQL 서비스를 사용합니다.

## 문서

- 현재 문서 지도는 `docs/README.md`에서 시작합니다.
- 매매 동작이나 불변식을 바꾸기 전에는 `docs/context_anchor.md`를 기준으로 확인합니다.
- 배포, DB 점검, 관리자 역할, 긴급 절차는 `docs/ops_runbook.md`를 기준으로 봅니다.
- Story/Task/Sub-task 계획의 기준은 Notion `Task`이며, 로컬 `/docs`는 운영 참고 문서, 인수인계, 런북, 보고서, 아카이브 용도입니다.

## Ops API (대시보드 MVP)

운영 대시보드 연동용 경량 로컬 API 서버를 실행합니다.

```bash
python -m trader.app.ops_api --host 127.0.0.1 --port 8080
```

사용 가능한 엔드포인트:

인증/식별:

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/me` (`Authorization: Bearer <token>` 필요)

사용자 자격증명 경로:

- `GET /api/me/credentials/upbit` (`Authorization: Bearer <token>` 필요)
- `POST /api/me/credentials/upbit` (`Authorization: Bearer <token>` 필요)

사용자 스코프 조회:

- `GET /api/me/overview` (`Authorization: Bearer <token>` 필요)
- `GET /api/me/orders?state=ERROR_NEEDS_REVIEW&limit=50` (`Authorization: Bearer <token>` 필요)
- `GET /api/me/pnl/daily?days=30&tz=UTC` (`Authorization: Bearer <token>` 필요)
- `GET /api/me/metrics/trade?limit=200` (`Authorization: Bearer <token>` 필요)

사용자 스코프 Bot 제어:

- `GET /api/me/bot/status` (`Authorization: Bearer <token>` 필요)
- `POST /api/me/bot/start` (`Authorization: Bearer <token>` 필요)
- `POST /api/me/bot/stop` (`Authorization: Bearer <token>` 필요)

레거시 운영 호환 경로:

- `GET /api/ops/summary`
- `GET /api/orders?state=ERROR_NEEDS_REVIEW&limit=50`
- `GET /api/pnl/daily?days=30&tz=UTC`
- `GET /api/metrics/trade?limit=200`
- `POST /api/bot/enable` (종료됨: `410 legacy_endpoint_retired` 반환, `/api/me/bot/start` 사용)
- `POST /api/bot/disable` (종료됨: `410 legacy_endpoint_retired` 반환, `/api/me/bot/stop` 사용)

프론트/백엔드 분리 배포 시 CORS 허용:

- `OPS_API_ALLOW_ORIGIN` (기본값: `*`)

## Ops Dashboard Web (분리형 프론트엔드)

Next.js 프론트엔드는 `apps/web`에 있으며 백엔드와 별도 프로세스로 실행됩니다.

로컬 프론트 개발 시 백엔드 API에 직접 연결해 실행합니다.

```bash
python -m trader.app.ops_api --host 127.0.0.1 --port 8080
cd apps/web
npm install
npm run dev
```

접속:

- `http://127.0.0.1:3000`
- 직접 개발 연결 시 `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080` 설정

Compose/Caddy 배포 경로:

- `https://qt-dashboard.local`
- `qt-dashboard.local`이 `127.0.0.1`을 가리키도록 hosts에 추가
- Caddy same-origin `/api/*` 라우팅을 사용하려면 `NEXT_PUBLIC_API_BASE_URL`은 비움
- 브라우저 인증서 경고 시 OS에 Caddy 로컬 CA를 신뢰 처리
- Caddy 내부 인증서 수명은 `infra/caddy/Caddyfile`의 `2160h`(90일)

Windows에서는 PowerShell을 관리자 권한으로 실행 후 로컬 CA를 신뢰 처리합니다.

```powershell
docker cp qt-caddy:/data/caddy/pki/authorities/local/root.crt .\infra\caddy\root.crt
certutil -addstore -f Root .\infra\caddy\root.crt
```

이후 Caddy와 브라우저를 재시작합니다.

```powershell
docker compose up -d --force-recreate caddy
```

## 모드

- `TRADE_MODE=PAPER` (기본): 실거래 주문 없음, DB에 모의 체결 반영
- `TRADE_MODE=REAL`: Upbit 실거래 주문 모드
- `TRADE_MODE=TEST`: `/v1/orders/test`만 호출 (실거래 없음)
- `TRADE_MODE=SHADOW`: 검증된 주문 의도만 기록 (거래소 제출 없음)

`REAL/TEST/SHADOW` 모드에서는 아래 키 2개가 모두 필요합니다.

V3 멀티유저 운영에서는 전역 `UPBIT_ACCESS_KEY`/`UPBIT_SECRET_KEY`를 `.env.runtime`에 두지 않습니다.
사용자별 Upbit 키는 로그인 후 `/api/me/credentials/upbit` 경로로 저장하며, 런타임은 DB의 `user_exchange_credentials`에서 사용자별 credential을 읽습니다.

## 환경 변수

- `TRADE_MODE` (`PAPER`, `REAL`, `TEST`, `SHADOW`)
- `UPBIT_BASE_URL` (기본값: `https://api.upbit.com`)
- `DATABASE_URL` (로컬 기본값: `sqlite:///./trading.db`, docker compose 기본값: `postgresql+psycopg://trader:${POSTGRES_PASSWORD}@postgres:5432/trading`)
- `POLL_INTERVAL_SECONDS` (기본값: `1`)
- `CONFIG_RELOAD_SECONDS` (기본값: `15`)
- `MIN_STRATEGY_CANDLES` (기본값: `120`)
- `ORDER_RETRY_MAX` (기본값: `3`)
- `ORDER_RETRY_BACKOFF_SECONDS` (기본값: `0.8`)
- `DEFAULT_FEE_RATE` (기본값: `0.0005`)
- `PAPER_INITIAL_CASH_KRW` (기본값: `1000000`)
- `ENFORCE_MARKET_ALLOWLIST` (`true/false`, 기본값: `false`)
- `ALLOWLIST_MARKETS` (JSON 배열, 기본값: `['KRW-BTC']`)
- `REHEARSAL_ORDER_NOTIONAL_KRW` (기본값: `6000`)
- `TELEGRAM_BOT_TOKEN` (선택)
- `TELEGRAM_CHAT_ID` (선택)
- `OPS_API_ALLOW_ORIGIN` (기본값: `*`, 분리형 프론트 출처 허용)
- `OPS_API_AUTH_SECRET` (기본값: `dev-ops-auth-secret-change-me`)
- `OPS_API_AUTH_TOKEN_TTL_SECONDS` (기본값: `43200`, 12시간)
- `OPS_API_CREDENTIALS_ENCRYPTION_KEY` (기본값: `dev-ops-credentials-encryption-key-change-me`)
- `OPS_API_CREDENTIALS_ACTIVE_KEY_VERSION` (기본값: `v1`)
- `OPS_API_CREDENTIALS_KEYRING_JSON` (credential key rotation용 JSON)
- `OPS_API_BUDGET_WINDOW_SECONDS` (기본값: `60`)
- `OPS_API_BUDGET_ME_LIMIT` (기본값: `120`)
- `OPS_API_BUDGET_ADMIN_LIMIT` (기본값: `300`)
- `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, 기본값: `INFO`)
- `LOG_DIR` (기본값: `logs`)
- `APP_INFO_LOG_FILE` (기본값: `application-info.log`, 스케줄러 `INFO`/`WARNING`)
- `APP_ERROR_LOG_FILE` (기본값: `application-error.log`, 스케줄러 `ERROR`/`CRITICAL`)
- `OPS_API_INFO_LOG_FILE` (기본값: `ops-api-info.log`, Ops API `INFO`/`WARNING`)
- `OPS_API_ERROR_LOG_FILE` (기본값: `ops-api-error.log`, Ops API `ERROR`/`CRITICAL`)
- `LOG_ROTATE_MAX_BYTES` (기본값: `10485760`, 10MB)
- `LOG_ROTATE_BACKUP_COUNT` (기본값: `10`)
- `WEB_LOG_DIR` (기본값: `./logs`, `apps/web` 프로세스 cwd 기준)
- `WEB_INFO_LOG_FILE` (기본값: `web-info.log`, 프론트 `INFO`/`WARNING`)
- `WEB_ERROR_LOG_FILE` (기본값: `web-error.log`, 프론트 `ERROR`)
- `WEB_LOG_LEVEL` (기본값: `LOG_LEVEL` 또는 `INFO`)
- `WEB_LOG_ROTATE_MAX_BYTES` (기본값: `LOG_ROTATE_MAX_BYTES` 또는 `10485760`)
- `WEB_LOG_ROTATE_BACKUP_COUNT` (기본값: `LOG_ROTATE_BACKUP_COUNT` 또는 `10`)

## 런타임 설정 (DB)

`id=1`인 `bot_config` 행은 런타임 중 재로딩됩니다.

- `is_enabled`: 긴급 중지
- `timeframe`: `1m`, `3m`, `5m`, `15m`, `30m`, `60m`, `240m`, `day`
- `markets_json`: 예: `['KRW-BTC', 'KRW-ETH']`
- `target_exposure_pct`: 매수 시그널 기본 목표 익스포저 비율 (예: `0.15`)
- `daily_loss_basis`: `TOTAL`(기본) 또는 `REALIZED_ONLY`
- `max_daily_loss_pct`
- `max_weekly_loss_pct`
- `max_monthly_loss_pct`
- `max_total_exposure_pct`
- `max_per_market_exposure_pct`
- `min_rebalance_threshold_pct`: 너무 작은 익스포저 변경은 건너뜀
- `min_order_krw_buffer`: 최소 주문 금액 대비 추가 KRW 버퍼
- `cooldown_hours_on_halt`: 리스크 중단 이후 재시작 차단 시간 (`0`이면 비활성)
- `max_new_orders_per_day`: 사용자별 일일 신규 주문 한도 (`0`이면 비활성)
- `max_orders_per_week`: 사용자별 주간 주문 한도 (`0`이면 비활성)
- `min_edge_pct`: BUY 시그널 최소 엣지 필터 (`0`이면 비활성)
- `fill_timeout_sec_entry`, `fill_timeout_sec_exit`, `fill_timeout_sec_rebalance`
- `max_reprice_attempts_entry`, `max_reprice_attempts_exit`, `max_reprice_attempts_rebalance`
- `reprice_step_bps`
- `slippage_budget_entry_pct`, `slippage_budget_exit_pct`
- `slippage_budget_breach_halt_count` (`0`이면 자동중지 비활성)
- `status_notify_interval_seconds`

활성 타임프레임은 `timeframe_config`에서 선택됩니다.

- `is_enabled=1`인 행이 후보
- 여러 행이 활성화되어 있으면 스케줄러가 `LIMIT 1`(`ORDER BY id ASC`)로 1개를 읽음

## 정합성 및 실행 안전장치

- 계좌 정합성 점검: `/v1/accounts` -> 로컬 `positions`
- 미체결 주문 정합성 점검: `/v1/orders/open` -> 로컬 `orders`
- 로컬 미체결 주문은 `/v1/order`로 재동기화
- 신규 체결은 1회 삽입 + 1회 반영 (`fills.is_applied`)
- 멱등성: 시장/타임프레임/캔들/사이드별 `client_order_id` 1개
- 제출 복구: 제출 응답 유실 시 `identifier`로 재조회

## 백테스트

백테스트는 로컬 DB에 저장된 캔들을 사용합니다.

```bash
python -m trader.app.backtest --market KRW-BTC --timeframe 15m
```

선택 인자:

- `--initial-cash` (기본값 `1000000`)
- `--fee-rate` (기본값 `0.0005`)
- `--slippage-bps` (기본값 `5`)

## P1 리허설

P1 스모크 테스트(읽기 전용 reconcile 루프):

```bash
python -m trader.app.p1_rehearsal --scenario smoke --minutes 60 --interval 10
```

P1 주문 라이프사이클(먼 가격 지정가 제출 -> 미체결 -> 취소):

```bash
python -m trader.app.p1_rehearsal --scenario order-cancel --market KRW-BTC --distance-pct 0.05
```

참고:

- `order-cancel`은 매우 작은 통제 조건의 `TRADE_MODE=REAL` 테스트 용도
- `ENFORCE_MARKET_ALLOWLIST=true` 설정 시 허용 목록 외 시장을 강제 차단
- 런타임 타임프레임을 `15m`에서 `5m`로 변경할 때 유사한 룩백 범위를 원하면 `MIN_STRATEGY_CANDLES=360` 권장

## P2 정책

- PnL/리스크 중단 기준 정책은 `docs/archive/p2_design.md`에 보관되어 있습니다.

## P3 실행 정책

- `OrderPolicy` 의도: `ENTRY`, `EXIT`, `REBALANCE`
- 작은 리밸런스 게이트와 주문 금액 버퍼를 제출 전에 적용
- 반대 방향 미체결 주문을 먼저 취소 (충돌 정책 Option A)
- 체결 품질 메트릭을 `trade_metrics`에 저장
- 슬리피지 예산 초과 시 경고 및 선택적 자동 중지
