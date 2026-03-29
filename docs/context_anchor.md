# Quant Trading MVP Context Anchor

Last verified: 2026-03-22
Verified against: `trader/config/settings.py`, `trader/config/config_repo.py`, `trader/trading/scheduler.py`, `trader/trading/strategy.py`, `trader/trading/risk.py`, `trader/trading/execution.py`, `trader/trading/reconcile.py`, `trader/trading/order_policy.py`, `trader/data/models.py`, `trader/api/ops_http.py`, `trader/auth/guard.py`, `trader/auth/tokens.py`, `trader/me/read_service.py`, `trader/ops/service.py`, `trader/audit/service.py`, `trader/release_gate.py`, `trader/app/main.py`, `scripts/run_release_gate.py`, `scripts/audit_upbit_credential_coverage.py`

## Quick routing

Read this file first when the task changes any of these:
- trading logic, scheduler flow, order execution, reconcile, fills, PnL, runtime config, risk, Ops API behavior
- DB invariants for `orders`, `order_attempts`, `fills`, `positions`, `daily_equity`, `paper_wallet`, `user_bot_config`, `user_bot_runtime`, `user_risk_guard`, `bot_config`

This file is usually not needed for:
- simple UI text/style work in `apps/web`
- isolated README/docs cleanup with no behavior change
- non-trading utility refactors that do not touch order/accounting/runtime semantics

Use this document as the stable invariant source for Codex/LLM-assisted work on this repo.

## 1. Project shape

- Project type: Upbit spot trading MVP.
- Architecture: multi-user trading scheduler + per-user execution worker + separate Ops API + separate Next.js dashboard frontend.
- Main Python package: `trader/`
- Frontend: `apps/web`
- Primary runtime entrypoints:
  - `python -m trader.app.main`
  - `python -m trader.app.ops_api`
  - `python -m trader.app.backtest`

## 2. Trading modes

`TRADE_MODE` supports:

- `PAPER`: default; no live exchange submit. Orders are inserted as immediately `FILLED` and a synthetic fill is created.
- `REAL`: live Upbit order submit.
- `TEST`: calls Upbit `/v1/orders/test`; stores ledger result as `TEST_OK`; no live order.
- `SHADOW`: validates and records intent only; no exchange submit; order state becomes `SHADOW`.

Important:

- `REAL`, `TEST`, `SHADOW` require Upbit credentials.
- Local CLI/dev falls back to `sqlite:///./trading.db` if `DATABASE_URL` is unset.
- Docker Compose defaults to PostgreSQL.
- Do not confuse `PAPER` immediate local fill semantics with real-mode asynchronous lifecycle.

## 3. Core scheduler loop

The scheduler loop lives in `trader/trading/scheduler.py`.

Current runtime shape:

- `MultiUserTradingScheduler` coordinates active users and runs per-user ticks with lock-based isolation.
- `TradingScheduler` executes one user tick.

Per due tick for one user, the scheduler does this:

1. Load runtime config from DB using `load_for_user(user_id)`.
2. For each configured market:
   - backfill candles,
   - upsert latest complete candle,
   - load recent candles,
   - use the last complete candle close as mark/reference price.
3. Build portfolio snapshot:
   - `PAPER`: from that user's local wallet + local positions.
   - non-paper: via reconcile against that user's Upbit account.
4. Update daily PnL snapshot for that user.
5. Evaluate strategy signal.
6. Apply risk engine.
7. Skip rebalance if below threshold.
8. Skip order if notional is below `5000 KRW + min_order_krw_buffer`.
9. Place, sync, and apply fills within that user scope.
10. Check slippage budget breach and optionally auto-halt that user's runtime.

Scheduled-order idempotency key:

- `"{timeframe}-{market}-{last_complete_candle_time_utc}"`
- `client_order_id = "u{user_id}-" + sanitized(idempotency_key) + "-" + side`
- Same candle, market, and side must not create duplicate logical orders within the same user scope.

