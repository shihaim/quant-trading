# P2 후속작업 구현 보고서

- 작성일: 2026-02-25
- 대상: 기획/개발 공용
- 기준 문서:
  - `docs/p2_implementation_report_2026-02-25.pdf`
  - `docs/p2_followup_report_2026-02-25.pdf`

## 1) 배경

P2 본 구현 이후 후속작업으로 제안된 항목 중, P3 착수 전에 가성비가 높은 2개를 우선 반영했다.

- `daily_loss_basis` 옵션화 (`TOTAL` / `REALIZED_ONLY`)
- PnL 평가 시점/공식 정책 문서화 (`docs/archive/p2_design.md`)

## 2) 이번 반영 범위

### 2.1 daily_loss_basis 옵션화

`bot_config`에 일손실 계산 기준을 선택할 수 있는 컬럼을 추가했다.

- 신규 컬럼: `bot_config.daily_loss_basis`
- 허용 값:
  - `TOTAL` (기본)
  - `REALIZED_ONLY`
- 기본값/보정 정책:
  - 컬럼이 없으면 마이그레이션에서 추가
  - `NULL`/빈값이면 `TOTAL`로 보정
  - 비정상 문자열은 로딩 시 `TOTAL`로 정규화

반영 파일:

- `trader/data/models.py`
- `trader/data/db.py`
- `trader/config/config_repo.py`

### 2.2 REALIZED_ONLY 계산 정확도 보강

`REALIZED_ONLY`를 단순 누적 실현손익이 아니라 "당일 시작 대비 실현손익 변화량"으로 계산하도록 확장했다.

- `daily_equity.start_realized_pnl` 컬럼 추가
- 일자 최초 스냅샷 생성 시 시작 실현손익을 고정 저장
- 당일 손익 계산:
  - `realized_daily_abs = current_realized_pnl - start_realized_pnl`
  - `realized_daily_pct = realized_daily_abs / start_equity` (`start_equity > 0`)

반영 파일:

- `trader/data/models.py`
- `trader/data/db.py`
- `trader/trading/pnl.py`
- `trader/trading/scheduler.py`

### 2.3 정책 문서화

PnL 평가 시점과 공식을 명시한 운영 정책 문서를 추가했다.

- 신규 문서: `docs/archive/p2_design.md`
- README에 정책 문서 링크 및 런타임 설정 항목(`daily_loss_basis`) 반영

반영 파일:

- `docs/archive/p2_design.md`
- `README.md`

## 3) 동작 방식 요약

스케줄러 틱에서 다음 순서로 처리한다.

1. 캔들 close 기준 mark price 수집
2. 리컨실/포지션 반영
3. `daily_equity` 스냅샷 업데이트
4. `daily_loss_basis`에 따라 `daily_pnl_pct` 계산
5. `RiskEngine`에 계산된 값 주입 후 HALT 판정

## 4) 테스트

아래 테스트를 추가/확장했고 전체 통과를 확인했다.

- `tests/test_config_repo.py`
  - `daily_loss_basis` 로딩/정규화 검증
- `tests/test_pnl.py`
  - `start_realized_pnl` 저장
  - `REALIZED_ONLY` 계산 검증
- `tests/test_scheduler_pnl.py`
  - 스케줄러가 기준값을 리스크 엔진에 전달하는지 검증

실행 결과:

- `python -m pytest -q` -> `32 passed`

## 5) 운영 적용 상태

운영 DB(`bot_config.id=1`) 기준값을 `REALIZED_ONLY`로 변경 완료.

- 확인값: `(1, 'REALIZED_ONLY')`
- 상태 요약: P2 후속 핵심 2개 항목 반영 완료, P3 착수 가능 상태

## 6) 기대 효과

- 급락장/변동장에서도 손실 통제 기준을 명시적으로 운영 가능
- P3(주문 정책/슬리피지) 단계에서 리스크 트리거 기준 혼선 감소
- 운영 로그 해석 시 "무엇을 기준으로 HALT가 걸렸는지" 설명 가능성 향상

## 7) 남은 후속 작업

- 필수 남은 작업: 없음
- 운영 로그 기반 파라미터 튜닝:
  - P3 실측 데이터(`trade_metrics`, 주문 체결 로그)가 충분히 쌓인 뒤 진행
  - 현 시점에서는 고정값 변경보다 관측 데이터 축적을 우선
