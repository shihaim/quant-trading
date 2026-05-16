# S3 Release Gate 리포트 자동화 (2026-03-16)

## 스토리 식별자

- `S3 (P0) 릴리즈 게이트 리포트 자동화`

## 단일 실행 경로

- 로컬:
  - `python scripts/run_release_gate.py --output-dir .`
- 로컬 + Docker smoke (auth/admin/session lifecycle):
  - `python scripts/run_release_gate.py --output-dir . --include-localtest-smoke`
- 로컬 + Docker smoke를 필수로 처리:
  - `python scripts/run_release_gate.py --output-dir . --include-localtest-smoke --localtest-smoke-required`
- 출력 산출물:
  - `release_gate_report.json`
  - `release_gate_report.md`

## Report schema

- `generated_at_utc`
- `git_ref`
- `overall_status` (`pass|fail`)
- `summary` (전체/성공/실패 수)
- `checks[]`:
  - `name`, `description`, `required`
  - `command`, `status`, `exit_code`
  - `started_at_utc`, `finished_at_utc`, `duration_seconds`
  - `summary`, `stdout_tail`, `stderr_tail`
- `failure_summary[]`:
  - `name`, `required`, `summary`, `exit_code`

## 최소 포함 check

- `pytest_result`
- `auth_smoke`
- `admin_boundary_smoke`
- `multi_user_isolation_smoke`
- `credential_coverage_validity`
- `migration_consistency`

## 선택 Local Smoke Check

- 이름: `localtest_auth_admin_smoke`
- 대상 명령: `scripts/smoke-localtest-auth-admin.ps1`
- 활성화 flag:
  - `--include-localtest-smoke`
  - `--localtest-base-url http://127.0.0.1:28080` (기본값)
  - `--localtest-smoke-required` (선택, 기본은 필수 아님)
  - `--powershell-binary powershell|pwsh`

## CI 연동

- `.github/workflows/ci-cd.yml`에서 `scripts/run_release_gate.py`를 실행한다.
- workflow는 아래 산출물을 업로드한다:
  - `release_gate_report.json`
  - `release_gate_report.md`

## 실패 가시성 규칙

- 필수 check가 실패하면 항상 `overall_status=fail`이 된다.
- 실패 요약은 check 이름과 원인을 명시해서 항상 출력한다.
