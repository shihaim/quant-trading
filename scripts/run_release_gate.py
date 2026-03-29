from __future__ import annotations

import argparse
from pathlib import Path

from trader.release_gate import ReleaseGateCheck, default_checks, run_release_gate, write_report_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run release gate checks and write release_gate_report.{json,md}",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write release_gate_report.json and release_gate_report.md",
    )
    parser.add_argument(
        "--max-output-chars",
        type=int,
        default=4000,
        help="Max stdout/stderr tail chars to keep per check result.",
    )
    parser.add_argument(
        "--include-localtest-smoke",
        action="store_true",
        help="Include local Docker smoke check using scripts/smoke-localtest-auth-admin.ps1.",
    )
    parser.add_argument(
        "--localtest-base-url",
        default="http://127.0.0.1:28080",
        help="Base URL passed to scripts/smoke-localtest-auth-admin.ps1.",
    )
    parser.add_argument(
        "--localtest-smoke-required",
        action="store_true",
        help="Mark local Docker smoke check as required.",
    )
    parser.add_argument(
        "--powershell-binary",
        default="powershell",
        help="PowerShell executable to run local smoke check (for example: powershell, pwsh).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cwd = Path(__file__).resolve().parents[1]
    checks = list(default_checks())
    if args.include_localtest_smoke:
        checks.append(
            ReleaseGateCheck(
                name="localtest_auth_admin_smoke",
                description="Local Docker auth/admin/session smoke via scripts/smoke-localtest-auth-admin.ps1",
                required=bool(args.localtest_smoke_required),
                command=[
                    str(args.powershell_binary),
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts/smoke-localtest-auth-admin.ps1",
                    "-BaseUrl",
                    str(args.localtest_base_url),
                ],
            )
        )
    report = run_release_gate(
        checks=checks,
        cwd=cwd,
        max_output_chars=int(args.max_output_chars),
    )
    json_path, markdown_path = write_report_files(report=report, output_dir=args.output_dir)
    print(f"release_gate_json={json_path}")
    print(f"release_gate_markdown={markdown_path}")
    print(f"release_gate_status={report.get('overall_status')}")
    return 0 if report.get("overall_status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
