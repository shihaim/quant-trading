# Upbit Credential Migration Runbook (2026-03-05)

## 목적

기존 운영 구조(`UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY` 전역 주입)에서,
V2 사용자별 암호화 자격증명 구조를 안전하게 도입하기 위한 운영 절차를 정의한다.

## 현재 코드 기준 전제

- `ops-api`는 사용자별 자격증명 저장/조회 경로를 지원한다.
- `trader` 실거래 루프(`REAL/TEST/SHADOW`)는 아직 전역 `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY`를 필수로 사용한다.
- 따라서 이번 전환은 "완전 제거"가 아니라 "병행 운영"이다.

## 사전 준비

1. GitHub Secrets 신규 등록
- `OPS_API_AUTH_SECRET`
- `OPS_API_CREDENTIALS_ENCRYPTION_KEY`

2. 기존 Secrets 유지 (필수)
- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`

3. 권장 백업
- 운영 DB `pg_dump -Fc` 백업 1회 생성

## 배포 절차 (권장 순서)

1. 신규 Secret 반영된 이미지/배포 적용
- `ops-api` 먼저 재기동
- 상태 확인 후 `trader` 재기동

2. API 기본 상태 확인
- `GET /api/ops/summary`
- `POST /api/auth/login`
- `GET /api/me`

3. 운영 owner 계정 자격증명 백필
- owner 계정으로 로그인 후 토큰 획득
- `POST /api/me/credentials/upbit`에 기존 운영 키 저장

PowerShell 예시:

```powershell
$login = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18080/api/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"<owner-email>","password":"<owner-password>"}'

$token = $login.access_token

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18080/api/me/credentials/upbit" `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body '{"access_key":"<upbit-access-key>","secret_key":"<upbit-secret-key>"}'
```

4. 사용자 경로 검증
- `GET /api/me/credentials/upbit` -> `has_credentials=true`, `is_valid=true`
- `GET /api/me/orders`
- `GET /api/me/pnl/daily?days=30&tz=UTC`
- `GET /api/me/metrics/trade?limit=50`

## 운영 판정 기준

- 전역 `UPBIT_*` 유지 상태에서 기존 거래 루프 정상
- 사용자 경로(`/api/me/*`) 인증/조회 정상
- `credentials_required`, `no_data_scope` 등 예외가 의도대로 동작

## 롤백 가이드

1. 신규 Secret 반영 전 버전으로 이미지 롤백
2. 기존 `UPBIT_*` 중심 구성으로 즉시 복귀
3. 필요 시 배포 전 생성한 `pg_dump`로 DB 복구

## 보안/운영 주의사항

- `OPS_API_CREDENTIALS_ENCRYPTION_KEY`를 임의 교체하면 기존 암호문 복호화가 실패할 수 있다.
- `OPS_API_AUTH_SECRET` 교체 시 기존 access token은 무효화된다(재로그인 필요).
- Secret 값은 로그/문서/채팅에 평문으로 남기지 않는다.

## 다음 단계 (완전 전환 조건)

아래가 구현되기 전까지는 `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY`를 제거하면 안 된다.

1. `trader`가 사용자별 암호화 자격증명을 직접 읽어 주문/조회 수행
2. 전역 `UPBIT_*` 의존 제거
3. 사용자 범위 쓰기 작업(거래/제어) 전면 전환 및 운영 검증 완료
