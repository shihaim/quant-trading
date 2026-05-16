# Quant Trading MVP 문맥 기준 (V3 전환 안전 기준)

최종 확인: 2026-03-22

확인 기준 파일: `trader/config/settings.py`, `trader/config/config_repo.py`, `trader/trading/scheduler.py`, `trader/trading/risk.py`, `trader/trading/execution.py`, `trader/trading/reconcile.py`, `trader/data/models.py`, `trader/api/ops_http.py`, `trader/auth/guard.py`, `trader/auth/tokens.py`, `trader/me/read_service.py`, `trader/ops/service.py`, `trader/audit/service.py`, `trader/release_gate.py`, `scripts/run_release_gate.py`, `scripts/audit_upbit_credential_coverage.py`, `apps/web/components/admin-users-runtime-table.tsx`, `apps/web/components/admin-audit-log-viewer.tsx`, `apps/web/components/ops-dashboard.tsx`, Notion Task index (`https://www.notion.so/31b899b6d7dc80d4af4be0041af7937d`), Notion V3 batch page (`https://www.notion.so/31c899b6d7dc81f5a92bfa159119e6e5`)

## 빠른 적용 기준

아래를 수정하는 작업은 이 문서를 먼저 읽는다.

- 주문 실행, reconcile, 체결, PnL, 런타임 config 검증, 리스크 guard
- `orders`, `positions`, `paper_wallet`, `daily_equity`, 자격증명, bot runtime, API 읽기/쓰기 경로의 사용자 scope
- legacy 단일 bot 전제에서 사용자별 trading core로 이동하는 마이그레이션

아래 작업에는 보통 이 문서가 필요하지 않다.

- `apps/web`의 단순 UI 문구/스타일 변경
- 동작 변경이 없는 docs 정리
- 주문/회계/런타임 의미를 건드리지 않는 국소 refactor

우선순위 규칙: 전환 영역에서 이 문서와 현재 branch 코드가 충돌하면 현재 branch 코드를 우선한다. 이 문서는 안정 불변식을 먼저 정리하고, 전환 중 항목은 고정된 설계가 아니다.

## 1. 계속 유지해야 할 안정 규칙

- `PAPER`는 로컬 모의 실행이다.
- `REAL`은 거래소 기반 비동기 lifecycle을 갖는다.
- `TEST`는 live order 없이 거래소 test path로 검증한다.
- `SHADOW`는 live execution 없이 intent만 기록한다.
- 잘못된 런타임 값은 fail-safe로 처리한다.
- 가격, 수량, tick size, 최소 주문금액 검증은 우회하면 안 된다.
- submit ambiguity가 blind resubmit으로 이어지면 안 된다.
- ambiguous submit 이후 복구는 identifier 기반 조회를 우선한다.
- 같은 fill은 두 번 적용되면 안 된다.
- `upbit_identifier`는 attempt 간 재사용하면 안 된다.
- 반대 방향 open order conflict 처리는 함부로 제거하면 안 된다.
- daily loss basis 의미를 의도 없이 바꾸면 안 된다.
- `PAPER` 즉시 local fill semantics와 real-mode 비동기 lifecycle을 혼동하면 안 된다.

## 2. V3 멀티유저 불변식

- 주문, attempt, fill, 포지션, PnL, wallet, 자격증명, bot runtime은 사용자 scope를 가져야 한다.
- 사용자 간 데이터 혼합은 허용되지 않는다.
- 한 사용자 tick 실패가 다른 사용자의 tick을 중지하거나 오염시키면 안 된다.
- runtime control은 사용자별이어야 하며 전역 단일 switch가 아니어야 한다.
- idempotency와 reconcile은 사용자 scope 안에서만 안전하게 동작해야 한다.
- 일반 runtime의 자격증명 로딩은 사용자별이어야 한다.
- 인증된 `/api/me/*` 읽기/쓰기 경로는 global owner bridge에 의존하면 안 된다.

## 3. Trading mode 기준

Mode semantics는 활성 사용자 runtime context마다 적용된다.

- `PAPER`: live exchange submit 없음. local simulated fill/accounting path 사용.
- `REAL`: Upbit live order submit과 exchange-backed lifecycle 사용.
- `TEST`: Upbit test-order path 사용. live order 없음.
- `SHADOW`: validation과 intent 기록만 수행.

중요:

- `REAL`, `TEST`, `SHADOW`는 활성 사용자 자격증명이 필요하다.
- non-paper mode가 하나의 거래소 계정을 공유한다고 가정하면 안 된다.

## 4. Runtime config 불변식

- runtime config는 validation/sanitization 이후에만 authoritative하다.
- 잘못된 값은 clamp하거나 안전한 기본값으로 fallback한다.
- timeout은 `1..120`으로 clamp한다.
- reprice attempt는 `1..10`으로 clamp한다.
- `reprice_step_bps`는 `1..500`으로 clamp한다.
- notify interval은 `300..86400`으로 clamp한다.
- `daily_loss_basis`는 `TOTAL` 또는 `REALIZED_ONLY`만 허용하며, 잘못된 값은 안전하게 fallback한다.

새 코드에서 durable invariant로 삼으면 안 되는 legacy pattern:

