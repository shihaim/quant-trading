# Don't worry, Be happy Design System

이 문서는 `apps/web`의 다음 구현 작업에서 따라야 할 디자인 시스템 기준이다. 현재 앱은 밝고 단단한 핀테크 콘솔을 목표로 하며, Wise에서 영감을 받은 선명한 라이트 UI를 사용한다.

## Product Identity

- 앱 이름은 항상 `Don't worry, Be happy`로 표기한다.
- 기본 언어는 한국어다. 영어는 보조 언어로 지원한다.
- 브랜드 톤은 불안감을 낮추는 명확함, 빠른 상태 파악, 숫자 신뢰감에 맞춘다.
- 마케팅형 랜딩보다 실제 운영 화면을 우선한다. 첫 화면도 제품의 실제 상태와 이동 경로를 보여줘야 한다.

## Design Principles

1. 밝은 캔버스 위에 흰색 표면을 올린다.
2. 두꺼운 테두리보다 아주 옅은 라인과 부드러운 그림자로 계층을 만든다.
3. 금융 숫자는 크게, 굵게, 흔들림 없이 보여준다.
4. 화면 전체의 카드 반경과 패딩 리듬을 맞춘다.
5. 데이터 테이블은 가로 스크롤을 허용하되 페이지 자체가 깨지지 않게 한다.
6. 사용자 화면과 관리자/운영 화면의 경계를 시각적으로 분명히 유지한다.

## Tokens

현재 핵심 토큰은 [apps/web/app/globals.css](apps/web/app/globals.css)와 [apps/web/tailwind.config.ts](apps/web/tailwind.config.ts)에 정의되어 있다.

| Role | Value | Usage |
| --- | --- | --- |
| Canvas | `#f9fafb` | 앱 전체 배경 |
| Surface | `#ffffff` | 카드, 패널, 폼 표면 |
| Ink | `#111827` | 제목, 주요 숫자, 기본 텍스트 |
| Muted | `#64748b` | 보조 설명, 라벨 |
| Line | `#f1f5f9` | 카드/패널의 아주 옅은 경계 |
| Line Strong | `#e2e8f0` | 입력창, 분리선, 보조 테두리 |
| Safe Green | `#00e676` | 연결 상태, 긍정 지표, 활성 상태 |
| Danger Coral | `#ff4d4d` | 위험, 손실, 매도/오류 계열 강조 |
| Info Blue | `#2563eb` | 정보성 상태, 보조 강조 |

## Typography

- 기본 폰트는 Pretendard, fallback은 `Segoe UI`, `sans-serif`다.
- 제목과 핵심 수치는 `font-black` 또는 `font-extrabold`를 우선한다.
- 작은 라벨은 `text-xs`, `font-bold` 이상을 사용해 흐릿하게 보이지 않게 한다.
- 숫자는 전역 `font-variant-numeric: tabular-nums;`를 유지한다.
- 앱 내부에서는 음수 letter spacing에 의존하지 않는다. 필요하면 Tailwind 기본 `tracking-tight` 정도만 사용한다.

## Layout

### App Shell

- 데스크톱에서는 좌측 사이드바와 상단 헤더를 함께 사용한다.
- 본문 컨테이너는 `max-width: 1200px`를 기준으로 중앙 정렬한다.
- 본문 wrapper는 `min-width: 0`과 `overflow-hidden`을 유지해 테이블/네비가 화면 바깥으로 페이지를 밀지 않게 한다.
- 상단 네비는 항목이 많아질 수 있으므로 내부 가로 스크롤을 허용한다.

### Page Structure

일반 페이지는 다음 순서를 따른다.

1. `main.page`
2. `header.page-header`
3. 필요 시 `section.page-toolbar`
4. 지표 카드 그리드
5. `section.data-panel`

폼 중심 페이지는 `main.page.page-narrow`를 사용한다.

### Admin Console

관리자 화면은 사용자용 대시보드와 같은 브랜드 토큰을 공유하되, 정보 구조와 밀도를 분리한다.

- 관리자 진입점은 `main.admin-console`을 사용한다.
- 최대 폭은 사용자 화면보다 넓은 `1480px` 기준으로 잡고, 데이터 테이블의 가로 스크롤은 패널 내부에서만 발생시킨다.
- 각 운영 영역은 `section.admin-panel`로 나누며, 반복 카드처럼 과하게 장식하지 않는다.
- 관리자 첫 화면은 “요약 지표 -> 위험 우선 테이블 -> 감사 로그” 순서로 배치한다.
- 위험, 중지, 인증 문제, 최근 오류가 있는 사용자를 우선 정렬한다.
- 관리자 화면에서는 `user_id`, `target_id`, API 권한 경계 같은 운영 정보를 노출할 수 있지만, 일반 사용자 화면으로 섞이지 않아야 한다.