## 4. Strategy and risk rules

### Strategy

Current strategy is `EmaCrossStrategy`.

- Fast EMA = 20
- Slow EMA = 60
- Requires at least `slow + 5` candles.
- `fast_ema > slow_ema` => `BUY`
- else => `SELL`
- BUY target exposure defaults to `0.10`, but scheduler overwrites it from runtime config.

### Risk engine

Risk engine output is the final allowed target exposure.

Hard guards:

- If bot is disabled: halt, target exposure = `0`.
- If daily PnL pct <= `-abs(max_daily_loss_pct)`: halt, target exposure = `0`.
- If weekly PnL pct <= `-abs(max_weekly_loss_pct)` (when configured): halt, target exposure = `0`.
- If monthly PnL pct <= `-abs(max_monthly_loss_pct)` (when configured): halt, target exposure = `0`.
- If `new_orders_today >= max_new_orders_per_day` (when configured): halt, target exposure = `0`.
- If `orders_this_week >= max_orders_per_week` (when configured): halt, target exposure = `0`.

Exposure logic:

- BUY or hold exposure is capped by:
  - `signal.target_exposure_pct`
  - `max_per_market_exposure_pct`
  - `max_total_exposure_pct`
- SELL forces target exposure to `0`.

Gates:

- Skip rebalance if `abs(target_exposure_pct - current_exposure_pct) < min_rebalance_threshold_pct`.
- Skip BUY if signal edge pct is below `min_edge_pct` (filter only, no runtime halt).
- Skip if order notional < `5000 KRW + min_order_krw_buffer`.

## 5. Runtime config invariants

Runtime config is loaded from DB, not only env.

### Bot config source

- Primary source: `user_bot_config` row for the active `user_id`
- Fallback source: global `bot_config.id = 1` when user row is missing
- Active timeframe source: first enabled row from `timeframe_config` ordered by `id ASC`
- If selected timeframe is invalid, fallback to `15m`
- Runtime enable/status source: `user_bot_runtime` per user
- Risk guard source: `user_risk_guard` per user

### Important runtime fields

- `is_enabled`
- `timeframe`
- `markets_json`
- `target_exposure_pct`
- `daily_loss_basis`: `TOTAL` or `REALIZED_ONLY`
- `max_daily_loss_pct`
- `max_weekly_loss_pct`
- `max_monthly_loss_pct`
- `max_total_exposure_pct`
- `max_per_market_exposure_pct`
- `min_rebalance_threshold_pct`
- `min_order_krw_buffer`
- `cooldown_hours_on_halt`
- `max_new_orders_per_day`
- `max_orders_per_week`
- `min_edge_pct`
- `fill_timeout_sec_entry`, `fill_timeout_sec_exit`, `fill_timeout_sec_rebalance`
- `max_reprice_attempts_entry`, `max_reprice_attempts_exit`, `max_reprice_attempts_rebalance`
- `reprice_step_bps`
- `slippage_budget_entry_pct`
- `slippage_budget_exit_pct`
- `slippage_budget_breach_halt_count`
- `status_notify_interval_seconds`

Sanitization rules:

- timeouts are clamped to `1..120`
- reprice attempts are clamped to `1..10`
- `reprice_step_bps` is clamped to `1..500`
- notify interval is clamped to `300..86400`
- `daily_loss_basis` is only `TOTAL` or `REALIZED_ONLY`; invalid values become `TOTAL`
- `max_weekly_loss_pct`, `max_monthly_loss_pct`, `min_edge_pct` are clamped into `0..1`
- `cooldown_hours_on_halt` is clamped to `0..168`
- `max_new_orders_per_day` is clamped to `0..10000`
- `max_orders_per_week` is clamped to `0..70000`

## 6. Order states and mappings

### Local open-state set

The system treats these as not yet closed:

- `NEW`
- `SENT`
- `OPEN`
- `PARTIAL`
- `WAIT`

### Upbit to local mapping

