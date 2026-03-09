# V3 멀티유저 전환 제품 인수인계 2026-03-09 (기획 + 운영)

- 작성일: 2026-03-09
- 대상: 기획, 운영, QA
- 범위: V3.1 ~ V3.8 배치 완료 기준 운영 문서

## 1) 한 줄 요약

V3 전환으로 주문/포지션/PnL/런타임이 사용자 단위로 분리되었고, 레거시 owner bridge가 제거되어 멀티유저 운영 기준이 정식화되었습니다.

## 2) 현재 상태 스냅샷

- 배치 페이지 기준 상태: `overall: completed`, `V3.1~V3.8: completed`
- 기준 페이지:
  - Task index: `https://www.notion.so/31b899b6d7dc80d4af4be0041af7937d`
  - V3 batch: `https://www.notion.so/31c899b6d7dc81f5a92bfa159119e6e5`
  - Story V3.8: `https://www.notion.so/31d899b6d7dc81098121d1809369d3e8`

## 3) 제품/운영 관점의 확정 변화

1. 데이터 격리
- 주문, 포지션, 일별 손익, 봇 런타임이 사용자 단위로 분리됨
- 사용자 A 장애/오류가 사용자 B 실행을 멈추지 않도록 격리됨

2. 접근 경계
- 일반 사용자: `/api/me/*`만 접근
- 관리자 전용: `/ops`, `/api/admin/*`

3. 레거시 경로 축소
- 글로벌 owner bridge 읽기 경로 제거
- 글로벌 `bot_config(id=1)` 단일 의존 제거

## 4) 릴리즈 게이트 (운영 승인 체크리스트)

- [ ] 사용자 간 order/position/pnl/runtime 데이터 혼합이 없다
- [ ] 사용자 A credential 오류가 사용자 B tick 실행에 영향 없다
- [ ] non-admin으로 `/ops`, `/api/admin/*` 접근 시 차단된다
- [ ] 마이그레이션 전/후 totals, counts가 일치한다
- [ ] 운영 배포 체크리스트(아래 5절)를 완료했다

## 5) 운영 실행 체크리스트

1. 배포 전
- `DATABASE_URL` 백업 완료
- 필수 시크릿 확인:
  - `OPS_API_AUTH_SECRET`
  - `OPS_API_CREDENTIALS_ENCRYPTION_KEY`
  - `OPS_API_CREDENTIALS_KEYRING_JSON`

2. 배포 직후
- `/api/me` 인증 확인
- `/api/me/credentials/upbit`에서 `has_credentials`, `is_valid` 확인
- 사용자 2명 이상으로 주문/조회/봇 상태를 교차 검증
- non-admin 계정으로 `/ops`, `/api/admin/*` 접근 차단 검증

3. 모니터링
- 사용자별 오류율, 주문 재시도, 봇 상태 전환 실패율 추적
- credential 관련 에러(`credentials_required`, `credentials_invalid`) 급증 감시

## 6) QA 핵심 시나리오

1. 사용자 A/B 동시 활성화
- A 주문 생성/조회 후 B 계정에서 A 데이터가 보이지 않아야 함

2. 장애 격리
- A 계정에 credential 오류 유도 후 B 스케줄러 tick/실행 지속 확인

3. 권한 경계
- non-admin 계정의 `/ops`, `/api/admin/*` 차단 확인

4. 봇 제어
- `/api/me/bot/status|start|stop`의 사용자 스코프 동작 확인

## 7) 현재 리스크와 대응

1. 문서/현장 절차 불일치
- 대응: 본 문서 기준으로 운영 체크리스트 고정, Notion 상태와 동기화

2. 운영자 계정 권한 오남용
- 대응: admin 전용 경로 접근 로그 주기 검토 및 감사 이벤트 점검

3. 키 회전 절차 누락
- 대응: 키링 JSON 기반 회전 런북(`credential_key_rotation_runbook_2026-03-08.md`) 주기 점검

## 8) 다음 기획 백로그 제안

1. 사용자별 API budget 대시보드(알람 임계치, 사용량 트렌드) 시각화
2. 리스크 가드 UX(손실 제한 도달/해제 이벤트) 운영 화면 노출 강화
3. 운영 승인 흐름(배포 전 게이트 체크 서명) 템플릿화

## 9) 관련 문서

- `docs/context_anchor_v3_transition.md`
- `docs/postgres_v3_schema_sync_runbook_2026-03-08.md`
- `docs/credential_key_rotation_runbook_2026-03-08.md`
- `docs/ops_runbook.md`
