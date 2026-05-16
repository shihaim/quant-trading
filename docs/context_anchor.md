# Quant Trading MVP 문맥 기준

최종 확인: 2026-03-22

확인 기준 파일: `trader/config/settings.py`, `trader/config/config_repo.py`, `trader/trading/scheduler.py`, `trader/trading/strategy.py`, `trader/trading/risk.py`, `trader/trading/execution.py`, `trader/trading/reconcile.py`, `trader/trading/order_policy.py`, `trader/data/models.py`, `trader/api/ops_http.py`, `trader/auth/guard.py`, `trader/auth/tokens.py`, `trader/me/read_service.py`, `trader/ops/service.py`, `trader/audit/service.py`, `trader/release_gate.py`, `trader/app/main.py`, `scripts/run_release_gate.py`, `scripts/audit_upbit_credential_coverage.py`

## 빠른 적용 기준

아래를 수정하는 작업은 이 문서를 먼저 읽는다.

- 거래 로직, scheduler flow, 주문 실행, reconcile, fill, PnL, runtime config, risk, Ops API 동작
- `orders`, `order_attempts`, `fills`, `positions`, `daily_equity`, `paper_wallet`, `user_bot_config`, `user_bot_runtime`, `user_risk_guard`, `bot_config`의 DB 불변식

아래 작업에는 보통 이 문서가 필요하지 않다.

- `apps/web`의 단순 UI 문구/스타일 변경
- 동작 변경이 없는 README/docs 정리
- 주문/회계/런타임 의미를 건드리지 않는 utility refactor

이 문서는 Codex/LLM 보조 작업에서 안정적인 불변식 기준으로 사용한다.

## 1. 프로젝트 형태

- 프로젝트 유형: Upbit spot trading MVP.
- 구조: 멀티유저 trading scheduler, 사용자별 execution worker, 별도 Ops API, 별도 Next.js dashboard frontend.
- 주요 Python package: `trader/`
- Frontend: `apps/web`
- 주요 runtime entrypoint:
  - `python -m trader.app.main`
  - `python -m trader.app.ops_api`
  - `python -m trader.app.backtest`

## 2. Trading mode

`TRADE_MODE`는 아래 값을 지원한다.

- `PAPER`: 기본값. live exchange submit 없음. order는 즉시 `FILLED`로 insert되고 synthetic fill이 생성된다.
- `REAL`: live Upbit order submit.
- `TEST`: Upbit `/v1/orders/test` 호출. ledger 결과는 `TEST_OK`로 저장하며 live order는 만들지 않는다.
- `SHADOW`: validation과 intent 기록만 수행. exchange submit 없음. order state는 `SHADOW`.

중요:

- `REAL`, `TEST`, `SHADOW`는 Upbit credential이 필요하다.
- local CLI/dev는 `DATABASE_URL`이 없으면 `sqlite:///./trading.db`로 fallback한다.
- Docker Compose 기본값은 PostgreSQL이다.
- `PAPER` immediate local fill semantics를 real-mode asynchronous lifecycle과 혼동하지 않는다.

## 3. Core scheduler loop

Scheduler loop는 `trader/trading/scheduler.py`에 있다.

현재 runtime 형태:

- `MultiUserTradingScheduler`가 활성 사용자를 조정하고, 사용자별 tick을 lock 기반으로 격리한다.
- `TradingScheduler`는 한 사용자 tick을 실행한다.

한 사용자에 대한 due tick 순서:

1. DB에서 `load_for_user(user_id)`로 runtime config를 읽는다.
2. 각 configured market에 대해 candle backfill, 최신 complete candle upsert, recent candle load를 수행한다.
3. 마지막 complete candle close를 mark/reference price로 사용한다.
4. portfolio snapshot을 만든다.
   - `PAPER`: 해당 사용자의 local wallet + local positions 기준.
   - non-paper: 해당 사용자의 Upbit account reconcile 기준.
5. 해당 사용자의 daily PnL snapshot을 갱신한다.
6. strategy signal을 평가한다.
7. risk engine을 적용한다.
8. rebalance threshold 미만이면 skip한다.
9. notional이 `5000 KRW + min_order_krw_buffer` 미만이면 skip한다.
10. 사용자 scope 안에서 order place, sync, fill apply를 수행한다.
11. slippage budget breach를 확인하고 필요하면 해당 사용자 runtime만 auto-halt한다.

