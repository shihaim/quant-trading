# P3 구현 보고서 (주문 정책, 슬리피지, 운영성)

- 작성일: 2026-02-25
- 대상: 기획/개발 공용
- 기준 문서: `P3._주문_정책슬리피지운영성(나중에_수익률과_직결)_-_재정렬.pdf`

## 1) 목적

P3의 목표는 신호만으로 주문을 내는 단계를 넘어서, 실행 비용과 체결 안정성을 통제하는 운영 가능한 실행 레이어를 만드는 것입니다.

- 미세 리밸런싱 차단으로 불필요 주문 감소
- 주문 의도(ENTRY/EXIT/REBALANCE) 기반 정책 실행
- 슬리피지와 체결 품질 지표의 구조화 저장
- OPEN 주문 충돌 및 장기 미체결 리스크 완화
- 예산 초과 시 경보와 자동 HALT로 손실 확산 방지

## 2) 반영 범위 요약

아래 항목을 코드에 반영했습니다.

- `P3-01` 미세 리밸런싱 게이트
- `P3-02` OrderPolicy 레이어
- `P3-03` 체결 품질 및 슬리피지 측정 저장
- `P3-04` 지정가 타임아웃 기반 재호가 루프
- `P3-05` OPEN 주문 충돌 정책 (반대 주문 선취소)
- `P3-06` 슬리피지 예산 경보 및 자동 HALT
- `P3-07` 운영 상태 스냅샷 및 주기 알림

## 3) 주요 변경 사항

### 3.1 주문 진입 게이트 강화

주문 생성 전 두 가지 게이트를 통과해야 합니다.

- 노출 변화폭 게이트:
  - `abs(target_exposure - current_exposure) < min_rebalance_threshold_pct`이면 스킵
- 최소 주문 금액 게이트:
  - `|target_qty - current_qty| * close_price < (5000 + min_order_krw_buffer)`이면 스킵

효과:

- 소액 계좌에서 수수료만 누적되는 잦은 미세 주문을 억제

### 3.2 OrderPolicy 레이어 도입

신규 파일 `trader/trading/order_policy.py`를 추가했습니다.

- `OrderIntent`: `ENTRY`, `EXIT`, `REBALANCE`
- `OrderPolicyConfig`: timeout, 재호가 횟수, 재호가 스텝
- `OrderPolicy.decide(...)`: 의도별 주문 정책 결정

ExecutionEngine은 정책 계산 결과를 받아 실행만 담당합니다.

### 3.3 체결 지표 저장 (`trade_metrics`)

주문 1건 단위로 체결 품질 지표를 저장합니다.

- `intended_price`
- `filled_vwap_price`
- `slippage_abs`, `slippage_pct` (불리한 방향을 양수로 정의)
- `fee_abs`
- `time_to_fill_ms`
- `partial_fill_count`

효과:

- 운영 후 체결 속도, 슬리피지, 수수료를 수치로 분석 가능

### 3.4 정책 기반 재호가 루프

REAL 모드에서 의도별 timeout과 재시도 횟수 기준으로 재호가 루프를 수행합니다.

- `fill_timeout_sec_entry`, `fill_timeout_sec_exit`, `fill_timeout_sec_rebalance`
- `max_reprice_attempts_entry`, `max_reprice_attempts_exit`, `max_reprice_attempts_rebalance`
- `reprice_step_bps`

`EXIT`는 상대적으로 공격적인 정책을 적용할 수 있도록 구성해 장시간 미체결 방치를 줄였습니다.

### 3.5 OPEN 주문 충돌 정책

신규 주문 전에 동일 마켓의 OPEN 주문을 조회하고, 반대 방향 주문이 있으면 선취소 후 신규 주문을 진행합니다.

효과:

- 반대 신호 전환 구간에서 주문 꼬임과 중복 리스크 감소

### 3.6 슬리피지 예산 경보와 자동 HALT

설정 컬럼으로 슬리피지 예산을 관리합니다.

- `slippage_budget_entry_pct`
- `slippage_budget_exit_pct`
- `slippage_budget_breach_halt_count`

동작:

- 예산 초과 시 로그 및 텔레그램 경보
- 일중 초과 누적이 임계치 이상이면 `bot_config.is_enabled=0`으로 자동 HALT

### 3.7 운영 상태 알림

신규 파일 `trader/trading/health.py`를 통해 상태 스냅샷을 생성하고 스케줄러가 주기적으로 알림을 보냅니다.

- 마지막 성공 루프 시각
- 최근 15분 오류 수
- 최근 15분 rate-limit 수
- OPEN 주문 수
- 현재 노출 비율
- 당일 손익 비율
- HALT 상태

## 4) 데이터 모델 및 스키마 변경

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

- `intent` 컬럼 추가 (`ENTRY`, `EXIT`, `REBALANCE`)

### 4.3 신규 테이블 `trade_metrics`

- 주문별 체결 품질 지표 저장
- `order_id` 유니크 제약 (주문 1건당 지표 1건)

### 4.4 뷰 및 문서 동기화

