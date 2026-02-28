# Quant Trading MVP

[English README](./README.md)

안전성을 최우선으로 두는 Upbit 현물 트레이딩 MVP입니다.

- 단일 서비스 아키텍처
- 동적 타임프레임 재로딩이 가능한 봉 마감 트리거
- 주문/체결/포지션 상태 영속화
- 시작 시점 및 실행 중 정합성(reconcile) 점검
- 멱등 주문 키와 재시도/복구 흐름
- 모의 투자 모드 및 로컬 백테스트 CLI

## 빠른 시작

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m trader.app.main
```

로컬 CLI/개발 실행은 `DATABASE_URL`이 설정되지 않으면 기본적으로 `sqlite:///./trading.db`를 사용합니다.
`docker-compose.yml`은 기본적으로 포함된 PostgreSQL 서비스를 사용합니다.

## Ops API (대시보드 MVP)

운영 대시보드 연동용 경량 로컬 API 서버를 실행합니다.

```bash
python -m trader.app.ops_api --host 127.0.0.1 --port 8080
```

사용 가능한 엔드포인트:

- `GET /api/ops/summary`
- `GET /api/orders?state=ERROR_NEEDS_REVIEW&limit=50`
- `GET /api/pnl/daily?days=30&tz=UTC`
- `GET /api/metrics/trade?limit=200`
- `POST /api/bot/enable`
- `POST /api/bot/disable`

프론트엔드/백엔드를 분리 배포할 경우, 다음 설정으로 CORS를 허용할 수 있습니다.

- `OPS_API_ALLOW_ORIGIN` (기본값: `*`)

## Ops Dashboard Web (분리된 프론트엔드)

Next.js 프론트엔드는 `apps/web`에 있으며 별도 프로세스로 실행됩니다.

```bash
python -m trader.app.ops_api --host 127.0.0.1 --port 8080
cd apps/web
npm install
npm run dev
```

접속:

- `http://127.0.0.1:3000`
- 백엔드 엔드포인트는 `NEXT_PUBLIC_API_BASE_URL`로 설정합니다 (기본값: `http://127.0.0.1:8080`)

## 모드

- `TRADE_MODE=PAPER` (기본값): 실제 주문 없이 DB에 모의 체결만 기록
- `TRADE_MODE=REAL`: Upbit 실제 주문 모드
- `TRADE_MODE=TEST`: `/v1/orders/test`만 호출 (실제 주문 없음)
- `TRADE_MODE=SHADOW`: 검증된 주문 의도만 기록 (거래소 제출 없음)

`REAL/TEST/SHADOW` 모드에서는 아래 두 키가 모두 필요합니다.

- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`

## 환경 변수

- `TRADE_MODE` (`PAPER`, `REAL`, `TEST`, `SHADOW`)
- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`
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
- `ALLOWLIST_MARKETS` (JSON 배열, 기본값: `["KRW-BTC"]`)
- `REHEARSAL_ORDER_NOTIONAL_KRW` (기본값: `6000`)
- `TELEGRAM_BOT_TOKEN` (선택)
- `TELEGRAM_CHAT_ID` (선택)
- `OPS_API_ALLOW_ORIGIN` (기본값: `*`, 분리된 프론트엔드 출처용)
- `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, 기본값: `INFO`)
- `LOG_DIR` (기본값: `logs`)
- `APP_INFO_LOG_FILE` (기본값: `application-info.log`, 스케줄러 `INFO`/`WARNING`)
- `APP_ERROR_LOG_FILE` (기본값: `application-error.log`, 스케줄러 `ERROR`/`CRITICAL`)
- `OPS_API_INFO_LOG_FILE` (기본값: `ops-api-info.log`, Ops API `INFO`/`WARNING`)
- `OPS_API_ERROR_LOG_FILE` (기본값: `ops-api-error.log`, Ops API `ERROR`/`CRITICAL`)
- `LOG_ROTATE_MAX_BYTES` (기본값: `10485760`, 10MB)
- `LOG_ROTATE_BACKUP_COUNT` (기본값: `10`)
- `WEB_LOG_DIR` (기본값: `./logs`, `apps/web` 프로세스 현재 작업 디렉터리 기준 프론트엔드 파일 로그)
- `WEB_INFO_LOG_FILE` (기본값: `web-info.log`, 프론트엔드 `INFO`/`WARNING`)
- `WEB_ERROR_LOG_FILE` (기본값: `web-error.log`, 프론트엔드 `ERROR`)
- `WEB_LOG_LEVEL` (기본값: `LOG_LEVEL` 또는 `INFO`)
- `WEB_LOG_ROTATE_MAX_BYTES` (기본값: `LOG_ROTATE_MAX_BYTES` 또는 `10485760`)
- `WEB_LOG_ROTATE_BACKUP_COUNT` (기본값: `LOG_ROTATE_BACKUP_COUNT` 또는 `10`)

## 런타임 설정 (DB)

`id=1`인 `bot_config` 행은 실행 중에도 다시 로드됩니다.

- `is_enabled`: 긴급 중지
- `timeframe`: `1m`, `3m`, `5m`, `15m`, `30m`, `60m`, `240m`, `day`
- `markets_json`: 예: `["KRW-BTC","KRW-ETH"]`
- `target_exposure_pct`: 매수 기준 기본 목표 비중 (예: `0.15`)
- `daily_loss_basis`: `TOTAL` (기본값) 또는 `REALIZED_ONLY`
- `max_daily_loss_pct`
- `max_total_exposure_pct`
- `max_per_market_exposure_pct`
- `min_rebalance_threshold_pct`: 아주 작은 익스포저 변화는 건너뜀
- `min_order_krw_buffer`: 최소 주문 금액 위에 추가로 확보할 KRW 버퍼
- `fill_timeout_sec_entry`, `fill_timeout_sec_exit`, `fill_timeout_sec_rebalance`
- `max_reprice_attempts_entry`, `max_reprice_attempts_exit`, `max_reprice_attempts_rebalance`
- `reprice_step_bps`
- `slippage_budget_entry_pct`, `slippage_budget_exit_pct`
- `slippage_budget_breach_halt_count` (`0`이면 자동 중지 비활성화)
- `status_notify_interval_seconds`

활성 타임프레임은 `timeframe_config`에서 선택됩니다.

- `is_enabled=1`인 행이 후보입니다.
- 여러 행이 활성화되어 있으면 스케줄러는 `LIMIT 1`로 한 행만 읽습니다 (`ORDER BY id ASC`).

## 정합성 점검과 실행 안전성

- 계좌 정합성 점검: `/v1/accounts` -> 로컬 `positions`
- 미체결 주문 정합성 점검: `/v1/orders/open` -> 로컬 `orders`
- 로컬 미체결 주문은 `/v1/order`로 다시 동기화
- 새로운 체결은 한 번만 삽입되고 한 번만 적용됨 (`fills.is_applied`)
- 멱등성: 시장/타임프레임/캔들/사이드별 `client_order_id` 하나만 사용
- 주문 제출 복구: 제출 응답을 잃어버린 경우 `identifier`로 재조회

## 백테스트

백테스트는 로컬 DB에 이미 저장된 캔들을 사용합니다.

```bash
python -m trader.app.backtest --market KRW-BTC --timeframe 15m
```

선택 인자:

- `--initial-cash` (기본값 `1000000`)
- `--fee-rate` (기본값 `0.0005`)
- `--slippage-bps` (기본값 `5`)

## P1 리허설

P1 스모크 테스트 (읽기 전용 정합성 점검 루프):

```bash
python -m trader.app.p1_rehearsal --scenario smoke --minutes 60 --interval 10
```

P1 주문 생명주기 (먼 가격 지정가 제출 -> 미체결 -> 취소):

```bash
python -m trader.app.p1_rehearsal --scenario order-cancel --market KRW-BTC --distance-pct 0.05
```

참고:

- `order-cancel`은 매우 작은 통제된 설정에서 `TRADE_MODE=REAL`로 실행하는 용도입니다.
- `ENFORCE_MARKET_ALLOWLIST=true`를 활성화하면 허용 목록 외 시장을 강제로 차단합니다.
- 런타임 타임프레임을 `15m`에서 `5m`로 바꿀 때는 비슷한 룩백 구간 유지를 위해 `MIN_STRATEGY_CANDLES=360`을 고려하세요.

## P2 정책

- PnL/리스크 중단 기준 정책은 `docs/p2_design.md`에 정리되어 있습니다.

## P3 실행 정책

- `OrderPolicy` 의도: `ENTRY`, `EXIT`, `REBALANCE`
- 작은 리밸런싱 차단 로직과 주문 금액 버퍼를 주문 제출 전에 적용
- 반대 방향의 미체결 주문을 먼저 취소함 (충돌 정책 Option A)
- 체결 품질 메트릭은 `trade_metrics`에 저장
- 슬리피지 예산 초과 시 경고를 발생시키고, 선택적으로 자동 중지 가능
