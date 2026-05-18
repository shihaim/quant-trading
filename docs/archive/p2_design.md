# P2 손익/리스크 정책

## 범위

이 문서는 스케줄러가 리스크 중지(HALT) 판단을 위해 일일 손익(PnL)을
어떻게 계산하는지 정의한다.

## 시가평가 시점

- 평가 시점: 스케줄러 틱 기준 캔들 종가 시점
- 기준 가격: 가장 최근에 완성된 캔들의 종가 (`candles[-1].close`)
- 이유: 백테스트와 실거래 간 정렬을 맞추고, HALT 동작을 재현 가능하게 유지하기 위함

## 자산 공식

- `market_value = sum(position.qty * mark_price)`
- `equity = cash_krw + market_value`
- 일일 TOTAL 손익:
- `daily_pnl_abs = equity - start_equity`
- `daily_pnl_pct = daily_pnl_abs / start_equity` (`start_equity > 0`인 경우, 아니면 `0`)

## 일일 기준선(Baseline)

- 기준 키: UTC 날짜 (`daily_equity.date_utc`)
- UTC 기준 하루의 첫 실행 시:
- `start_equity = current_equity`
- `start_realized_pnl = current_realized_pnl`
- 같은 UTC 날짜 내에서는:
- 기준선 필드는 고정
- 최신 스냅샷 필드만 갱신

## `daily_loss_basis` 옵션

`bot_config.daily_loss_basis`는 아래 두 값을 지원한다.

- `TOTAL` (기본값)
- 자산 기준 일일 손익(실현 + 미실현)을 사용
- `REALIZED_ONLY`
- 실현 손익 변화분만 사용
- `realized_daily_abs = current_realized_pnl - start_realized_pnl`
- `realized_daily_pct = realized_daily_abs / start_equity` (`start_equity > 0`인 경우, 아니면 `0`)

## 리스크 중지 규칙

- 리스크 엔진 입력값: 선택된 기준에 따라 계산된 `daily_pnl_pct`
- 중지 조건:
- `daily_pnl_pct <= -abs(max_daily_loss_pct)`
- 중지 시 스케줄러는 신규 주문 생성을 건너뛰고, HALT 로그 및 알림을 발생시킨다.
