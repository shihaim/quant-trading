# S3 Release Gate Report Automation (2026-03-16)

## Story
- `S3 (P0) 릴리즈 게이트 리포트 자동화`

## One-command Path
- Local:
  - `python scripts/run_release_gate.py --output-dir .`
- Local + Docker smoke (auth/admin/session lifecycle):
  - `python scripts/run_release_gate.py --output-dir . --include-localtest-smoke`
- Local + Docker smoke (required):
  - `python scripts/run_release_gate.py --output-dir . --include-localtest-smoke --localtest-smoke-required`
- Output artifacts:
  - `release_gate_report.json`
  - `release_gate_report.md`

## Report Schema
- `generated_at_utc`
- `git_ref`
- `overall_status` (`pass|fail`)
- `summary` (total/passed/failed counts)
- `checks[]`:
  - `name`, `description`, `required`
  - `command`, `status`, `exit_code`
  - `started_at_utc`, `finished_at_utc`, `duration_seconds`
  - `summary`, `stdout_tail`, `stderr_tail`
- `failure_summary[]`:
  - `name`, `required`, `summary`, `exit_code`

## Minimum Included Checks
- `pytest_result`
- `auth_smoke`
- `admin_boundary_smoke`
- `multi_user_isolation_smoke`
- `credential_coverage_validity`
- `migration_consistency`

## Optional Local Smoke Check
- Name: `localtest_auth_admin_smoke`
- Command target: `scripts/smoke-localtest-auth-admin.ps1`
- Enable flags:
  - `--include-localtest-smoke`
  - `--localtest-base-url http://127.0.0.1:28080` (default)
  - `--localtest-smoke-required` (optional, default is non-required)
  - `--powershell-binary powershell|pwsh`

## CI Integration
- `.github/workflows/ci-cd.yml` runs `scripts/run_release_gate.py`.
- The workflow uploads:
  - `release_gate_report.json`
  - `release_gate_report.md`

## Failure Visibility Rule
- Required check failure always makes `overall_status=fail`.
- Failure summary is always emitted with explicit check name and reason.
