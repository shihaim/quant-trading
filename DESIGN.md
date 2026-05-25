# Don't worry, Be happy Design System

이 문서는 `apps/web`의 다음 구현 작업에서 따라야 할 디자인 시스템 기준입니다. 목표는 사용자가 자동매매 상태를 불안 없이 빠르게 이해하고, 관리자는 운영 문제를 조밀하게 파악할 수 있는 화면을 만드는 것입니다.

## Product Identity

- 제품명은 항상 `Don't worry, Be happy`로 표기한다.
- 기본 언어는 한국어이며, 영어를 보조 언어로 지원한다.
- 브랜드 톤은 차분하고 신뢰감 있게 유지한다. 과장된 마케팅 문구보다 실제 상태, 손익, 주문, 제어 흐름을 명확히 보여준다.
- 운영 도메인은 `https://dont-worry-be-happy.today`이며, `www` 도메인도 같은 서비스로 취급한다.

## Design Principles

1. 밝은 캔버스 위에 흰색 표면을 얹어 조용한 금융 대시보드 느낌을 유지한다.
2. 숫자, 상태, 최근 업데이트 시간이 흔들림 없이 읽히도록 한다.
3. 사용자 화면과 관리자 화면의 역할을 분리한다.
4. 일반 사용자에게는 내부 ID, API path, source, scope, user_id 같은 구현 정보를 노출하지 않는다.
5. 관리자 화면은 더 조밀해도 되지만, 긴 값이 테이블 폭을 깨지 않게 한다.
6. 모든 오류 문구는 먼저 사람이 이해할 수 있는 요약을 보여준다.

## Tokens

토큰은 [apps/web/app/globals.css](apps/web/app/globals.css)와 [apps/web/tailwind.config.ts](apps/web/tailwind.config.ts)를 기준으로 한다.

| Role | Value | Usage |
| --- | --- | --- |
| Canvas | `#f9fafb` | 전체 배경 |
| Surface | `#ffffff` | 카드, 패널, 주요 표면 |
| Ink | `#111827` | 제목, 주요 숫자, 기본 텍스트 |
| Muted | `#64748b` | 보조 설명, 라벨 |
| Line | `#f1f5f9` | 카드/패널의 얇은 경계 |
| Line Strong | `#e2e8f0` | 입력창, 구분선 |
| Safe Green | `#00e676` | 연결 상태, 긍정 지표, 활성 상태 |
| Danger Coral | `#ff4d4d` | 위험, 손실, 오류 |
| Info Blue | `#2563eb` | 정보성 상태와 보조 강조 |

## Typography

- 기본 폰트는 Pretendard, fallback은 `Segoe UI`, `sans-serif`다.
- 제목과 핵심 수치는 `font-black` 또는 `font-extrabold`를 사용한다.
- 작은 라벨은 `text-xs`, `font-bold` 이상으로 처리해 흐릿하게 보이지 않게 한다.
- 숫자 영역은 `font-variant-numeric: tabular-nums;`를 유지한다.
- viewport 폭에 따라 폰트 크기를 직접 스케일하지 않는다.

## Layout

### App Shell

- 데스크톱에서는 좌측 사이드바와 상단 헤더를 함께 사용한다.
- 본문 컨테이너는 기본 `max-width: 1200px`로 중앙 정렬한다.
- 관리자 화면은 `max-width: 1480px`까지 허용한다.
- 본문 wrapper에는 `min-width: 0`과 `overflow-hidden`을 유지해 테이블이 페이지 전체 폭을 밀지 않게 한다.

### Page Structure

일반 사용자 페이지는 아래 순서를 따른다.

1. `main.page`
2. `header.page-header`
3. 필요 시 `section.page-toolbar`
4. 지표 카드 grid
5. `section.data-panel`

인증처럼 좁은 화면이 더 적합한 페이지는 `main.page.page-narrow`를 사용한다.

### Admin Console

관리자 화면은 브랜드 토큰은 공유하지만 정보 구조와 밀도를 사용자 화면과 분리한다.

- 진입점은 `main.admin-console`을 사용한다.
- 운영 영역은 `section.admin-panel`로 나누되, 카드 안에 또 다른 카드를 중첩하지 않는다.
- 관리자 첫 화면은 주요 지표, 위험 우선 테이블, 감사 로그 순서로 배치한다.
- 관리자 화면에는 운영 ID와 권한 경계 정보를 보여줄 수 있지만, 일반 사용자 화면으로 옮기지 않는다.

## Core Components

### `.panel`

주요 흰색 표면에 사용한다.