Scheduled-order idempotency key:

- `"{timeframe}-{market}-{last_complete_candle_time_utc}"`
- `client_order_id = "u{user_id}-" + sanitized(idempotency_key) + "-" + side`
- 같은 candle, market, side는 같은 사용자 scope 안에서 중복 logical order를 만들면 안 된다.

## 4. Strategy와 risk 규칙

현재 strategy는 `EmaCrossStrategy`다.

- Fast EMA = 20
- Slow EMA = 60
- 최소 `slow + 5` candle 필요
- `fast_ema > slow_ema`이면 `BUY`
- 그 외에는 `SELL`
- BUY target exposure 기본값은 `0.10`이지만 scheduler가 runtime config 값으로 덮어쓴다.

Risk engine output은 최종 허용 target exposure다.

Hard guard:

- bot disabled: halt, target exposure = `0`
- daily PnL pct <= `-abs(max_daily_loss_pct)`: halt, target exposure = `0`
- weekly PnL pct <= `-abs(max_weekly_loss_pct)` (설정 시): halt, target exposure = `0`
- monthly PnL pct <= `-abs(max_monthly_loss_pct)` (설정 시): halt, target exposure = `0`
- `new_orders_today >= max_new_orders_per_day` (설정 시): halt, target exposure = `0`
- `orders_this_week >= max_orders_per_week` (설정 시): halt, target exposure = `0`

Exposure logic:

- BUY 또는 hold exposure는 아래 값으로 cap된다.
  - `signal.target_exposure_pct`
  - `max_per_market_exposure_pct`
  - `max_total_exposure_pct`
- SELL은 target exposure를 `0`으로 강제한다.

Gate:

- `abs(target_exposure_pct - current_exposure_pct) < min_rebalance_threshold_pct`이면 rebalance skip.
- BUY signal edge pct가 `min_edge_pct`보다 낮으면 skip. 이 filter는 runtime halt가 아니다.
- order notional이 `5000 KRW + min_order_krw_buffer`보다 작으면 skip.

## 5. Runtime config 불변식

Bot config source:

- 주 소스: active `user_id`의 `user_bot_config` row.
- fallback 소스: user row가 없을 때 global `bot_config.id = 1`.
- active timeframe 소스: `timeframe_config`에서 `is_enabled=true`인 첫 row, `id ASC` 기준.
- 선택된 timeframe이 invalid이면 `15m`으로 fallback.
- runtime enable/status 소스: 사용자별 `user_bot_runtime`.
- risk guard 소스: 사용자별 `user_risk_guard`.

중요 runtime field:

- `target_exposure_pct`
- `max_total_exposure_pct`
- `max_per_market_exposure_pct`
- `daily_loss_basis`
- `min_rebalance_threshold_pct`
- `min_order_krw_buffer`
- `fill_timeout_sec_entry`
- `fill_timeout_sec_exit`
- `fill_timeout_sec_rebalance`
- `max_reprice_attempts_entry`
- `max_reprice_attempts_exit`
- `max_reprice_attempts_rebalance`
- `reprice_step_bps`
- `slippage_budget_*`
- `max_weekly_loss_pct`
- `max_monthly_loss_pct`
- `cooldown_hours_on_halt`
- `max_new_orders_per_day`
- `max_orders_per_week`
- `min_edge_pct`

Sanitization:

- exposure 계열 값은 안전 범위로 clamp한다.
- timeout은 `1..120`.
- reprice attempt는 `1..10`.
- `reprice_step_bps`는 `1..500`.
- `daily_loss_basis`는 `TOTAL` 또는 `REALIZED_ONLY`; invalid 값은 `TOTAL`.
- invalid timeframe은 `15m`.

## 6. Order state와 mapping

Local open state:

- `NEW`
- `SENT`
- `OPEN`
- `PARTIAL`
- `WAIT`

Terminal/특수 state:

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

## 7. 주문 실행 불변식

Order/accounting table은 수정 시 가장 중요한 기준이다.

