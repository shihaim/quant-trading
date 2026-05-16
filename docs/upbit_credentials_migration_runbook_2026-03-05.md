# Upbit 자격증명 마이그레이션 런북 (2026-03-08 갱신)

## 목적

전역 `UPBIT_ACCESS_KEY`/`UPBIT_SECRET_KEY` 중심 운영에서,
사용자별 암호화 자격증명(`user_exchange_credentials`) 중심 운영으로 안전하게 전환한다.

## 현재 코드 기준 전제 (2026-03-08)

- `ops-api`는 사용자별 자격증명 저장/조회 및 bot 제어를 지원한다.
- `trader` 멀티유저 스케줄러는 사용자별 자격증명을 로드해 실행한다.
- CI/CD 배포 파이프라인은 아직 `UPBIT_*`를 `.env.runtime`에 주입하고 있다.
- 즉, 현재 권장 전략은 `병행 운영 -> 검증 -> 전역 키 제거`다.

## 핵심 원칙

- 자격증명 원문 입력은 운영자가 직접 수행한다.
- `OPS_API_CREDENTIALS_ENCRYPTION_KEY`/`KEYRING`은 로테이션 계획 없이 임의 변경하지 않는다.
- 사용자별 격리 불변식(교차 사용자 혼합 금지)을 깨지 않는다.

## Phase 0. 사전 점검/백업

1. 운영 DB 백업
- `pg_dump -Fc` 1회 생성

2. 사용자/자격증명 현황 파악
- 활성 사용자 대비 등록 완료 사용자 수를 확인한다.
- 자동 점검 스크립트 사용 가능:
  - `python scripts/audit_upbit_credential_coverage.py --fail-on-missing --fail-on-invalid`

예시 SQL:

```sql
SELECT COUNT(*) AS active_users
FROM users
WHERE is_active = true;

SELECT COUNT(DISTINCT user_id) AS users_with_upbit_credentials
FROM user_exchange_credentials
WHERE exchange = 'UPBIT';

SELECT u.id, u.email
FROM users u
LEFT JOIN user_exchange_credentials c
  ON c.user_id = u.id
 AND c.exchange = 'UPBIT'
WHERE u.is_active = true
  AND c.id IS NULL
ORDER BY u.id;
```

## Phase 1. 시크릿/배포 경로 정비

GitHub Secrets(또는 동등한 주입 경로)에 아래를 명시적으로 관리한다.

- `OPS_API_AUTH_SECRET`
- `OPS_API_CREDENTIALS_ENCRYPTION_KEY`
- `OPS_API_CREDENTIALS_ACTIVE_KEY_VERSION` (예: `v1`)
- `OPS_API_CREDENTIALS_KEYRING_JSON` (예: `{"v1":"<secret>"}`)

배포 워크플로우의 `.env.runtime` 생성 단계에 위 값을 주입한다.

관리자 권한은 `OPS_API_ADMIN_EMAILS` env allowlist가 아니라 DB의 `users.is_admin`으로 관리한다. 최초 운영자 또는 비상 운영자 권한 부여는 `docs/ops_runbook.md`의 Admin role 운영 섹션을 따른다.

`UPBIT_ACCESS_KEY`/`UPBIT_SECRET_KEY`는 이 단계에서 제거하지 말고 유지한다.

## Phase 2. 사용자 자격증명 백필

대상: 활성 사용자 중 `user_exchange_credentials` 미등록 사용자.

절차(사용자별 반복):

1. `POST /api/auth/login`으로 토큰 발급
2. `POST /api/me/credentials/upbit`로 키 저장
3. `GET /api/me/credentials/upbit`에서 `has_credentials=true`, `is_valid=true` 확인

PowerShell 예시:

```powershell
$base = "http://127.0.0.1:18080"
$login = Invoke-RestMethod -Method Post -Uri "$base/api/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"<user-email>","password":"<user-password>"}'
$token = $login.access_token

Invoke-RestMethod -Method Post -Uri "$base/api/me/credentials/upbit" `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body '{"access_key":"<upbit-access-key>","secret_key":"<upbit-secret-key>"}'

Invoke-RestMethod -Method Get -Uri "$base/api/me/credentials/upbit" `
  -Headers @{ Authorization = "Bearer $token" }
```

템플릿 스크립트(사용자 1명 단위) 예시:

```powershell
pwsh .\scripts\backfill_upbit_credentials_template.ps1 `
  -BaseUrl "http://127.0.0.1:18080" `
  -Email "user@example.com" `
  -Password "<user-password>" `
  -AccessKey "<upbit-access-key>" `
  -SecretKey "<upbit-secret-key>"
```

## Phase 3. 컷오버 검증

권장 순서:

1. `TRADE_MODE=TEST` 또는 `SHADOW`로 선검증
2. 사용자 2명 이상으로 `/api/me/bot/start` 후 격리 동작 확인
3. 회귀 게이트 통과 확인 (V3 Release Gates)
4. 이상 없으면 `TRADE_MODE=REAL` 전환

검증 체크:

- `/api/me/orders`, `/api/me/pnl/daily`, `/api/me/metrics/trade`, `/api/me/bot/status`
- 비관리자 `/api/ops` 접근 차단
- 사용자 A 실패/halt가 사용자 B 실행을 멈추지 않는지 확인

## Phase 4. 전역 `UPBIT_*` 제거

아래 조건이 모두 만족될 때만 제거:

1. 활성 사용자 전원 `is_valid=true`
2. 스케줄러 credential load 실패 로그 없음
3. 멀티유저 회귀 게이트 연속 통과

제거 순서:

1. GitHub Secrets에서 `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY` 제거(또는 비주입)
2. 워크플로우 `.env.runtime` 생성 단계에서도 `UPBIT_*` 라인 제거
3. 배포 후 모니터링(최소 1~2 릴리즈 사이클)

## 롤백

1. 배포 롤백
- 이전 이미지/이전 `.env.runtime` 조합으로 복귀

2. 키 운영 롤백
- `OPS_API_CREDENTIALS_ACTIVE_KEY_VERSION`을 이전 버전으로 되돌림
- `OPS_API_CREDENTIALS_KEYRING_JSON`에 이전 키 포함 유지

3. 데이터 롤백(필요 시)
- 사전 백업(`pg_dump`) 복구

## 보안 주의사항

- Secret 값은 문서/로그/채팅에 평문으로 남기지 않는다.
- 키 로테이션은 반드시 런북(`docs/credential_key_rotation_runbook_2026-03-08.md`) 절차대로 진행한다.
- `OPS_API_AUTH_SECRET` 변경 시 기존 토큰 무효화가 발생하므로 재로그인 공지 필요.
