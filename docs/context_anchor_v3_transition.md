# Quant Trading MVP Context Anchor (V3 Transition Safe)

Last verified: 2026-03-22
Verified against: `trader/config/settings.py`, `trader/config/config_repo.py`, `trader/trading/scheduler.py`, `trader/trading/risk.py`, `trader/trading/execution.py`, `trader/trading/reconcile.py`, `trader/data/models.py`, `trader/api/ops_http.py`, `trader/auth/guard.py`, `trader/auth/tokens.py`, `trader/me/read_service.py`, `trader/ops/service.py`, `trader/audit/service.py`, `trader/release_gate.py`, `scripts/run_release_gate.py`, `scripts/audit_upbit_credential_coverage.py`, `apps/web/components/admin-users-runtime-table.tsx`, `apps/web/components/admin-audit-log-viewer.tsx`, `apps/web/components/ops-dashboard.tsx`, Notion Task index (`https://www.notion.so/31b899b6d7dc80d4af4be0041af7937d`), Notion V3 batch page (`https://www.notion.so/31c899b6d7dc81f5a92bfa159119e6e5`)

## Quick routing

Read this file first when the task changes any of these:
- order execution, reconcile, fills, PnL, runtime config validation, risk guards
- user scoping of orders, positions, wallet, credentials, bot runtime, API read/write paths
- migration from legacy single-bot assumptions to user-scoped trading core

This file is usually not needed for:
- simple UI text/style work in `apps/web`
- isolated docs cleanup with no behavior change
- implementation-local refactors that do not affect trading/accounting/runtime semantics

Priority rule:
- If current branch code conflicts with this file in an in-transition area, prefer current branch code.
- This file documents stable invariants first. Anything marked "in transition" is not a hard design freeze.

## 1. What remains stable

These rules should remain true during V3 unless the product behavior explicitly changes.

- `PAPER` is local-only simulated execution.
- `REAL` is exchange-backed execution with asynchronous lifecycle.
- `TEST` validates against the exchange test path without placing a live order.
- `SHADOW` records intent without live execution.
- Invalid runtime values must fail safe.
- Price, volume, tick-size, and minimum-notional validation must not be bypassed.
- Submit ambiguity must not cause blind resubmission.
- Recovery after ambiguous submit should prefer identifier-based lookup.
- The same fill must never be applied twice.
- `upbit_identifier` must not be reused across attempts.
- Opposite-side open-order conflict handling must not be casually removed.
- Daily loss basis semantics must not be changed accidentally.
- `PAPER` immediate local fill semantics must not be confused with real-mode lifecycle.

## 2. Multi-user invariants for V3

These are now more important than legacy single-bot assumptions.

- Orders, attempts, fills, positions, pnl, wallet state, credentials, and bot runtime must be user-scoped.
- No cross-user data mixing is allowed.
- One user failure must not halt or corrupt other users' ticks.
- Runtime control must be per user, not global.
- Idempotency and reconciliation must be safe within user scope.
- Credential loading for normal runtime must be user-scoped.
- API reads and writes under authenticated `/api/me/*` must not depend on a global owner bridge.

## 3. Trading mode facts

Mode semantics apply per active user runtime context.

- `PAPER`: no live exchange submit; local simulated fill/accounting path.
- `REAL`: live Upbit order submit and exchange-backed lifecycle.
- `TEST`: Upbit test-order path; no live order.
- `SHADOW`: validation and intent record only.

Important:
- `REAL`, `TEST`, and `SHADOW` require credentials for the active user.
- Do not assume non-paper modes share one exchange account.

## 4. Runtime config invariants

Keep these rules, but do not reintroduce legacy global assumptions.

- Runtime config is authoritative at runtime only after validation/sanitization.
- Invalid values must clamp or safely fall back.
- Timeouts are clamped to `1..120`.
- Reprice attempts are clamped to `1..10`.
- `reprice_step_bps` is clamped to `1..500`.
- Notify interval is clamped to `300..86400`.
- `daily_loss_basis` only allows `TOTAL` or `REALIZED_ONLY`; invalid values fall back safely.

Do not assume these legacy patterns remain valid:
- one global `bot_config(id=1)` row
- one shared runtime state for all users
- one global bot enable/disable switch

Current branch note:
- `load_for_user()` uses `user_bot_config`; if a user row is missing, it creates a default `user_bot_config` row.
- `load_for_user()` no longer falls back to global `bot_config(id=1)`.

## 5. Order execution invariants

These remain core even while write paths become user-aware.

