# Quant Trading MVP Context Anchor (V3 Transition Safe)

Last verified: 2026-03-06
Verified against: `trader/config/settings.py`, `trader/config/config_repo.py`, `trader/trading/execution.py`, `trader/trading/reconcile.py`, `ticket/BATCH_MAP.md`

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

These areas are actively changing for V3.

- Scheduler flow is moving from single-engine assumptions to per-user execution contexts.
- Runtime/config ownership is moving away from global single-row assumptions.
- `/api/me/*` is moving away from legacy owner-bridge behavior.
- Bot start/stop behavior is moving to per-user runtime control.
- Schema and write paths are moving to user-aware ownership boundaries.

Do not treat the following as durable invariants during V3:
- one global scheduler loop as the only authoritative execution shape
- one global bot row or one global runtime row
- one owner-selected data scope for authenticated reads
- one exchange credential path shared by normal runtime

## 9. V3 do-not-break rules

1. Do not introduce cross-user data mixing.
2. Do not reintroduce a global single-owner bridge path.
3. Do not reintroduce `bot_config(id=1)` as a required runtime dependency.
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
