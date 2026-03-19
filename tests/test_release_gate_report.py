from __future__ import annotations

import json
from pathlib import Path

from trader.release_gate import ReleaseGateCheck, render_markdown_report, run_release_gate, write_report_files


def test_release_gate_report_marks_failure_and_includes_failure_summary(tmp_path):
    checks = [
        ReleaseGateCheck(
            name="pass_check",
            description="should pass",
            command=["python", "-c", "print('pass')"],
        ),
        ReleaseGateCheck(
            name="fail_check",
            description="should fail",
            command=["python", "-c", "import sys; print('boom'); sys.exit(3)"],
        ),
    ]
    report = run_release_gate(checks=checks, cwd=tmp_path, max_output_chars=500)

    assert report["overall_status"] == "fail"
    assert report["summary"]["failed_checks"] == 1
    assert report["summary"]["failed_required_checks"] == 1
    assert report["failure_summary"][0]["name"] == "fail_check"
    assert report["failure_summary"][0]["exit_code"] == 3
    assert report["failure_summary"][0]["summary"]

    markdown = render_markdown_report(report)
    assert "## Failure Summary" in markdown
    assert "fail_check" in markdown
    assert "exit_code=3" in markdown


def test_release_gate_report_writes_json_and_markdown_files(tmp_path):
    checks = [
        ReleaseGateCheck(
            name="only_pass",
            description="single pass check",
            command=["python", "-c", "print('ok')"],
        )
    ]
    report = run_release_gate(checks=checks, cwd=tmp_path, max_output_chars=200)
    json_path, markdown_path = write_report_files(report=report, output_dir=tmp_path)

    assert json_path.exists()
    assert markdown_path.exists()

    loaded = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert loaded["overall_status"] == "pass"
    assert loaded["summary"]["passed_checks"] == 1

    markdown = Path(markdown_path).read_text(encoding="utf-8")
    assert "# Release Gate Report" in markdown
    assert "only_pass" in markdown