- `delta = target_qty - current_qty`
- `abs(delta) < 1e-8` => no order
- `delta > 0` => buy side
- `delta < 0` => sell side
- One logical order can have multiple attempts.
- Before submit, validate price, volume, tick size, rounding, and minimum-notional rules.
- If allowlist policy rejects a market, reject locally and do not submit to exchange.
- Do not blindly resubmit after submit uncertainty.
- Use one-time `upbit_identifier` values per attempt.
- After sync, a partially executed still-open order should become `PARTIAL`.

User-scope clarification:
- Duplicate logical-order prevention must be evaluated within the same user scope.
- Identifier recovery and order matching must not mix users.

## 6. Reconcile and accounting invariants

These remain true, but they must operate within the correct user boundary.

- Reconcile updates local trading state from exchange/account data.
- If exchange state exists but local state is missing, recovery may create local records.
- Fill ingestion must be idempotent.
- Applied fills drive position and PnL updates.
- Unrealized PnL can depend on current mark/reference price.
- `cash_krw` style balance calculations must use the correct account scope.

User-scope clarification:
- Reconcile must never overwrite one user's positions/wallet with another user's account data.
- PnL/equity calculations must never aggregate unrelated users by accident.

## 7. Order states and semantics

Keep these semantics stable unless the state model itself changes.

Local open-state concept:
- `NEW`
- `SENT`
- `OPEN`
- `PARTIAL`
- `WAIT`

Other important states:
- `FILLED`
- `CANCELED`
- `REJECTED`
- `ERROR_NEEDS_REVIEW`
- `TEST_OK`
- `SHADOW`

Upbit mapping should remain semantically consistent:
- `wait` -> `OPEN`
- `watch` -> `OPEN`
- `done` -> `FILLED`
- `cancel` -> `CANCELED`

## 8. In-transition items (not hard-frozen)

Already landed on current branch:

- Scheduler now has `MultiUserTradingScheduler` with per-user failure isolation.
- `/api/me/*` reads/writes are user-scoped via authenticated user identity.
- Bot start/stop and runtime status are per-user (`user_bot_runtime`).
- Core trading/accounting tables are user-scoped where required (`orders`, `positions`, `daily_equity`, `paper_wallet`).

Remaining transition/compatibility zones:

- No runtime owner-resolution fallback is currently expected. Keep new runtime paths explicitly user-scoped.
- `legacy_user_id`는 V3 이전 `user_id`가 없던 단일봇 rows를 귀속시키는 마이그레이션/backfill 도구에서만 사용할 수 있다. 정상 멀티유저 런타임 기본값이 아니며, 현재 rows는 명시적인 자체 `user_id`를 가져야 한다.

Do not treat the following as durable invariants during V3:

- global `bot_config(id=1)` fallback must exist forever
- implicit owner resolution should be preferred over explicit per-user scope in new code

## 9. V3 do-not-break rules

1. Do not introduce cross-user data mixing.
2. Do not route authenticated `/api/me/*` reads through a global single-owner bridge path.
3. Do not reintroduce `bot_config(id=1)` as a required runtime dependency outside explicit compatibility fallback.
4. Do not make one user's runtime failure stop unrelated users.
5. Do not break identifier-based recovery after ambiguous submit.
6. Do not apply the same fill twice.
7. Do not bypass validation for tick size, quantity rounding, or minimum notional.
8. Do not confuse `PAPER` local simulation with exchange-backed modes.
9. Do not assume credentials/runtime are process-global in normal multi-user operation.
10. Do not let idempotency or reconcile logic match records across users.

## 10. Best prompt pattern for Codex in this repo during V3

Use prompts in this order:

1. Read `docs/context_anchor_v3_transition.md`
2. Read the specific files involved
3. State which stable invariant must remain true
4. State which V3 in-transition area is being changed
5. Then patch

Example:

> Read `docs/context_anchor_v3_transition.md`, then inspect the scheduler/runtime/user-scoping files involved. Keep fill idempotency, identifier-based recovery, and no cross-user data mixing intact while moving runtime control to per-user scope.

## 11. Post-V3 backlog guardrails (S1~S7, 2026-03-10)

Reference backlog page (Notion):
- `https://www.notion.so/31f899b6d7dc81cb897deda764f70769`

Use this section when implementing the post-V3 hardening backlog.

### 11.1 Story routing

- S1, S2, S3: operations visibility/readability/automation hardening
- S4, S5, S6: compatibility and safety hardening on live paths
- S7: risk policy expansion