- `wait` -> `OPEN`
- `watch` -> `OPEN`
- `done` -> `FILLED`
- `cancel` -> `CANCELED`
- missing state during sync defaults to `SENT`
- missing state during reconcile open-orders defaults to `OPEN`

### Other important states

- `REJECTED`: validation or submit-level rejection
- `ERROR_NEEDS_REVIEW`: recovery failed; manual inspection required
- `TEST_OK`: test-order path succeeded
- `SHADOW`: validation-only shadow mode record

## 7. Order execution invariants

Execution engine is in `trader/trading/execution.py`.

### Logical order behavior

- `delta = target_qty - current_qty`
- `abs(delta) < 1e-8` => no order
- `delta > 0` => `bid`
- `delta < 0` => `ask`
- One logical order can have multiple `order_attempts`

### Validation and allowlist behavior

If market allowlist is enforced and the market is not allowed:

- create local order row
- set state to `REJECTED`
- set `error_class = VALIDATION_ERROR`
- do not submit to exchange

Before submit:

- price must be `> 0`
- volume must be `> 0`
- order chance is fetched from Upbit
- price is adjusted to tick size
- volume is rounded down to `0.00000001`
- order notional must satisfy `min_total + min_order_krw_buffer`

### Conflict, idempotency, and recovery

Before creating a new logical order for a market:

- if there is an opposite-side open order in that market, cancel it first

Critical recovery invariant:

- On submit failure, do not blindly resubmit the same attempt.
- The engine performs one submit, then recovery by Upbit `identifier` lookup only.

Mechanics:

- Each attempt reserves a unique one-time `upbit_identifier`.
- `upbit_identifier` must never be reused across attempts.
- If create succeeds, sync by `upbit_uuid`.
- If create fails, classify error, then try `get_order_by_identifier()` up to `max_submit_retries`.
- If recovery still fails, final state becomes `ERROR_NEEDS_REVIEW`.

### Reprice policy

Policy is deterministic by intent:

- `ENTRY`: `LIMIT`, default timeout `10s`, default reprice attempts `2`
- `EXIT`: `LIMIT`, but `AGGRESSIVE_LIMIT` if stop or hard-halt; default timeout `4s`, default reprice attempts `1`
- `REBALANCE`: conservative `LIMIT`, default reprice attempts `1`
- `reprice_step_bps` default is `10`
- market fallback on exit is currently disabled in scheduler config

### Partial fills

After sync:

- if local state is `OPEN` and `0 < executed_volume < requested_volume`, convert to `PARTIAL`

## 8. Reconcile invariants

Non-paper trading uses `ReconcileService`.

Reconcile flow:

1. Pull accounts from Upbit and overwrite local positions.
2. Pull open orders from Upbit and reconcile into local `orders` and `order_attempts`.
3. Sync local open orders again via execution engine.
4. Apply unapplied fills exactly once.
5. Recompute unrealized PnL.

Important:

- `cash_krw = KRW.balance + KRW.locked`
- position qty uses `balance + locked`
- mark price defaults to current candle close; if missing, falls back to avg buy price
- if an open exchange order exists but no local logical order exists, reconcile creates one
- reconcile-created attempts use `submit_reason = RECOVER`

## 9. Fill, position, and PnL invariants

### Fill ledger

- `fills.trade_id` is globally unique
- `fills.is_applied` prevents double-applying fills
- new fills are inserted once, then applied once

### Position accounting

Buy fill:

- increases qty
- updates avg price using weighted cost + fee

Sell fill:

- realizes PnL as `(sell_qty * (price - avg_price)) - fee`
- reduces qty
- if qty becomes zero, avg price resets to `0`

### Daily equity

`daily_equity` stores:

- `start_equity`
- `start_realized_pnl`
- `last_equity`
- `realized_pnl`
- `unrealized_pnl`
- `daily_pnl_abs`
- `daily_pnl_pct`

Daily loss basis:

