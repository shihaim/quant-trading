# Quant Trading MVP

[Korean README](./README.ko.md)

Upbit spot trading MVP focused on safety-first operations:

- single-service architecture
- bar-close trigger with dynamic timeframe reload
- persistent order/fill/position state
- reconcile on startup and during runtime
- idempotent order keys and retry/recovery flow
- paper trading mode and local backtest CLI

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m trader.app.main
```

Local CLI/dev runs still fall back to `sqlite:///./trading.db` unless `DATABASE_URL` is set.
`docker-compose.yml` uses the bundled PostgreSQL service by default.

## Ops API (Dashboard MVP)

Run a lightweight local API server for operations dashboard integration:

```bash
python -m trader.app.ops_api --host 127.0.0.1 --port 8080
```

Available endpoints:

Auth and identity:

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/me` (requires `Authorization: Bearer <token>`)

User credential path:

- `GET /api/me/credentials/upbit` (requires `Authorization: Bearer <token>`)
- `POST /api/me/credentials/upbit` (requires `Authorization: Bearer <token>`)

User-scoped reads:

- `GET /api/me/orders?state=ERROR_NEEDS_REVIEW&limit=50` (requires `Authorization: Bearer <token>`)
- `GET /api/me/pnl/daily?days=30&tz=UTC` (requires `Authorization: Bearer <token>`)
- `GET /api/me/metrics/trade?limit=200` (requires `Authorization: Bearer <token>`)

User-scoped bot control:

- `GET /api/me/bot/status` (requires `Authorization: Bearer <token>`)
- `POST /api/me/bot/start` (requires `Authorization: Bearer <token>`)
- `POST /api/me/bot/stop` (requires `Authorization: Bearer <token>`)

Legacy ops compatibility paths:

- `GET /api/ops/summary`
- `GET /api/orders?state=ERROR_NEEDS_REVIEW&limit=50`
- `GET /api/pnl/daily?days=30&tz=UTC`
- `GET /api/metrics/trade?limit=200`
- `POST /api/bot/enable` (retired: returns `410 legacy_endpoint_retired`, use `/api/me/bot/start`)
- `POST /api/bot/disable` (retired: returns `410 legacy_endpoint_retired`, use `/api/me/bot/stop`)

For split frontend/backend deployment, allow CORS with:

- `OPS_API_ALLOW_ORIGIN` (default: `*`)

## Ops Dashboard Web (Separated Frontend)

Next.js frontend lives in `apps/web` and runs as a separate process.

For local frontend development, run it directly against the backend API:

```bash
python -m trader.app.ops_api --host 127.0.0.1 --port 8080
cd apps/web
npm install
npm run dev
```

Open:

- `http://127.0.0.1:3000`
- set `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080` for direct frontend dev

For Compose/Caddy deployment, open:

- `https://qt-dashboard.local`
- add a local hosts entry for `qt-dashboard.local` pointing to `127.0.0.1`
- leave `NEXT_PUBLIC_API_BASE_URL` empty to use same-origin `/api/*` routing through Caddy
- trust the Caddy local CA on your host OS if your browser warns about the certificate
- Caddy internal cert lifetime is configured in `infra/caddy/Caddyfile` as `2160h` (90 days)

On Windows (run PowerShell as Administrator), trust the local CA used by Caddy:

```powershell
docker cp qt-caddy:/data/caddy/pki/authorities/local/root.crt .\infra\caddy\root.crt
certutil -addstore -f Root .\infra\caddy\root.crt
```

Then restart Caddy and your browser:

```powershell
docker compose up -d --force-recreate caddy
```

## Modes

- `TRADE_MODE=PAPER` (default): no live order, simulated fills in DB
- `TRADE_MODE=REAL`: live Upbit order mode
- `TRADE_MODE=TEST`: calls `/v1/orders/test` only (no live order)
- `TRADE_MODE=SHADOW`: records validated order intent only (no exchange submit)

In `REAL/TEST/SHADOW` mode, both keys are required:

- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`

## Environment Variables

- `TRADE_MODE` (`PAPER`, `REAL`, `TEST`, `SHADOW`)
- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`
- `UPBIT_BASE_URL` (default: `https://api.upbit.com`)
- `DATABASE_URL` (local fallback: `sqlite:///./trading.db`, docker compose default: `postgresql+psycopg://trader:${POSTGRES_PASSWORD}@postgres:5432/trading`)
- `POLL_INTERVAL_SECONDS` (default: `1`)
- `CONFIG_RELOAD_SECONDS` (default: `15`)
- `MIN_STRATEGY_CANDLES` (default: `120`)
- `ORDER_RETRY_MAX` (default: `3`)
- `ORDER_RETRY_BACKOFF_SECONDS` (default: `0.8`)
- `DEFAULT_FEE_RATE` (default: `0.0005`)
- `PAPER_INITIAL_CASH_KRW` (default: `1000000`)
- `ENFORCE_MARKET_ALLOWLIST` (`true/false`, default: `false`)
- `ALLOWLIST_MARKETS` (JSON array, default: `['KRW-BTC']`)
- `REHEARSAL_ORDER_NOTIONAL_KRW` (default: `6000`)
- `TELEGRAM_BOT_TOKEN` (optional)
- `TELEGRAM_CHAT_ID` (optional)
- `OPS_API_ALLOW_ORIGIN` (default: `*`, separated frontend origin)
- `OPS_API_AUTH_SECRET` (default: `dev-ops-auth-secret-change-me`)
- `OPS_API_AUTH_TOKEN_TTL_SECONDS` (default: `43200`, 12h)
- `OPS_API_CREDENTIALS_ENCRYPTION_KEY` (default: `dev-ops-credentials-encryption-key-change-me`)
- `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, default: `INFO`)
- `LOG_DIR` (default: `logs`)
- `APP_INFO_LOG_FILE` (default: `application-info.log`, scheduler `INFO`/`WARNING`)
- `APP_ERROR_LOG_FILE` (default: `application-error.log`, scheduler `ERROR`/`CRITICAL`)
- `OPS_API_INFO_LOG_FILE` (default: `ops-api-info.log`, Ops API `INFO`/`WARNING`)
- `OPS_API_ERROR_LOG_FILE` (default: `ops-api-error.log`, Ops API `ERROR`/`CRITICAL`)
- `LOG_ROTATE_MAX_BYTES` (default: `10485760`, 10MB)
- `LOG_ROTATE_BACKUP_COUNT` (default: `10`)
- `WEB_LOG_DIR` (default: `./logs` from `apps/web` process cwd)
- `WEB_INFO_LOG_FILE` (default: `web-info.log`, frontend `INFO`/`WARNING`)
- `WEB_ERROR_LOG_FILE` (default: `web-error.log`, frontend `ERROR`)
- `WEB_LOG_LEVEL` (default: `LOG_LEVEL` or `INFO`)
- `WEB_LOG_ROTATE_MAX_BYTES` (default: `LOG_ROTATE_MAX_BYTES` or `10485760`)
- `WEB_LOG_ROTATE_BACKUP_COUNT` (default: `LOG_ROTATE_BACKUP_COUNT` or `10`)

## Runtime Config (DB)

The `bot_config` row with `id=1` is reloaded during runtime:

- `is_enabled`: emergency stop
- `timeframe`: `1m`, `3m`, `5m`, `15m`, `30m`, `60m`, `240m`, `day`
- `markets_json`: for example `['KRW-BTC', 'KRW-ETH']`
- `target_exposure_pct`: default target exposure ratio on buy signals (example: `0.15`)
- `daily_loss_basis`: `TOTAL` (default) or `REALIZED_ONLY`
- `max_daily_loss_pct`
- `max_weekly_loss_pct`
- `max_monthly_loss_pct`
- `max_total_exposure_pct`
- `max_per_market_exposure_pct`
- `min_rebalance_threshold_pct`: skip tiny exposure changes
- `min_order_krw_buffer`: extra KRW buffer above minimum notional
- `cooldown_hours_on_halt`: start-block cooldown window after risk halt (`0` disables cooldown)
- `max_new_orders_per_day`: per-user daily new-order limit (`0` disables limit)
- `max_orders_per_week`: per-user weekly order limit (`0` disables limit)
- `min_edge_pct`: BUY signal edge threshold (`0` disables filter)
- `fill_timeout_sec_entry`, `fill_timeout_sec_exit`, `fill_timeout_sec_rebalance`
- `max_reprice_attempts_entry`, `max_reprice_attempts_exit`, `max_reprice_attempts_rebalance`
- `reprice_step_bps`
- `slippage_budget_entry_pct`, `slippage_budget_exit_pct`
- `slippage_budget_breach_halt_count` (`0` disables auto-halt)
- `status_notify_interval_seconds`

Active timeframe is selected from `timeframe_config`:

- rows where `is_enabled=1` are candidates
- if multiple rows are enabled, scheduler reads one row with `LIMIT 1` (`ORDER BY id ASC`)

## Reconcile and Execution Safety

- account reconcile: `/v1/accounts` -> local `positions`
- open-order reconcile: `/v1/orders/open` -> local `orders`
- local open orders are re-synced with `/v1/order`
- new fills are inserted once and applied once (`fills.is_applied`)
- idempotency: one `client_order_id` per market/timeframe/candle/side
- submit recovery: if submit response is lost, re-query by `identifier`

## Backtest

Backtest uses candles already stored in local DB.

```bash
python -m trader.app.backtest --market KRW-BTC --timeframe 15m
```

Optional args:

- `--initial-cash` (default `1000000`)
- `--fee-rate` (default `0.0005`)
- `--slippage-bps` (default `5`)

## P1 Rehearsal

P1 smoke (read-only reconcile loop):

```bash
python -m trader.app.p1_rehearsal --scenario smoke --minutes 60 --interval 10
```

P1 order lifecycle (far-limit submit -> open -> cancel):

```bash
python -m trader.app.p1_rehearsal --scenario order-cancel --market KRW-BTC --distance-pct 0.05
```

Notes:

- `order-cancel` is intended for `TRADE_MODE=REAL` with ultra-small controlled setup
- enable `ENFORCE_MARKET_ALLOWLIST=true` to hard-block non-allowlist markets
- when switching runtime timeframe from `15m` to `5m`, consider `MIN_STRATEGY_CANDLES=360` to keep a similar lookback horizon

## P2 Policy

- PnL/risk-halt basis policy is documented in `docs/p2_design.md`.

## P3 Execution Policy

- `OrderPolicy` intents: `ENTRY`, `EXIT`, `REBALANCE`
- tiny rebalance gate and order-notional buffer run before submit
- opposite-side open orders are canceled first (conflict policy Option A)
- fill quality metrics are stored in `trade_metrics`
- slippage budget breaches trigger alerts and optional auto-halt