- order intent는 `ENTRY`, `EXIT`, `REBALANCE`를 사용한다.
- price/volume/tick-size/min-notional validation을 우회하지 않는다.
- market allowlist가 켜져 있고 market이 허용되지 않으면 local reject 후 exchange submit을 하지 않는다.
- submit failure 이후 같은 attempt를 blind resubmit하지 않는다.
- identifier 기반 recovery를 우선한다.
- one logical order can have multiple attempts.
- attempt마다 `upbit_identifier`를 재사용하지 않는다.
- opposite-side open-order conflict 처리는 함부로 제거하지 않는다.

## 8. Reconcile 불변식

- Upbit account를 읽어 local position을 갱신한다.
- Upbit open order를 읽어 local `orders`와 `order_attempts`를 reconcile한다.
- exchange state가 있으나 local record가 없으면 recovery가 local record를 만들 수 있다.
- fill ingestion은 idempotent해야 한다.
- local state가 `OPEN`이고 `0 < executed_volume < requested_volume`이면 `PARTIAL`로 전환한다.
- 사용자 scope 밖의 order/position/wallet을 건드리면 안 된다.

## 9. Fill, position, PnL 불변식

- 같은 exchange fill/trade id는 한 번만 적용한다.
- applied fill이 position quantity, average price, realized PnL, wallet/accounting update를 만든다.
- daily equity는 사용자별, UTC date 기준 snapshot이다.
- unrealized PnL은 mark/reference price를 사용한다.
- mark price가 없으면 average buy price fallback을 사용할 수 있다.
- 사용자 간 equity/PnL aggregation은 의도 없이 하면 안 된다.

## 10. Ops API 불변식

Ops API는 local DB state 위에 운영 읽기/쓰기 경로를 제공한다.

현재 중요한 계약:

- `/api/me/*` 아래 사용자 scope 읽기/쓰기: credentials, orders, pnl, metrics, bot status/start/stop.
- `/api/admin/users/{user_id}/*` 아래 admin per-user scope 읽기.
- admin 운영 요약: `GET /api/admin/users/runtime-summary`
- admin audit 조회: `GET /api/admin/audit/logs`
- admin session lifecycle: `POST /api/admin/users/{user_id}/sessions/invalidate`
- admin role 변경: `POST /api/admin/users/{user_id}/role`
- retired admin compatibility alias는 `410 legacy_endpoint_retired`와 replacement metadata를 반환한다.
- retired bot compatibility endpoint `POST /api/bot/enable|disable`도 `410 legacy_endpoint_retired`를 반환한다.

유지해야 할 경계:

- `/api/me/*`는 사용자 scope이며 owner bridge에 의존하면 안 된다.
- 명시적인 migration/removal 작업이 아니면 compatibility fallback path를 함부로 제거하지 않는다.
- non-admin은 `/ops`와 `/api/admin/*`에 접근할 수 없다.

## 11. 수정 시 절대 깨면 안 되는 항목

1. 사용자 scope 안에서 candle, market, side 기준 order idempotency를 깨지 않는다.
2. ambiguous submit 이후 identifier 기반 recovery를 깨지 않는다.
3. 같은 fill을 두 번 적용하지 않는다.
4. opposite-side open-order cancellation/recovery를 제거하지 않는다.
5. `REAL`/`TEST`/`SHADOW` credential requirement를 우회하지 않는다.
6. min-notional과 tick-size validation을 우회하지 않는다.
7. daily loss basis 의미를 바꾸지 않는다.
8. slippage sign convention을 뒤집지 않는다.
9. `PAPER` immediate fill과 real-mode asynchronous lifecycle을 혼동하지 않는다.
10. runtime config가 env에서만 온다고 가정하지 않는다. DB config가 runtime의 authoritative source다.
11. scheduler, execution, reconcile, Ops read path에서 사용자 간 데이터를 섞지 않는다.
12. 인증된 `/api/me/*` data read를 owner fallback scope로 보내지 않는다.

## 12. 권장 작업 순서

1. `docs/context_anchor.md`를 읽는다.
2. 관련 trading 파일을 좁혀서 읽는다.
3. 유지할 invariant를 먼저 말한다.
4. 테스트를 먼저 추가하거나 갱신한다.
5. 최소 구현으로 통과시킨다.
6. 필요한 docs/runbook/Notion mapping을 갱신한다.

예시:

> `docs/context_anchor.md`를 읽고, `trader/trading/execution.py`와 `trader/trading/reconcile.py`를 확인한다. identifier 기반 recovery, fill idempotency, opposite-side open-order cancellation을 깨지 않고 버그를 수정한다.