### 11.2 Global rules for all S1~S7 changes

1. Keep user scope boundaries explicit on all read/write queries.
2. Preserve admin/non-admin boundary checks on `/ops` and `/api/admin/*`.
3. Preserve event naming contracts where already used by tests/runbooks/dashboards.
4. Ship changes with backend + tests (+ frontend/docs when applicable) in the same task.
5. Do not broaden compatibility fallbacks while adding new behavior.

### 11.3 Story-specific do-not-break notes

- S1 (ops visibility):
  - Do not aggregate unrelated users into a single status row.
  - Do not expose admin-only fields to non-admin callers.
- S2 (audit read/search):
  - Do not expose raw sensitive secrets in API/UI payloads.
  - Do not add unbounded full-scan defaults for long time ranges.
  - Keep bounded query windows (default bounded range, explicit max range guard).
- S3 (release gate artifact):
  - Do not report pass when required checks were skipped.
  - Always include failure reasons in artifact output.
  - Keep credential coverage check reproducible on CI/local (avoid environment-only pass conditions).
- S4 (legacy bot endpoint retirement):
  - Use staged deprecation/removal; do not break known callers without migration note.
  - Keep `/api/me/bot/*` as the single authoritative contract.
- S5 (auth/session hardening):
  - Keep token-expiry behavior deterministic across frontend/backend.
  - Preserve current admin boundary while changing session lifecycle.
- S6 (order_attempts hardening):
  - Validate existing data before unique constraints.
  - Keep fill idempotency and identifier recovery semantics unchanged.
- S7 (risk policy expansion):
  - Expose halt reasons consistently in API/UI.
  - Keep per-user failure isolation; one user guard trigger must not stop others.

### 11.4 Recommended Codex prompt fragment for S1~S7

Use this exact fragment after selecting a story:

> Read `docs/context_anchor_v3_transition.md` first. Implement Story `Sx` from `2026-03-10 Post-V3 Ops Hardening Backlog` while preserving: no cross-user mixing, no owner-bridge reintroduction on `/api/me/*`, no required global `bot_config(id=1)`, per-user failure isolation, and admin boundary integrity. Patch backend/tests/docs together (plus frontend if touched), then map results to story acceptance.

### 11.5 Implemented B1~B3 references (2026-03-22)

Use these as current contracts for branches with B1~B3 applied:

- S1 endpoint: `GET /api/admin/users/runtime-summary`
- S2 endpoint: `GET /api/admin/audit/logs`
  - filters: `actor_user_id`, `target_user_id`, `action`, `target_type`, `from`, `to`, `result`
  - guardrails: default bounded window, maximum date-range guard, latest-first pagination
- S3 command: `python scripts/run_release_gate.py --output-dir .`
  - artifacts: `release_gate_report.json`, `release_gate_report.md`
- S3 credential audit command: `python scripts/audit_upbit_credential_coverage.py`
- S4 compatibility endpoint behavior:
  - `POST /api/bot/enable|disable` -> `410 legacy_endpoint_retired`
  - replacement path metadata: `/api/me/bot/start|stop`
- S5 session lifecycle:
  - token includes `token_version`; stale/revoked token yields `401 session_revoked`
  - admin action: `POST /api/admin/users/{user_id}/sessions/invalidate`
  - admin role source: `users.is_admin` (DB-backed)
  - role change endpoint: `POST /api/admin/users/{user_id}/role` with token-version bump
  - retired legacy admin aliases: `/api/ops/summary`, `/api/admin/summary`, `/api/orders`, `/api/admin/orders`, `/api/pnl/daily`, `/api/admin/pnl/daily`, `/api/metrics/trade`, `/api/admin/metrics/trade` -> `410 legacy_endpoint_retired`
  - retired rotate alias: `POST /api/ops/credentials/rotate` -> `410 legacy_endpoint_retired` (use `/api/admin/credentials/rotate`)
- S6 order-attempt consistency:
  - normalized latest/next attempt calculations in shared helpers
  - runbook: `docs/order_attempts_unique_constraints_runbook_2026-03-22.md`
- S7 risk policy expansion:
  - new config keys: `max_weekly_loss_pct`, `max_monthly_loss_pct`, `cooldown_hours_on_halt`, `max_new_orders_per_day`, `max_orders_per_week`, `min_edge_pct`
  - new halt reasons: `weekly_loss_limit`, `monthly_loss_limit`, `new_orders_daily_limit`, `orders_weekly_limit`, `cooldown_active`
