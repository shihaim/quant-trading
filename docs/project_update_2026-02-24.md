# Quant Trading MVP 작업 보고서

- 작성일: 2026-02-24
- 대상: 기획/개발 공용
- 프로젝트 경로: `F:\src\quant-trading`

## 1. 작업 목표

개인용 코인 자동매매 MVP를 빠르게 구현하되, 수익률보다 아래 항목을 우선하도록 구성함.

- 사고 방지(중복 주문, 재시작 후 상태 꼬임, 체결 누락)
- 봉 마감 기준 실행(틱 기반 난사 방지)
- 설정 변경(timeframe/마켓/리스크 한도)의 런타임 반영
- 로컬 DB 기반 영속화 및 복구 가능성 확보

## 2. 구현 범위 요약

### 2.1 코어 엔진

- 단일 서비스 아키텍처로 초기 MVP 구성
- 모듈 분리:
  - 데이터: CandleService
  - 전략: EMA(20/60) Cross
  - 리스크: 일일 손실/노출 제한
  - 실행: 주문 생성/상태 동기화/재시도
  - 포트폴리오: 포지션/체결 반영
  - 스케줄러: 봉 마감 트리거 + 설정 리로드

### 2.2 상태 영속화(DB)

- SQLite 기반 테이블 구성:
  - `bot_config`, `candles`, `orders`, `fills`, `positions`, `paper_wallet`
- 보강 필드:
  - `orders.retry_count`, `orders.last_error`
  - `fills.is_applied` (중복 체결 반영 방지)

### 2.3 업비트 연동

- 공개 시세 API(캔들) 연동
- 인증/JWT 기반 private API 래핑(계좌, 주문, 주문조회)
- 요청 레이트리밋 + 재시도(backoff) 처리

### 2.4 실행 안정성 강화

- idempotency key 기반 `client_order_id` 생성
- 동일 봉/마켓 재실행 시 중복 주문 방지
- 주문 전송 실패 시 재시도 + `identifier` 조회 복구
- 부분체결 상태(PARTIAL) 반영

### 2.5 Reconcile(정합성 복구)

- 계좌 잔고(`/v1/accounts`) → 로컬 `positions` 동기화
- 미체결 주문(`/v1/orders/open`) → 로컬 `orders` 동기화
- 로컬 open 주문 재조회(`/v1/order`) + 신규 fill 반영

### 2.6 운영 모드

- `TRADING_MODE=paper` / `TRADING_MODE=real` 분리
- 기본값은 `paper`
- `paper` 모드:
  - 주문 즉시 가상 체결
  - 수수료 반영
  - `paper_wallet` 현금 잔고 업데이트

### 2.7 백테스트

- 로컬 DB 캔들 재생형 백테스트 추가
- 커맨드:
  - `python -m trader.app.backtest --market KRW-BTC --timeframe 15m`
- 수수료/슬리피지 적용 가능

## 3. 실행/검증 결과

### 3.1 실행 결과

- 앱 실행(`python -m trader.app.main`) 정상 기동 확인
- 백테스트 실행은 초기 캔들 부족 오류 확인 후 백필로 해결
- 재실행 결과:
  - `market=KRW-BTC timeframe=15m`
  - `trades=0`
  - `start_equity=1000000.00 end_equity=1000000.00`

### 3.2 안전성 관련 확인

- 실주문 테스트는 수행하지 않음
- main 실행은 `paper` 모드 기준으로 확인
- 공개 시세 캔들 API 호출은 수행함(백필 목적)

## 4. 주요 파일(참고)

- 엔트리포인트: `trader/app/main.py`
- 백테스트 CLI: `trader/app/backtest.py`
- 스케줄러: `trader/trading/scheduler.py`
- 실거래 실행 엔진: `trader/trading/execution.py`
- 페이퍼 실행 엔진: `trader/trading/paper_execution.py`
- 리컨실: `trader/trading/reconcile.py`
- 포트폴리오 반영: `trader/trading/portfolio.py`
- 업비트 클라이언트: `trader/exchange/upbit_client.py`
- DB 모델: `trader/data/models.py`
- 설정 로드: `trader/config/settings.py`, `trader/config/config_repo.py`

## 5. 코드 가독성 개선

- 함수/메서드 단위 한글 docstring 주석 추가
- 핵심 패키지 `__init__.py` 설명도 한글로 통일

## 6. 현재 리스크/제약

- 실계좌 주문 흐름(real mode)은 미검증 상태
- 전략 로직은 안정성 검증용 단순 EMA Cross 수준
- 테스트는 기본 단위 테스트 위주이며 통합 테스트 미구축

## 7. 권장 후속 작업

1. 실계좌 소액 리허설 환경에서 end-to-end 검증
2. 일일 PnL 계산(실현+미실현) 고도화 및 하드 스탑 자동화
3. 주문 타입(시장가/지정가) 정책 분리 및 슬리피지 제어 강화
4. Alembic 도입으로 스키마 마이그레이션 정식화
5. 운영 로그/알림(에러 코드, 재시도 횟수, 주문 지연) 대시보드화