- `TOTAL`: use full daily equity change
- `REALIZED_ONLY`: use `current_realized_pnl - start_realized_pnl`

## 10. Trade metrics and slippage invariants

For each order, at most one `trade_metrics` row exists.

Metrics derive from applied fills:

- VWAP from fill notional / fill volume
- fee sum from fills
- `time_to_fill_ms = last fill time - order created time`
- `partial_fill_count = number of fills`

Slippage sign convention:

- buy worse than intended price => positive slippage
- sell worse than intended price => positive slippage

Budget checks:

- `EXIT` uses `slippage_budget_exit_pct`
- non-`EXIT` uses `slippage_budget_entry_pct`
- if breach count since UTC day start >= `slippage_budget_breach_halt_count`, scheduler auto-disables the bot

## 11. Core data model

Main tables:

- `users`
- `user_exchange_credentials`
- `user_api_budget`
- `audit_log`
- `user_bot_config` (unique `user_id`)
- `user_bot_runtime` (unique `user_id`)
- `user_risk_guard` (unique `user_id`)
- `bot_config`
- `timeframe_config`
- `candles` unique by `(market, timeframe, candle_time_utc)`
- `orders` unique `(user_id, client_order_id)`
- `order_attempts` unique `(order_id, attempt_no)`
- `fills` unique `trade_id`
- `trade_metrics` unique `order_id`
- `positions` PK `(user_id, market)`
- `daily_equity` PK `(user_id, date_utc)`
- `paper_wallet` PK `user_id`

Order and accounting tables are the most important anchor for modifications.

## 12. Ops/API notes

Ops API surfaces operational reads and writes over local DB state.

Notable endpoints:

- auth: signup/login
- user-scoped reads/writes under `/api/me/*` (credentials, orders, pnl, metrics, bot status/start/stop)
- admin per-user scoped reads under `/api/admin/users/{user_id}/*`
- admin ops visibility summary: `GET /api/admin/users/runtime-summary`
- admin audit read/search: `GET /api/admin/audit/logs`
- admin session lifecycle control: `POST /api/admin/users/{user_id}/sessions/invalidate`
- admin role change: `POST /api/admin/users/{user_id}/role`
- retired admin compatibility aliases return `410 legacy_endpoint_retired` with replacement metadata
- legacy compatibility endpoints `POST /api/bot/enable|disable` are retired and return `410 legacy_endpoint_retired` with replacement path metadata

Release gate artifact command:

- `python scripts/run_release_gate.py --output-dir .`

Current compatibility behavior:

- `/api/me/*` is user-scoped and must not depend on owner bridging.
- Do not casually remove compatibility fallback paths unless the task explicitly includes migration/removal.

## 13. Do-not-break rules

Preserve these invariants unless the task explicitly changes product behavior:

1. Do not break order idempotency by candle, market, and side within user scope.
2. Do not resubmit blindly after submit ambiguity; recover by identifier first.
3. Do not apply the same fill twice.
4. Do not reuse `upbit_identifier` across attempts.
5. Do not remove conflict cancellation for opposite-side open orders.
6. Do not bypass min-notional and tick-size validation.
7. Do not change daily loss basis semantics accidentally.
8. Do not invert the slippage sign convention.
9. Do not confuse `PAPER` immediate fills with real-mode asynchronous lifecycle.
10. Do not assume runtime config comes only from env; DB config is authoritative at runtime.
11. Do not mix data between users in scheduler, execution, reconcile, or Ops read paths.
12. Do not route authenticated `/api/me/*` data reads through owner fallback scope.

## 14. Best prompt pattern for Codex in this repo

Use prompts in this order:

1. Read `docs/context_anchor.md`
2. Read the specific trading files involved
3. State which invariant must remain true
4. Then patch

Example:

> Read `docs/context_anchor.md`, then inspect `trader/trading/execution.py` and `trader/trading/reconcile.py`. Fix the bug without breaking identifier-based recovery, fill idempotency, or opposite-side open-order cancellation.
