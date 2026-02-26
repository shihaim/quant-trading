# P4 제품 보고서 (Ops Dashboard 웹 콘솔)

- 작성일: 2026-02-26
- 대상: 기획/운영/개발 공용
- 범위: Ops Dashboard MVP + 웹 분리 배포 + 한/영 UI

## 1) 목적

운영자가 매일 1개 화면에서 다음을 즉시 판단하도록 지원:

- 봇이 실제로 동작 중인지 (`RUNNING/HALTED/DISABLED`)
- 당일 손익과 손실 컷 기준이 무엇인지 (`TOTAL/REALIZED_ONLY`)
- 즉시 조치가 필요한 주문 오류가 있는지 (`ERROR_NEEDS_REVIEW`)
- 체결 품질(슬리피지/체결시간) 이상 징후가 있는지
- 운영자가 안전하게 봇을 `Enable/Disable` 할 수 있는지

## 2) 이번 릴리즈 산출물

### 2.1 운영 API (백엔드)

- `GET /api/ops/summary`
- `GET /api/orders?state=...&limit=...`
- `GET /api/pnl/daily?days=...&tz=...`
- `GET /api/metrics/trade?limit=...`
- `POST /api/bot/enable`
- `POST /api/bot/disable`

특징:

- SQLite 기반 운영 요약 API 제공
- 프론트/백엔드 분리 배포 지원(CORS)
- 운영 관점 집계(`orders counts`, `needs_review_top`, `execution KPI`) 내장

### 2.2 웹 콘솔 (프론트)

- Next.js 기반 대시보드 페이지
- 폴링 주기 선택(10s/15s/30s)
- 버튼 조작: Refresh, Enable, Kill Switch
- 한/영 UI 토글 지원 (언어 선택 상태 localStorage 저장)

## 3) 사용자 가치

- 운영 리스크(손실 확대, 미체결 누적, 에러 누락) 조기 발견
- 봇 제어의 실수 가능성 감소(상태 가시화 + 확인 모달)
- 운영자/개발자/협업자 간 공통 화면 확보
- 한국어/영어 사용자 모두 동일 기능 접근 가능

## 4) 운영 정책 반영 포인트

- `daily_loss_basis`를 손익 카드에 명시
- `halt_threshold_pct` 대비 현재 손실률 게이지 노출
- `ERROR_NEEDS_REVIEW` 상위 건 즉시 노출
- 슬리피지 예산 초과 횟수(`breach_count_24h`) 노출
- `bot_config.is_enabled` 제어 API 제공

## 5) 배포/운영 방식

### 5.1 기본 실행

1. 백엔드 API 실행  
`python -m trader.app.ops_api --host 127.0.0.1 --port 8080`

2. 프론트 실행  
`cd apps/web && npm.cmd run dev`

3. 접속  
`http://127.0.0.1:3000`

### 5.2 분리 배포 설정

- 프론트: `NEXT_PUBLIC_API_BASE_URL`
- 백엔드 CORS: `OPS_API_ALLOW_ORIGIN`

## 6) 이번 단계 한계

- 인증/권한(로그인, RBAC) 미포함
- 설정 변경 감사로그(누가/언제/무엇) UI 미포함
- 차트 고도화(시계열 드릴다운, 비교 분석)는 후속 범위

## 7) 다음 우선순위 제안

1. Bot Control 화면(2단계 확인 + 변경 diff)
2. Orders 상세/필터 확장(상태 머신 중심)
3. PnL 비교 뷰(TOTAL vs REALIZED_ONLY 동시 시각화)
4. 운영 인증(최소 IP 제한 또는 간단 인증)