## Core Components

### `.panel`

앱 셸 내부의 큰 표면에 사용한다.

- radius: `24px`
- border: `1px solid var(--line)`
- shadow: `0 12px 40px rgba(0, 0, 0, 0.035)`
- background: `var(--surface)`

### `.page-header`

페이지의 제목과 설명을 담는 첫 번째 패널이다.

- 모든 주요 페이지에서 같은 반경, 패딩, 그림자를 유지한다.
- 상단/하단 두께가 다르게 보이지 않도록 별도 nested card를 넣지 않는다.
- 제목은 `font-display text-3xl font-black` 조합을 기본으로 한다.

### `.page-toolbar`

필터, 기간, 시간대, 새로고침 버튼처럼 페이지 조작 컨트롤을 담는다.

- 컨트롤은 `flex flex-wrap`으로 배치한다.
- 입력/셀렉트는 `.form-control`을 사용한다.
- 툴바 안에 별도의 카드형 wrapper를 중첩하지 않는다.

### `.metric-card`

핵심 숫자 카드에 사용한다.

- 숫자는 `font-display text-3xl font-black`을 기본으로 한다.
- 중간 폭에서는 과도한 열 수를 피한다.
- 3개 지표: `grid gap-4 md:grid-cols-2 xl:grid-cols-3`
- 4개 지표: `grid gap-4 md:grid-cols-2 xl:grid-cols-4`

### `.data-panel`

테이블과 상세 데이터 블록에 사용한다.

- `max-width: 100%`, `min-width: 0`을 유지한다.
- 큰 테이블은 `overflow-auto`를 붙인다.
- 내부 table은 `width: max-content; min-width: 100%;` 규칙을 따른다.
- `th`, `td`는 기본적으로 `white-space: nowrap`을 사용한다.

### `.admin-panel`

관리자 운영 화면의 기본 표면이다.

- radius: `18px`
- border: `1px solid var(--line)`
- shadow: `0 12px 40px rgba(0, 0, 0, 0.02)`
- 사용자용 `.panel`보다 덜 둥글고 더 조밀하게 사용한다.

### `.admin-table`

관리자용 데이터 테이블이다.

- wrapper는 `.admin-table-wrap`을 사용한다.
- table은 `width: max-content; min-width: 100%;`를 유지한다.
- 행은 위험도 우선 정렬을 허용하며, 위험 행은 매우 옅은 red/amber 배경만 사용한다.
- 컬럼명은 운영자가 스캔하기 쉬운 짧은 한국어를 기본으로 한다.

### `.status-badge`

관리자 화면의 상태 배지는 다음 tone만 사용한다.

- green: 정상, 실행 중, 성공
- amber: 중지, 주의, 미등록
- red: 오류, 인증 문제, 요청 제한, 실패
- blue: 정보성 범위, 자동 갱신
- gray: 비활성, 전체, 알 수 없음

### Buttons

- 공통 버튼은 `.btn`을 사용한다.
- 주요 액션은 `.btn-primary`, 보조 액션은 `.btn-secondary`를 사용한다.
- 버튼 높이는 기본 `44px`이며, 작은 툴바 버튼만 `min-h-9`로 낮출 수 있다.
- active 상태는 짙은 `ink` 배경 또는 흰색 표면+그림자 조합을 사용한다.

### Forms

- 입력 요소는 `.form-control`을 사용한다.
- focus 상태는 green ring을 사용한다: `rgba(0, 230, 118, 0.16)`.
- 인증 페이지는 `page-narrow` 폭을 유지하고, 불필요한 장식 카드는 추가하지 않는다.

## Tables And Data

- Use explicit table classes instead of relying on browser auto layout.
  - User-facing tables use `.data-table` plus a page-specific class such as `.data-table-orders`, `.data-table-pnl`, or `.data-table-execution`.
  - Admin tables use `.admin-table` plus a page-specific class such as `.admin-table-runtime` or `.admin-table-audit`.
- Declare column intent with `colgroup` in each table.
  - Date/time columns get fixed widths.
  - Market, side, intent, status, and action columns get predictable fixed widths.
  - Money, percentage, count, and latency body cells use `.table-cell-number` and right alignment.
  - Column headers stay left-aligned on every table, including numeric columns.
  - Long notes, errors, emails, metadata labels, and action names use `.table-truncate` with a `title` attribute for the full value.
- User tables should optimize for calm scanning.
  - Keep row height comfortable.
  - Keep status badges in a stable fixed-width column.
  - Give explanatory columns, such as order notes, the remaining width without letting them move other columns.
- Admin tables should optimize for dense operations.
  - Keep horizontal scrolling inside `.admin-table-wrap`.
  - Do not let long emails, errors, or metadata expand the table unexpectedly.
  - It is acceptable for admin tables to expose operational IDs, but those fields must stay out of user-facing pages.

