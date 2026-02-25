# P2 구현 보고서 (손실 통제/정산 PnL 정확도 고도화)

- 작성일: 2026-02-25
- 대상: 기획/개발 공용
- 기준 문서: `P2._손실_통제정산(pnl)_정확도_고도화_(실거래_안정성의_핵심).pdf`

## 1) 목적

P2의 목적은 “일중 손실 통제”를 실제 수치 기반으로 동작시키는 것입니다.

- 일별 기준 자산(baseline) 영속화
- 미실현손익(unrealized PnL) 계산/저장
- `daily_pnl_pct`를 리스크 엔진에 실제 주입

즉, 기존의 `daily_pnl_pct=0` 하드코딩 상태를 제거하고, 실계정/페이퍼 모두에서 동일한 손실 통제 체계로 정렬했습니다.

## 2) 이번 반영 범위 요약

이번 작업에서 P2 핵심 3개를 완료했습니다.

- `P2-01` 일별 기준 자산 테이블 추가 (`daily_equity`)
- `P2-02` 포지션 미실현손익 계산/갱신 로직 추가
- `P2-03` `daily_pnl_pct` 계산 후 `RiskEngine`에 실제 값 전달

## 3) 기획자 관점 요약

### 3.1 무엇이 달라졌나

- 봇이 매 실행 주기마다 “오늘 시작 자산 대비 손익률(%)”을 계산합니다.
- 손실률이 `max_daily_loss_pct` 이하로 내려가면 리스크 엔진이 즉시 HALT 판단을 내립니다.
- HALT 시 주문 생성을 건너뛰고 로그/알림으로 이유를 남깁니다.

### 3.2 왜 중요한가

- 실거래 안정성의 핵심인 “손실 컷”이 더 이상 더미 값(0) 기반이 아닙니다.
- 동일 날짜에는 시작 기준자산이 고정되어 일일 손익률이 일관되게 계산됩니다.
- 날짜가 바뀌면 새 기준자산을 자동으로 생성해 운영자가 별도 리셋할 필요가 없습니다.

## 4) 개발자 관점 상세

### 4.1 데이터 모델/DB

- 신규 모델: `DailyEquity`
  - `date_utc` (PK)
  - `start_equity`, `last_equity`
  - `realized_pnl`, `unrealized_pnl`
  - `daily_pnl_abs`, `daily_pnl_pct`
  - `updated_at`
- SQLite 경량 마이그레이션에 `daily_equity` 생성 로직 추가
- KST 조회용 뷰 `daily_equity_kst` 추가
- 스키마 설명 동기화 대상에 `daily_equity` 추가

대상 파일:

- `trader/data/models.py`
- `trader/data/db.py`

### 4.2 서비스/로직

- 신규 서비스: `PnLService`
  - 일자별 baseline 생성/유지
  - 일중 손익 금액/비율 계산 및 저장
- `PortfolioService` 확장
  - `update_unrealized_pnl(mark_prices)`
  - `total_realized_pnl(...)`
  - `total_unrealized_pnl(...)`
- `ReconcileService`에서 리컨실 이후 미실현손익 갱신
- `TradingScheduler`에서:
  - 스냅샷 이후 `daily_pnl_pct` 계산
  - `RiskEngine.evaluate(..., daily_pnl_pct=실계산값)` 주입
  - `scheduler_daily_pnl` 로그 추가

대상 파일:

- `trader/trading/pnl.py`
- `trader/trading/portfolio.py`
- `trader/trading/reconcile.py`
- `trader/trading/scheduler.py`

## 5) 실행 흐름 (요약)

1. 캔들/마크가격 준비
2. 계좌/주문 리컨실
3. 포지션 미실현손익 갱신
4. 일별 baseline 기준으로 `daily_pnl_abs`, `daily_pnl_pct` 계산/저장
5. 리스크 평가에 `daily_pnl_pct` 주입
6. HALT 여부에 따라 주문 진행/중단

## 6) 테스트 및 검증 결과

신규 테스트:

- `tests/test_pnl.py`
  - 미실현손익 계산 정확성
  - 동일 날짜 baseline 고정
  - 날짜 변경 시 baseline 신규 생성
- `tests/test_scheduler_pnl.py`
  - 스케줄러가 계산된 `daily_pnl_pct`를 리스크 엔진에 전달하는지 검증
  - HALT 시 주문 생성 호출이 발생하지 않는지 검증

전체 테스트 결과:

- `python -m pytest -q` → `28 passed`

## 7) 운영 확인 가이드 (SQL 예시)

```sql
-- 일별 PnL 원본(UTC)
SELECT * FROM daily_equity ORDER BY date_utc DESC;

-- 일별 PnL KST 뷰
SELECT * FROM daily_equity_kst ORDER BY date_utc DESC;

-- 최신 포지션 손익 상태
SELECT market, qty, avg_price, realized_pnl, unrealized_pnl, updated_at
FROM positions
ORDER BY market;
```

## 8) 남은 후속 작업 (권장)

P2 문서의 나머지 권장 항목은 다음 순서로 진행하는 것을 권장합니다.

1. `daily_loss_basis` 옵션화 (`TOTAL` vs `REALIZED_ONLY`)
2. PnL 평가 시점 정책 문서화 (`docs/p2_design.md`)
3. 운영 로그 기반 파라미터 튜닝 후 P3 착수
