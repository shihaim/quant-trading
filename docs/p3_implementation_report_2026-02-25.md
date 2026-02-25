# P3 구현 보고서 (주문 정책/슬리피지/운영성)

- 작성일: 2026-02-25
- 대상: 기획/개발 공용
- 기준 문서: `P3._주문_정책슬리피지운영성(나중에_수익률과_직결)_-_재정렬.pdf`

## 1) 목적

P3의 핵심 목표는 "신호가 있어도 아무 주문이나 내지 않고", 비용/체결/운영 리스크를 통제하는 실행 레이어를 만드는 것입니다.

- 미세 리밸런싱 차단으로 불필요 거래 억제
- 정책 기반 주문(ENTRY/EXIT/REBALANCE)으로 재현성 확보
- 슬리피지/체결 품질을 수치화해 튜닝 가능 상태 확보
- 충돌 주문/장시간 미체결 등 운영 리스크 감소

## 2) 이번 반영 범위 요약

아래 항목을 코드에 반영했습니다.

- `P3-01` 미세 리밸런싱 게이트
- `P3-02` OrderPolicy 레이어
- `P3-03` 체결 품질/슬리피지 실측 저장
- `P3-04` 지정가 타임아웃 + 재호가 루프
- `P3-05` OPEN 주문 충돌 정책(Option A)
- `P3-06` 슬리피지 예산 경보 + 자동 HALT(옵션)
- `P3-07` 운영 상태 스냅샷/주기 알림

## 3) 주요 기능 변경

### 3.1 리밸런싱/주문 진입 게이트

주문 생성 전 아래 조건을 통과해야 합니다.

- 노출 변화폭 게이트:
  - `abs(target_exposure - current_exposure) < min_rebalance_threshold_pct` 이면 스킵
- 주문 금액 게이트:
  - `|target_qty-current_qty| * close_price < (5000 + min_order_krw_buffer)` 이면 스킵

효과:
- 소액 운용에서 수수료만 누적되는 미세 주문을 강하게 차단

### 3.2 OrderPolicy 레이어 도입

신규 파일 `trader/trading/order_policy.py` 추가:

- `OrderIntent`: `ENTRY`, `EXIT`, `REBALANCE`
- `OrderPolicyConfig`: timeout/재호가 횟수/호가 스텝
- `OrderPolicy.decide(...)`: intent별 정책 결정

ExecutionEngine은 정책 "결과"만 받아 실행합니다.

### 3.3 체결 지표 저장(`trade_metrics`)

주문별 체결 품질 지표를 DB에 저장합니다.

- `intended_price`
- `filled_vwap_price`
- `slippage_abs`, `slippage_pct` (불리한 방향 +값)
- `fee_abs`
- `time_to_fill_ms`
- `partial_fill_count`

효과:
- 운영 후 "체결 시간/슬리피지/수수료"를 숫자로 분석 가능

### 3.4 정책 기반 재호가 루프

REAL 모드에서 정책 기준으로 재시도/재호가를 수행합니다.

- `fill_timeout_sec_*`
- `max_reprice_attempts_*`
- `reprice_step_bps`

`EXIT`는 공격적 정책(AGGRESSIVE_LIMIT)으로 설정 가능하며, OPEN 주문 장기 방치를 줄였습니다.

### 3.5 OPEN 주문 충돌 정책

신규 주문 전에 동일 마켓 OPEN 주문을 조회하고,
반대 방향 주문이 있으면 선취소 후 신규 주문을 진행합니다.

효과:
- 반대 신호 구간에서 주문 꼬임/중복 리스크 감소

### 3.6 슬리피지 예산 경보 + 자동 HALT

슬리피지 예산을 설정으로 관리합니다.

- `slippage_budget_entry_pct`
- `slippage_budget_exit_pct`
- `slippage_budget_breach_halt_count`

동작:
- 예산 초과 시 텔레그램/로그 경보
- 일중 초과 누적이 임계치 이상이면 `bot_config.is_enabled=0` 자동 HALT

### 3.7 운영 상태(Health) 알림

신규 파일 `trader/trading/health.py` 추가:

- 마지막 성공 루프 시각
- 최근 15분 오류 수
- 최근 15분 rate-limit 수
- open orders 수
- exposure_pct
- daily_pnl_pct
- halted 여부

스케줄러가 주기적으로 상태 메시지를 발송합니다.

## 4) 데이터 모델/스키마 변경

### 4.1 `bot_config` 확장

추가 컬럼:

- `min_rebalance_threshold_pct`
- `min_order_krw_buffer`
- `fill_timeout_sec_entry`
- `fill_timeout_sec_exit`
- `fill_timeout_sec_rebalance`
- `max_reprice_attempts_entry`
- `max_reprice_attempts_exit`
- `max_reprice_attempts_rebalance`
- `reprice_step_bps`
- `slippage_budget_entry_pct`
- `slippage_budget_exit_pct`
- `slippage_budget_breach_halt_count`
- `status_notify_interval_seconds`

### 4.2 `orders` 확장

- `intent` 컬럼 추가 (`ENTRY/EXIT/REBALANCE`)

### 4.3 신규 테이블 `trade_metrics`

- 주문별 실행 품질 지표 저장
- `order_id` unique(주문 1건당 지표 1건)

### 4.4 뷰/문서 동기화

- `trade_metrics_kst` 포함 KST 뷰 갱신
- 스키마 설명 테이블(`schema_*_docs`) 갱신

## 5) 런타임 동작 흐름

1. 캔들/리밸런싱 신호 계산
2. 리스크 엔진으로 target exposure 확정
3. 주문 전 게이트(미세 변화/최소 금액+버퍼)
4. intent 계산 + 정책 결정
5. 충돌 OPEN 주문 선취소
6. 주문 제출/동기화/재호가 루프
7. fills 반영 + trade_metrics 저장
8. 슬리피지 예산 경보/자동 HALT 판정
9. 상태 스냅샷 주기 알림

## 6) 테스트 결과

신규/보강 테스트를 반영했습니다.

- `tests/test_rebalance_gate.py`
- `tests/test_order_policy.py`
- `tests/test_trade_metrics.py`
- `tests/test_execution_and_paper.py` (충돌 정책 케이스 추가)
- `tests/test_scheduler_reload.py` (state 구조 변경 반영)

실행 결과:

- `python -m pytest -q`
- `40 passed`

## 7) 운영 시 확인 포인트

- 로그 키워드:
  - `scheduler_order_skipped ... min_rebalance_threshold`
  - `execution_order_policy ...`
  - `execution_trade_metric_upserted ...`
  - `scheduler_slippage_budget_breach ...`
  - `scheduler_auto_halt_by_slippage ...`

- DB 점검:
  - `bot_config.is_enabled` (자동 HALT 여부)
  - `trade_metrics` (VWAP/슬리피지/체결시간)
  - `orders.intent` (정책 분류)

## 8) 미지원/후속 항목

P3 문서 내 아래 항목은 현재 코드에 직접 반영되지 않았습니다.

- `max_weekly_loss_pct`, `max_monthly_loss_pct`
- `cooldown_hours_on_halt`
- `max_new_orders_per_day`, `max_orders_per_week`
- `min_edge_pct` (예측 기반 스킵 필터)

권장 순서:

1. 주/월 손실 제한 + 쿨다운
2. 일/주 주문 횟수 제한
3. `min_edge_pct` 실측 기반 도입(현재 `trade_metrics` 데이터 활용)
