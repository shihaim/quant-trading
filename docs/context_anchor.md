# Quant Trading Context Anchor

Last verified: 2026-05-18

This is the canonical working context for coding agents and reviewers. Read it before changing trading behavior, runtime ownership, multi-user scope, credentials, reconciliation, PnL, risk, or Ops API contracts.

Use `docs/context_anchor_v3_transition.md` only when you need deeper historical V3 transition details, old backlog guardrails, or compatibility-removal context.

## When To Read

Read this file first for changes touching:

- scheduler flow, order execution, reconcile, fills, PnL, risk, runtime config
- `orders`, `order_attempts`, `fills`, `positions`, `daily_equity`, `paper_wallet`
- `user_bot_config`, `user_bot_runtime`, `user_risk_guard`, user credentials
- `/api/me/*`, `/api/admin/*`, Ops API behavior, auth/session/admin boundaries
- database schema, migration, backfill, or runtime ownership semantics

Usually skip it for:

- purely presentational frontend copy/style changes
- docs-only cleanup that does not change runtime meaning
- local cache/build artifact cleanup

## Current Architecture

- Product: Upbit spot trading MVP with safety-first live operation.
- Runtime: `MultiUserTradingScheduler` coordinates active users; `TradingScheduler` executes one user tick.
- Backend package: `trader/`
- Frontend: `apps/web`
- Ops API: `python -m trader.app.ops_api`
- Trader entrypoint: `python -m trader.app.main`
- Backtest entrypoint: `python -m trader.app.backtest`
- Docker operation uses `.env.runtime` by default through `deploy.ps1` and `docker-compose.yml`.

## Runtime Sources Of Truth

- Runtime config: per-user `user_bot_config`.
- Runtime status/control: per-user `user_bot_runtime`.
- Risk guard: per-user `user_risk_guard`.
- Exchange credentials: per-user encrypted `user_exchange_credentials`.
- Admin role: `users.is_admin`.
- Session revocation: monotonic `users.token_version`.
- Trading/accounting records: user-scoped tables and queries.

Do not reintroduce these as normal runtime dependencies:

- global `bot_config(id=1)` fallback
- env-based admin allowlist
- env-level global Upbit API key for normal multi-user runtime
- owner bridge for authenticated `/api/me/*` reads

`legacy_user_id` is migration/backfill-only. It attributes pre-V3 single-bot rows that had no `user_id`; it is not a default runtime user.

## Trading Modes

- `PAPER`: local simulated execution; no live exchange submit.
- `REAL`: live Upbit submit and exchange-backed lifecycle.
- `TEST`: Upbit test-order path; no live order.
- `SHADOW`: validation and intent record only; no exchange submit.

Rules:

- `REAL`, `TEST`, and `SHADOW` require credentials for the active user.
- Do not assume non-paper users share one exchange account.
- Do not confuse `PAPER` immediate fill semantics with real-mode asynchronous exchange lifecycle.

## Multi-User Invariants

These are hard constraints:

1. Do not mix data across users.
2. One user's failure must not halt or corrupt another user's runtime.
3. Runtime control is per user, not global.
4. Idempotency and reconciliation are evaluated within the same user scope.
5. Normal credential loading is per user.
6. `/api/me/*` reads and writes use authenticated user identity.
7. User-specific admin reads must include an explicit target user.
8. Non-admin users must not access `/ops` or `/api/admin/*`.

## Scheduler Tick Contract

For each due user tick:

1. Load `RuntimeConfig` with `ConfigRepo.load_for_user(user_id)`.
2. Backfill/upsert complete candles for configured markets.
3. Use the last complete candle close as mark/reference price.
4. Build a portfolio snapshot:
   - `PAPER`: local paper wallet and local positions for that user.
   - non-paper: Upbit account reconcile for that user.
5. Update that user's daily PnL snapshot.
6. Evaluate strategy.
7. Apply risk policy and runtime guardrails.
8. Skip when rebalance delta or notional is below configured thresholds.
9. Place/sync/apply fills inside the same user scope.
10. Apply slippage-budget halt only to the impacted user.

Scheduled-order idempotency:

- Base key: `"{timeframe}-{market}-{last_complete_candle_time_utc}"`
- `client_order_id`: `"u{user_id}-" + sanitized(base_key) + "-" + side`
- The same candle, market, and side must not create duplicate logical orders within the same user scope.

## Strategy And Risk

Current strategy: `EmaCrossStrategy`.

- Fast EMA: `20`
- Slow EMA: `60`
- Minimum candles: `slow + 5`
- `fast_ema > slow_ema` -> `BUY`
- otherwise -> `SELL`
- BUY target exposure is set from runtime config.

Risk policy may halt or reduce exposure based on:

