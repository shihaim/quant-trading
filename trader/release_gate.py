from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ReleaseGateCheck:
    name: str
    command: list[str]
    description: str
    required: bool = True


@dataclass(frozen=True)
class ReleaseGateCheckResult:
    name: str
    description: str
    required: bool
    command: list[str]
    status: str
    exit_code: int
    started_at_utc: str
    finished_at_utc: str
    duration_seconds: float
    summary: str
    stdout_tail: str
    stderr_tail: str


def default_checks() -> list[ReleaseGateCheck]:
    return [
        ReleaseGateCheck(
            name="pytest_result",
            description="Repository pytest result",
            command=["python", "-m", "pytest", "-q"],
        ),
        ReleaseGateCheck(
            name="auth_smoke",
            description="Auth signup/login/me smoke",
            command=[
                "python",
                "-m",
                "pytest",
                "-q",
                "tests/test_ops_http_auth.py::test_auth_endpoints_support_signup_login_and_me",
            ],
        ),
        ReleaseGateCheck(
            name="admin_boundary_smoke",
            description="Admin boundary deny/allow smoke",
            command=[
                "python",
                "-m",
                "pytest",
                "-q",
                "tests/test_ops_http_auth.py::test_admin_user_scoped_routes_enforce_admin_and_target_scope",
                "tests/test_ops_http_auth.py::test_admin_audit_logs_endpoint_supports_filters_pagination_and_admin_boundary",
            ],
        ),
        ReleaseGateCheck(
            name="multi_user_isolation_smoke",
            description="Multi-user runtime failure isolation smoke",
            command=[
                "python",
                "-m",
                "pytest",
                "-q",
                "tests/test_multi_user_scheduler.py::test_run_user_tick_halt_isolated_to_target_user",
                "tests/test_multi_user_scheduler.py::test_daily_loss_limit_halt_isolated_to_impacted_user",
            ],
        ),
        ReleaseGateCheck(
            name="credential_coverage_validity",
            description="Credential coverage and validity audit",
            command=[
                "python",
                "scripts/audit_upbit_credential_coverage.py",
                "--json",
                "--bootstrap-empty-schema",
                "--database-url",
                "sqlite:///./release_gate_credentials.db",
                "--encryption-key",
                "release-gate-dummy-key",
                "--fail-on-missing",
                "--fail-on-invalid",
            ],
        ),
        ReleaseGateCheck(
            name="migration_consistency",
            description="Migration consistency smoke",
            command=[
                "python",
                "-m",
                "pytest",
                "-q",
                "tests/test_v3_user_scope_migration.py::test_migration_dry_run_projects_rows_without_writing_target",
                "tests/test_v3_user_scope_migration.py::test_snapshot_copy_preserves_backfill_totals_and_user_counts",
            ],
        ),
    ]


def run_release_gate(
    *,
    checks: Sequence[ReleaseGateCheck],
    cwd: str | Path,
    max_output_chars: int = 4000,
) -> dict:
    results: list[ReleaseGateCheckResult] = []
    for check in checks:
        results.append(_run_check(check=check, cwd=cwd, max_output_chars=max_output_chars))

    failed = [result for result in results if result.status != "pass"]
    required_failed = [result for result in failed if result.required]
    overall_status = "pass" if not required_failed else "fail"
    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report = {
        "generated_at_utc": now_utc,
        "git_ref": _resolve_git_ref(cwd=cwd),
        "overall_status": overall_status,
        "summary": {
            "total_checks": len(results),
            "required_checks": len([result for result in results if result.required]),
            "passed_checks": len([result for result in results if result.status == "pass"]),
            "failed_checks": len(failed),
            "failed_required_checks": len(required_failed),
        },
        "checks": [asdict(result) for result in results],
        "failure_summary": [
            {
                "name": result.name,
                "required": result.required,
                "summary": result.summary,
                "exit_code": result.exit_code,
            }
            for result in failed
        ],
    }
    return report


