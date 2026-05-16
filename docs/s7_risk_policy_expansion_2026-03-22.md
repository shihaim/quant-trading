# S7 리스크 정책 확장 (2026-03-22)

## 범위

- 주간/월간 손실 guard 추가.
- 중지 후 cooldown 강제 적용.
- 일간/주간 주문 수 제한 추가.
- BUY 진입용 최소 edge filter(`min_edge_pct`) 추가.
- me/admin status payload와 ops UI에 halt reason/cooldown 노출.

## 신규 런타임 정책 field

- `max_weekly_loss_pct`
- `max_monthly_loss_pct`
- `cooldown_hours_on_halt`
- `max_new_orders_per_day`
- `max_orders_per_week`
- `min_edge_pct`

## 신규 중지/상태 signal

- `weekly_loss_limit`
- `monthly_loss_limit`
- `new_orders_daily_limit`
- `orders_weekly_limit`
- `cooldown_active`

## 동작 메모

- 리스크 정책 check는 사용자 scope 기준이며 다른 사용자에게 영향을 주지 않는다.
- 정책 중지가 발생하면 runtime은 `halt_reason`과 함께 `HALTED` 상태가 된다.
- `cooldown_hours_on_halt > 0`이면 `cooldown_until`을 기록하고 만료 전까지 `/api/me/bot/start`를 차단한다.
- `min_edge_pct`는 filter(BUY skip)이며, 그 자체로 runtime hard halt를 만들지 않는다.