- `trade_metrics_kst` 포함 KST 조회용 뷰 갱신
- 스키마 설명 테이블(`schema_*_docs`) 동기화

## 5) 런타임 동작 흐름

1. 캔들 조회 및 신호 계산
2. 리스크 엔진에서 목표 노출 산출
3. 주문 진입 게이트(변화폭, 최소 주문 금액) 검증
4. 주문 의도 분류 및 정책 결정
5. 충돌 OPEN 주문 선취소
6. 주문 제출, 동기화, 필요 시 재호가
7. fills 반영 및 trade_metrics 저장
8. 슬리피지 예산 초과 경보 및 자동 HALT 판정
9. 운영 상태 스냅샷 주기 알림

## 6) 테스트 결과

신규 및 보강 테스트를 반영했습니다.

- `tests/test_rebalance_gate.py`
- `tests/test_order_policy.py`
- `tests/test_trade_metrics.py`
- `tests/test_execution_and_paper.py` (충돌 정책 케이스 포함)
- `tests/test_scheduler_reload.py` (state 구조 반영)

실행 결과:

- `python -m pytest -q`
- `40 passed`

## 7) 운영 확인 포인트

로그 키워드:

- `scheduler_order_skipped ... min_rebalance_threshold`
- `execution_order_policy ...`
- `execution_trade_metric_upserted ...`
- `scheduler_slippage_budget_breach ...`
- `scheduler_auto_halt_by_slippage ...`

DB 확인 포인트:

- `bot_config.is_enabled` (자동 HALT 여부)
- `trade_metrics` (VWAP, 슬리피지, 체결 시간)
- `orders.intent` (의도 분류)

## 8) 미반영 항목과 후속 우선순위

문서의 제안 항목 중 아직 직접 반영하지 않은 항목:

- `max_weekly_loss_pct`, `max_monthly_loss_pct`
- `cooldown_hours_on_halt`
- `max_new_orders_per_day`, `max_orders_per_week`
- `min_edge_pct` (예측 기반 스킵 필터)

권장 우선순위:

1. 주간/월간 손실 제한 + HALT 후 쿨다운
2. 일간/주간 신규 주문 횟수 제한
3. `trade_metrics` 실측 기반 `min_edge_pct` 도입

## 9) 권장 프리셋 (월 2~3% 보수 운용)

### 9.1 `bot_config` 권장값

```json
{
  "is_enabled": true,
  "timeframe": "240m",
  "markets_json": ["KRW-BTC"],
  "target_exposure_pct": 0.30,
  "daily_loss_basis": "REALIZED_ONLY",
  "max_daily_loss_pct": 0.005,
  "max_total_exposure_pct": 0.50,
  "max_per_market_exposure_pct": 0.50,
  "min_rebalance_threshold_pct": 0.05,
  "min_order_krw_buffer": 0,
  "fill_timeout_sec_entry": 10,
  "fill_timeout_sec_exit": 4,
  "fill_timeout_sec_rebalance": 10,
  "max_reprice_attempts_entry": 2,
  "max_reprice_attempts_exit": 1,
  "max_reprice_attempts_rebalance": 1,
  "reprice_step_bps": 10,
  "slippage_budget_entry_pct": 0.0005,
  "slippage_budget_exit_pct": 0.0020,
  "slippage_budget_breach_halt_count": 3,
  "status_notify_interval_seconds": 14400
}
```

### 9.2 적용 SQL 예시

```sql
UPDATE bot_config
SET
  is_enabled = 1,
  timeframe = '240m',
  markets_json = '["KRW-BTC"]',
  target_exposure_pct = 0.30,
  daily_loss_basis = 'REALIZED_ONLY',
  max_daily_loss_pct = 0.005,
  max_total_exposure_pct = 0.50,
  max_per_market_exposure_pct = 0.50,
  min_rebalance_threshold_pct = 0.05,
  min_order_krw_buffer = 0,
  fill_timeout_sec_entry = 10,
  fill_timeout_sec_exit = 4,
  fill_timeout_sec_rebalance = 10,
  max_reprice_attempts_entry = 2,
  max_reprice_attempts_exit = 1,
  max_reprice_attempts_rebalance = 1,
  reprice_step_bps = 10,
  slippage_budget_entry_pct = 0.0005,
  slippage_budget_exit_pct = 0.0020,
  slippage_budget_breach_halt_count = 3,
  status_notify_interval_seconds = 14400,
  updated_at = CURRENT_TIMESTAMP
WHERE id = 1;

UPDATE timeframe_config
SET
  is_enabled = CASE WHEN timeframe = '240m' THEN 1 ELSE 0 END,
  updated_at = CURRENT_TIMESTAMP;
```

### 9.3 운영 주의사항

- 자산이 1~2만원 수준이면 최소 주문 금액(5,000 KRW) 제약으로 주문 스킵이 자주 발생할 수 있습니다.
- `max_daily_loss_pct=0.005`는 보수적인 설정이라 HALT가 빠르게 발생할 수 있습니다.
- 초기 운영은 SHADOW 또는 TEST로 충분히 검증한 뒤 REAL 비중을 단계적으로 확대하는 방식을 권장합니다.
