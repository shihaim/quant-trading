# S7 Risk Policy Expansion (2026-03-22)

## Scope

- Add weekly/monthly loss guards.
- Add cooldown-on-halt enforcement.
- Add daily/weekly order-count limits.
- Add minimum edge filter (`min_edge_pct`) for BUY-side entries.
- Expose halt reason and cooldown in me/admin status payloads and ops UI.

## New Runtime Policy Fields

- `max_weekly_loss_pct`
- `max_monthly_loss_pct`
- `cooldown_hours_on_halt`
- `max_new_orders_per_day`
- `max_orders_per_week`
- `min_edge_pct`

## New Halt/Status Signals

- `weekly_loss_limit`
- `monthly_loss_limit`
- `new_orders_daily_limit`
- `orders_weekly_limit`
- `cooldown_active`

## Behavior Notes

- Risk policy checks are user-scoped and do not affect unrelated users.
- When a policy halt is triggered, runtime is set to `HALTED` with `halt_reason`.
- If `cooldown_hours_on_halt > 0`, `cooldown_until` is written and `/api/me/bot/start` is blocked until expiry.
- `min_edge_pct` is a filter (BUY skip), not a hard runtime halt by itself.