- radius: `24px`
- border: `1px solid var(--line)`
- shadow: `0 12px 40px rgba(0, 0, 0, 0.035)`
- background: `var(--surface)`

### `.page-header`

페이지 제목과 설명을 담는 첫 번째 패널이다.

- 모든 주요 사용자 페이지에서 같은 배경, padding, shadow를 유지한다.
- 상단/하단 여백이 다르게 보이지 않도록 별도 nested card를 넣지 않는다.
- 제목은 `font-display text-3xl font-black` 조합을 기본으로 한다.

### `.page-toolbar`

필터, 기간, 시간대, 새로고침 버튼 같은 페이지 조작 컨트롤을 담는다.

- 기본 구조는 `.toolbar-row`, `.toolbar-filters`, `.toolbar-actions`, `.toolbar-meta`를 사용한다.
- 필터는 왼쪽, 새로고침 같은 실행 버튼과 메타 정보는 오른쪽에 둔다.
- 모바일에서는 자연스럽게 줄바꿈되며, 컨트롤 사이 간격은 `gap-2` 또는 `gap-3`을 유지한다.
- 입력/select는 `.form-control`을 사용한다.
- 툴바 안에 별도의 카드형 wrapper를 중첩하지 않는다.

### `.metric-card`

핵심 숫자 카드에 사용한다.

- 숫자는 `font-display text-3xl font-black`을 기본으로 한다.
- 3개 지표는 `grid gap-4 md:grid-cols-2 xl:grid-cols-3`을 사용한다.
- 4개 지표는 `grid gap-4 md:grid-cols-2 xl:grid-cols-4`를 사용한다.

### `.data-panel`

테이블과 상세 데이터 블록에 사용한다.

- `max-width: 100%`, `min-width: 0`을 유지한다.
- 테이블 wrapper에는 `overflow-auto`를 붙인다.
- 새 테이블에는 `width: max-content; min-width: 100%`만 단독으로 의존하지 않는다.
- 현재 테이블 기준은 `colgroup`과 페이지별 table class를 함께 사용하는 것이다.

### `.admin-panel`

관리자 운영 화면의 기본 표면이다.

- radius: `18px`
- border: `1px solid var(--line)`
- shadow: `0 12px 40px rgba(0, 0, 0, 0.02)`
- 사용자용 `.panel`보다 더 작고 조밀하게 사용할 수 있다.

### Buttons

- 공통 버튼은 `.btn`을 사용한다.
- 주요 액션은 `.btn-primary`, 보조 액션은 `.btn-secondary`를 사용한다.
- 기본 높이는 `44px`이며, 작은 툴바 버튼만 `min-h-9`로 낮출 수 있다.
- active 상태는 짙은 `ink` 배경 또는 연한 표면과 shadow 조합을 사용한다.

### Forms

- 입력 요소는 `.form-control`을 사용한다.
- focus 상태는 green ring `rgba(0, 230, 118, 0.16)`을 사용한다.
- 인증 페이지는 `page-narrow` 폭을 유지하고, 불필요한 장식 카드를 추가하지 않는다.

## Tables And Data

테이블은 브라우저 자동 레이아웃에 맡기지 않고 명시적으로 폭 의도를 선언한다.

- 사용자 테이블은 `.data-table`과 페이지별 class를 함께 사용한다.
  - 주문: `.data-table-orders`
  - 손익: `.data-table-pnl`
  - 체결 품질: `.data-table-execution`
- 관리자 테이블은 `.admin-table`과 페이지별 class를 함께 사용한다.
  - 런타임/사용자 상태: `.admin-table-runtime`
  - 감사 로그: `.admin-table-audit`
- 각 테이블은 `colgroup`으로 컬럼 폭을 선언한다.
- 모든 테이블 헤더는 왼쪽 정렬한다. 숫자 컬럼도 헤더는 왼쪽 정렬한다.
- 금액, 퍼센트, 개수, latency body cell은 `.table-cell-number`와 우측 정렬을 사용한다.
- 긴 note, error, email, metadata label, action name은 `.table-truncate`와 `title` 속성을 함께 사용한다.
- 상태 badge 컬럼은 고정 폭을 유지해 행마다 badge 위치가 흔들리지 않게 한다.
- 설명 컬럼은 남은 폭을 사용하되, 다른 컬럼을 밀어내지 않는다.
- 관리자 테이블의 가로 스크롤은 `.admin-table-wrap` 안에서만 발생해야 한다.

## Error Message UX