- 하나의 전역 `bot_config(id=1)` row
- 모든 사용자가 공유하는 runtime state
- 하나의 전역 bot enable/disable switch

현재 branch 메모:

- `load_for_user()`는 먼저 `user_bot_config`를 사용하고, 사용자 row가 없을 때만 호환성을 위해 global `bot_config(id=1)`로 fallback한다.

## 5. 주문 실행 불변식

- `delta = target_qty - current_qty`
- `abs(delta) < 1e-8`이면 주문하지 않는다.
- `delta > 0`이면 buy side다.
- `delta < 0`이면 sell side다.
- 하나의 logical order는 여러 attempt를 가질 수 있다.
- submit 전 price, volume, tick size, rounding, 최소 주문금액을 검증한다.
- allowlist 정책이 market을 거부하면 local reject 후 거래소에 submit하지 않는다.
- submit uncertainty 이후 blind resubmit을 하면 안 된다.
- attempt마다 one-time `upbit_identifier`를 사용한다.
- sync 후 일부 체결된 open order는 `PARTIAL`이어야 한다.

사용자 scope 기준:

- duplicate logical order 방지는 같은 사용자 scope 안에서 판단한다.
- identifier recovery와 order matching은 사용자 간에 섞이면 안 된다.

## 6. Reconcile 및 accounting 불변식

- reconcile은 exchange/account data를 local trading state에 반영한다.
- exchange state는 있으나 local state가 없으면 recovery가 local record를 만들 수 있다.
- fill ingestion은 idempotent해야 한다.
- 적용된 fill이 position과 PnL update를 만든다.
- unrealized PnL은 현재 mark/reference price에 의존할 수 있다.
- `cash_krw`류 balance 계산은 올바른 account scope를 사용해야 한다.

사용자 scope 기준:

- reconcile이 한 사용자의 position/wallet을 다른 사용자의 account data로 덮어쓰면 안 된다.
- PnL/equity 계산이 서로 다른 사용자를 accidental aggregation하면 안 된다.

## 7. 주문 상태와 의미

Local open-state 개념:

- `NEW`
- `SENT`
- `OPEN`
- `PARTIAL`
- `WAIT`

그 외 중요 상태:

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

## 8. 전환 중 항목

이미 반영된 항목:

- Scheduler는 `MultiUserTradingScheduler`를 사용하며 사용자별 failure isolation을 갖는다.
- `/api/me/*` 읽기/쓰기는 인증 사용자 identity 기준으로 사용자 scope가 적용된다.
- Bot start/stop과 runtime status는 사용자별 `user_bot_runtime` 기준이다.
- 핵심 trading/accounting table(`orders`, `positions`, `daily_equity`, `paper_wallet`)은 필요한 곳에 사용자 scope를 가진다.

남아 있는 compatibility zone:

- `ConfigRepo.load_for_user()`는 `user_bot_config`가 없으면 global `bot_config(id=1)`로 fallback한다.
- 일부 constructor path는 `user_id`가 생략되면 owner user를 해석한다.

durable invariant로 삼으면 안 되는 항목:

- global `bot_config(id=1)` fallback이 영구적으로 필요하다는 전제
- 새 코드에서 명시적 user scope보다 implicit owner resolution을 선호하는 전제

## 9. V3에서 깨면 안 되는 규칙

1. 사용자 간 데이터 혼합을 만들지 않는다.
2. 인증된 `/api/me/*` 읽기를 global single-owner bridge path로 보내지 않는다.
3. 명시적 compatibility fallback 밖에서 `bot_config(id=1)`을 필수 runtime dependency로 재도입하지 않는다.
4. 한 사용자의 runtime 실패가 다른 사용자를 멈추게 하지 않는다.
5. ambiguous submit 이후 identifier 기반 recovery를 깨지 않는다.
6. 같은 fill을 두 번 적용하지 않는다.
7. tick size, quantity rounding, 최소 주문금액 validation을 우회하지 않는다.
8. `PAPER` local simulation과 exchange-backed mode를 혼동하지 않는다.
9. 정상 멀티유저 운영에서 credentials/runtime을 process-global로 가정하지 않는다.
10. idempotency 또는 reconcile logic이 사용자 간 record를 match하지 않게 한다.

## 10. 권장 작업 prompt 순서

1. `docs/context_anchor_v3_transition.md`를 읽는다.
2. 관련 Notion Story와 현재 branch code를 확인한다.
3. 유지할 invariant를 먼저 말한다.
4. backend/frontend/tests/docs를 함께 수정한다.
5. 변경 결과를 Story/Task/Acceptance에 매핑한다.

예시:

> `docs/context_anchor_v3_transition.md`를 먼저 읽고, `2026-03-10 Post-V3 Ops Hardening Backlog`의 Story `Sx`를 구현한다. 사용자 간 데이터 혼합 금지, `/api/me/*` owner bridge 재도입 금지, 필수 global `bot_config(id=1)` 의존 금지, 사용자별 failure isolation, admin boundary를 유지한다. backend/tests/docs를 함께 수정하고, frontend를 건드렸다면 frontend도 함께 검증한 뒤 acceptance mapping을 반환한다.