- 테이블은 카드 안에서만 보여준다.
- 페이지 전체가 가로로 밀리는 대신 테이블 영역 자체가 스크롤되어야 한다.
- 행 hover는 `#f8fafc`로 아주 조용하게 처리한다.
- 테이블 헤더는 uppercase, `text-xs`, muted 색상, 굵은 weight를 사용한다.
- 금액은 locale formatter를 사용하고 한국어 기본에서는 `원` 표기를 우선한다.
- 일반 사용자 화면에서는 내부 식별자와 API 구현 정보를 노출하지 않는다.
- 주문 테이블에는 `client_order_id`, `upbit_identifier`, `upbit_uuid` 같은 내부 추적 컬럼을 표시하지 않는다.
- `scope`, `user_id`, `source`, API path, 화면 구현 ID는 관리자/개발자 맥락에서만 사용한다.

## Localization

- 기본 locale은 `ko`다.
- 사용자가 언어를 변경하면 `localStorage`의 `dwbh_locale`에 저장한다.
- 새 화면을 만들 때는 하드코딩 텍스트 대신 [apps/web/lib/locale.tsx](apps/web/lib/locale.tsx)의 `APP_TEXT`에 key를 추가한다.
- 언어 토글은 `한국어 / EN` 표기를 사용한다.
- 날짜와 숫자는 `intlLocale`을 통해 `ko-KR` 또는 `en-US` 포맷을 사용한다.

## Navigation Labels

현재 사용자 화면의 기본 라벨은 다음과 같다.

| Route | Korean | English |
| --- | --- | --- |
| `/` | 시작 | Entry |
| `/dashboard` | 대시보드 | Dashboard |
| `/orders` | 주문 | Orders |
| `/pnl` | 손익 | PnL |
| `/execution` | 체결 지표 | Execution Metrics |
| `/control` | 봇 제어 | Bot Control |
| `/admin/ops` | 관리자 운영 | Admin Ops |

## Responsive Rules

- 카드가 좁아져 숫자나 제목이 잘리면 열 수를 줄인다.
- 데스크톱 사이드바가 있는 상태를 기준으로 `md:grid-cols-3` 또는 `md:grid-cols-4`를 무리하게 사용하지 않는다.
- 데이터가 많은 화면은 본문 최대 폭을 넓히기보다 테이블 영역의 가로 스크롤로 처리한다.
- 모바일에서는 카드가 1열로 자연스럽게 내려와야 한다.

## Do

- 기존 `.page`, `.page-header`, `.page-toolbar`, `.metric-card`, `.data-panel`, `.btn`, `.form-control` 클래스를 먼저 사용한다.
- 새 컴포넌트는 현재 토큰과 spacing 리듬을 재사용한다.
- 숫자, 수익률, 상태값은 한눈에 스캔 가능하게 만든다.
- 사용자별 데이터 화면에서는 `/api/me/*` 경계를 유지한다.
- 사용자에게 필요한 문구는 `최근 업데이트`, `개 항목`, `서비스 정상`처럼 자연어로 표현한다.

## Don't

- 카드 안에 또 다른 큰 카드를 중첩하지 않는다.
- 페이지 섹션을 불필요하게 floating card처럼 반복하지 않는다.
- 어두운 대시보드 테마, 과한 그라디언트, 단색 위주의 보라/베이지/슬레이트 팔레트를 도입하지 않는다.
- 화면 설명 문구를 길게 늘어놓아 실제 데이터 밀도를 낮추지 않는다.
- 임시 한국어 문구를 깨진 인코딩 상태로 남기지 않는다.
- `P1-FE*`, `GET /api/...`, `Rows`, `Loaded`, `CORE LIVE CONNECTED`, `Design System v*` 같은 개발/운영 라벨을 일반 사용자 화면에 노출하지 않는다.
- 자동매매 화면에 guardrail 원시 설정값 전체를 그대로 펼쳐 놓지 않는다. 기본은 요약 상태, 상세 설정은 관리자/고급 화면에서 다룬다.

## Implementation Checklist

새 페이지나 주요 UI 변경 시 아래를 확인한다.

1. 앱 이름이 `Don't worry, Be happy`로 일관되는가?
2. 한국어가 기본이고 영어 전환 시 문구가 모두 바뀌는가?
3. 페이지가 `page -> page-header -> toolbar/cards/data-panel` 구조를 따르는가?
4. 카드/패널의 반경, 패딩, 그림자가 기존 화면과 맞는가?
5. 테이블이 본문을 밀지 않고 패널 내부에서 스크롤되는가?
6. 일반 사용자 화면에 내부 ID, API 경로, source/scope/user_id가 보이지 않는가?
7. `npm run lint`, `tsc --noEmit`, 가능하면 `npm run build`가 통과하는가?