- bot disabled
- daily, weekly, or monthly loss limits
- daily/weekly order-count limits
- total/per-market exposure caps
- minimum signal edge
- rebalance threshold
- minimum order notional plus buffer

Risk halts must be per-user and observable through runtime status/halt reason.

## Runtime Config Rules

Runtime config must be sanitized before use:

- invalid timeframe -> `15m`
- `daily_loss_basis` only `TOTAL` or `REALIZED_ONLY`
- timeouts clamped to `1..120`
- reprice attempts clamped to `1..10`
- `reprice_step_bps` clamped to `1..500`
- notify interval clamped to `300..86400`
- exposure/risk percentages clamped to safe ranges

Important fields:

- `target_exposure_pct`
- `max_total_exposure_pct`
- `max_per_market_exposure_pct`
- `daily_loss_basis`
- `min_rebalance_threshold_pct`
- `min_order_krw_buffer`
- `fill_timeout_sec_entry`, `fill_timeout_sec_exit`, `fill_timeout_sec_rebalance`
- `max_reprice_attempts_*`
- `slippage_budget_*`
- `max_weekly_loss_pct`, `max_monthly_loss_pct`
- `cooldown_hours_on_halt`
- `max_new_orders_per_day`, `max_orders_per_week`
- `min_edge_pct`

## Order And Exchange Invariants

Do not break:

- price, volume, tick-size, and minimum-notional validation
- market allowlist local rejection before exchange submit
- one logical order with multiple attempts
- one-time `upbit_identifier` values per attempt
- identifier-based recovery after ambiguous submit
- opposite-side open-order conflict handling
- transition of partially executed open orders to `PARTIAL`
- no blind resubmission after submit uncertainty

Local open states:

- `NEW`
- `SENT`
- `OPEN`
- `PARTIAL`
- `WAIT`

Terminal/special states:

- `FILLED`
- `CANCELED`
- `REJECTED`
- `ERROR_NEEDS_REVIEW`
- `TEST_OK`
- `SHADOW`

Upbit mapping:

- `wait` -> `OPEN`
- `watch` -> `OPEN`
- `done` -> `FILLED`
- `cancel` -> `CANCELED`

## Reconcile, Fill, And PnL Invariants

- Reconcile must operate inside the correct user boundary.
- Upbit account data must not overwrite another user's local state.
- Missing local records may be recovered only for the correct user/account context.
- Fill ingestion must be idempotent.
- The same exchange fill/trade id must be applied once.
- Applied fills update position quantity, average price, realized PnL, and wallet/accounting state.
- Daily equity is user-scoped and keyed by UTC date.
- Unrealized PnL uses mark/reference price; average buy price fallback is acceptable when mark is missing.
- Do not aggregate unrelated users' equity/PnL unless the endpoint explicitly asks for aggregate admin reporting.

## Ops API Contracts

Current important contracts:

- `/api/me/*`: authenticated user's credentials, orders, PnL, metrics, bot status/start/stop.
- `/api/admin/users/{user_id}/*`: admin per-user reads and operations.
- `GET /api/admin/users/runtime-summary`: aggregate admin runtime summary.
- `GET /api/admin/audit/logs`: admin audit query with bounded filters.
- `POST /api/admin/users/{user_id}/sessions/invalidate`: admin session invalidation.
- `POST /api/admin/users/{user_id}/role`: DB-backed role change with `token_version` bump.
- retired compatibility aliases return `410 legacy_endpoint_retired` with replacement metadata.

Maintain:

- `/api/me/*` must never depend on an owner bridge.
- `/api/admin/*` must preserve admin-only boundaries.
- Role changes must invalidate existing sessions predictably.
- Sensitive secrets must not be exposed in API/UI/log payloads.

## Operational Notes

- Upbit `401 Unauthorized` in non-paper modes usually means invalid key, missing permission, deleted key, or IP allowlist mismatch.
- If stored credential decryption fails, the app should surface a local credential error before reaching Upbit.
- `.env.runtime` should contain runtime platform secrets and credential encryption keys, not per-user Upbit API keys.
- Changing `OPS_API_CREDENTIALS_ENCRYPTION_KEY`, active key version, or keyring can make stored credentials unreadable unless rotation is handled deliberately.

## Development Workflow

Before patching behavior:

1. Read this anchor.
2. Inspect the narrow code paths involved.
3. State the invariant(s) that must remain true.
4. Add or update focused tests when behavior changes.
5. Patch narrowly.
6. Run verification and report the exact commands.
7. Update runbooks/Notion mapping when the operational contract changes.

Good prompt shape:

> Read `docs/context_anchor.md`, then inspect the scheduler, execution, and reconcile files involved. Preserve no cross-user mixing, fill idempotency, identifier-based recovery, and per-user failure isolation while fixing the issue.