- 사용자 페이지에는 `API 401: invalid credentials` 같은 원본 API 오류를 그대로 보여주지 않는다.
- 로그인 실패는 “이메일 또는 비밀번호를 다시 확인해주세요.”처럼 사용자가 다음 행동을 알 수 있는 문구로 표현한다.
- 네트워크/서버 오류는 “잠시 후 다시 시도해주세요.”와 같이 과도한 기술 상세를 숨긴다.
- 관리자 화면은 원본 오류나 운영 상세를 보여줄 수 있지만, 먼저 사람이 읽을 수 있는 요약을 제공한다.
- locale 문구는 [apps/web/lib/locale.tsx](apps/web/lib/locale.tsx)의 `APP_TEXT`에 추가한다.

## Localization

- 기본 locale은 `ko`다.
- 사용자가 언어를 변경하면 `localStorage`의 `dwbh_locale`에 저장한다.
- 새 화면의 하드코딩 문구는 [apps/web/lib/locale.tsx](apps/web/lib/locale.tsx)의 `APP_TEXT` key로 추가한다.
- 언어 토글은 `한국어 / EN` 표기를 사용한다.
- 날짜와 숫자는 `intlLocale`을 통해 `ko-KR` 또는 `en-US` 형식을 사용한다.

## Navigation Labels

| Route | Korean | English |
| --- | --- | --- |
| `/` | 시작 | Entry |
| `/dashboard` | 대시보드 | Dashboard |
| `/orders` | 주문 | Orders |
| `/pnl` | 손익 | PnL |
| `/execution` | 체결 품질 | Execution Metrics |
| `/control` | 자동매매 | Bot Control |
| `/admin/ops` | 관리자 운영 | Admin Ops |

## Responsive Rules

- 카드가 좁아지면 숫자보다 제목/설명을 먼저 줄인다.
- 데이터가 많은 화면은 본문 최대 폭을 무리하게 넓히기보다 테이블 영역의 가로 스크롤로 처리한다.
- 모바일에서는 카드가 1열로 자연스럽게 내려오도록 한다.
- 버튼과 입력 텍스트는 모든 viewport에서 부모 요소를 넘치지 않아야 한다.

## Do

- 기존 `.page`, `.page-header`, `.page-toolbar`, `.metric-card`, `.data-panel`, `.btn`, `.form-control` 클래스를 먼저 사용한다.
- 숫자와 손익은 상태값이 한눈에 비교 가능하게 만든다.
- 사용자별 데이터 화면에서는 `/api/me/*` 경계를 유지한다.
- 새 테이블을 만들 때는 colgroup, 페이지별 table class, truncate 정책을 함께 설계한다.
- 사용자가 보는 문구는 “최근 업데이트”, “개 항목”, “서비스 정상”처럼 자연스러운 제품 문구로 표현한다.

## Don't

- 카드 안에 또 다른 큰 카드를 중첩하지 않는다.
- 페이지 섹션을 반복적인 floating card처럼 만들지 않는다.
- 일반 사용자 화면에 `P1-FE*`, `GET /api/...`, `Rows`, `Loaded`, `CORE LIVE CONNECTED`, `Design System v*` 같은 개발/운영 라벨을 노출하지 않는다.
- 사용자 화면의 주문 테이블에 `client_order_id`, `upbit_identifier`, `upbit_uuid` 같은 내부 추적 컬럼을 표시하지 않는다.
- 자동매매 화면에 guardrail 상세 설정값 전체를 기본으로 펼쳐 놓지 않는다. 상세 설정은 관리자/고급 화면에서 다룬다.
- raw API error를 사용자에게 그대로 보여주지 않는다.

## Implementation Checklist

새 페이지나 주요 UI 변경 시 아래를 확인한다.

1. 제품명이 `Don't worry, Be happy`로 일관되는가?
2. 한국어가 기본이고 영어 전환 시 모든 문구가 바뀌는가?
3. 페이지가 `page -> page-header -> toolbar/cards/data-panel` 구조를 따르는가?
4. 카드/패널의 배경, padding, shadow가 기존 화면과 맞는가?
5. 테이블이 본문을 밀지 않고 패널 안에서 스크롤되는가?
6. 모든 테이블 헤더가 왼쪽 정렬인가?
7. 숫자 body cell만 우측 정렬되고, 헤더는 왼쪽 정렬인가?
8. 일반 사용자 화면에 내부 ID, API 경로, source/scope/user_id가 보이지 않는가?
9. 사용자 오류 문구가 친절하고 다음 행동을 안내하는가?
10. `npm run lint`, `tsc --noEmit`, 가능하면 `npm run build`가 통과하는가?
