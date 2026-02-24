# 5m 전환 체크리스트 (2026-02-24)

## 1) 적용 상태
- `.env`
  - `MIN_STRATEGY_CANDLES=360`
  - `LOG_LEVEL=INFO`
- `bot_config(id=1)`
  - `timeframe='5m'`
  - `markets_json='["KRW-BTC"]'`
  - `is_enabled=1`

## 2) 재시작
- `.env` 변경사항 반영을 위해 `main` 프로세스를 재시작한다.
- 실행 명령:
```powershell
python -m trader.app.main
```

## 3) 모니터링 포인트 (로그)
- 시작 로그:
  - `scheduler_started`
- 트리거 로그(5분마다):
  - `scheduler_tick_triggered`
  - `scheduler_next_run_scheduled`
- 전략/주문 로그:
  - `scheduler_signal`
  - `scheduler_order_ok` 또는 `scheduler_order_skipped`
- API 로그:
  - `upbit_request ...`
  - `network_error/retryable_status/http_error` 발생 여부

## 4) 첫 30분 점검 기준
- 5분 간격으로 트리거가 6회 이상 발생
- `upbit_request retryable_status` 과다 반복이 없음
- `scheduler_order_error` 연속 발생이 없음
- DB `orders`/`fills` 상태와 로그가 일치

## 5) 즉시 롤백 방법
- `bot_config.timeframe`을 `15m`로 되돌림
- 또는 `bot_config.is_enabled=0`으로 즉시 주문 중지