def write_report_files(*, report: dict, output_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "release_gate_report.json"
    markdown_path = out_dir / "release_gate_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def render_markdown_report(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Release Gate Report")
    lines.append("")
    lines.append(f"- generated_at_utc: `{report.get('generated_at_utc')}`")
    lines.append(f"- git_ref: `{report.get('git_ref')}`")
    lines.append(f"- overall_status: `{report.get('overall_status')}`")
    lines.append("")
    lines.append("## Summary")
    summary = report.get("summary", {})
    lines.append(f"- total_checks: `{summary.get('total_checks')}`")
    lines.append(f"- passed_checks: `{summary.get('passed_checks')}`")
    lines.append(f"- failed_checks: `{summary.get('failed_checks')}`")
    lines.append(f"- failed_required_checks: `{summary.get('failed_required_checks')}`")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| name | status | required | duration_sec | exit_code | summary |")
    lines.append("| --- | --- | --- | ---: | ---: | --- |")
    for check in report.get("checks", []):
        lines.append(
            "| {name} | {status} | {required} | {duration} | {exit_code} | {summary} |".format(
                name=str(check.get("name", "")),
                status=str(check.get("status", "")),
                required=str(check.get("required", "")),
                duration=f"{float(check.get('duration_seconds', 0.0)):.2f}",
                exit_code=str(check.get("exit_code", "")),
                summary=_to_markdown_cell(str(check.get("summary", ""))),
            )
        )
    failure_summary = report.get("failure_summary", [])
    if failure_summary:
        lines.append("")
        lines.append("## Failure Summary")
        lines.append("")
        for failure in failure_summary:
            lines.append(
                "- `{name}` (required={required}, exit_code={exit_code}): {summary}".format(
                    name=str(failure.get("name", "")),
                    required=str(failure.get("required", "")),
                    exit_code=str(failure.get("exit_code", "")),
                    summary=str(failure.get("summary", "")),
                )
            )
    return "\n".join(lines) + "\n"


def _run_check(*, check: ReleaseGateCheck, cwd: str | Path, max_output_chars: int) -> ReleaseGateCheckResult:
    started = datetime.now(timezone.utc)
    started_text = started.isoformat().replace("+00:00", "Z")
    started_monotonic = time.monotonic()
    process = subprocess.run(
        check.command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    finished = datetime.now(timezone.utc)
    finished_text = finished.isoformat().replace("+00:00", "Z")
    duration_seconds = max(0.0, time.monotonic() - started_monotonic)
    stdout_tail = _tail_text(process.stdout or "", max_chars=max_output_chars)
    stderr_tail = _tail_text(process.stderr or "", max_chars=max_output_chars)
    status = "pass" if process.returncode == 0 else "fail"
    summary = _build_summary(status=status, stdout_tail=stdout_tail, stderr_tail=stderr_tail)
    return ReleaseGateCheckResult(
        name=check.name,
        description=check.description,
        required=check.required,
        command=list(check.command),
        status=status,
        exit_code=int(process.returncode),
        started_at_utc=started_text,
        finished_at_utc=finished_text,
        duration_seconds=round(duration_seconds, 3),
        summary=summary,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
    )


def _build_summary(*, status: str, stdout_tail: str, stderr_tail: str) -> str:
    if status == "pass":
        candidate = _first_non_empty_line(stdout_tail) or "ok"
        return candidate[:200]
    detail = _best_failure_line(stderr_tail) or _best_failure_line(stdout_tail) or "failed"
    return detail[:200]


def _first_non_empty_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _best_failure_line(text: str) -> str | None:
    blocked_prefixes = (
        "traceback",
        "file ",
        "the above exception",
        "during handling",
    )
    candidates: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        candidates.append(stripped)
    for line in reversed(candidates):
        lowered = line.lower()
        if any(lowered.startswith(prefix) for prefix in blocked_prefixes):
            continue
        if lowered.startswith("^"):
            continue
        return line
    return _first_non_empty_line(text)


def _tail_text(text: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _resolve_git_ref(*, cwd: str | Path) -> str:
    env_ref = str(os.getenv("GITHUB_SHA", "")).strip()
    if env_ref:
        return env_ref
    for command in (
        ["git", "-c", "safe.directory=*", "rev-parse", "HEAD"],
        ["git", "rev-parse", "HEAD"],
    ):
        try:
            process = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            continue
        if process.returncode == 0:
            value = str(process.stdout or "").strip()
            if value:
                return value
    return "unknown"


def _to_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br/>")
