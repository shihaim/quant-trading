from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_me_read_service_never_uses_owner_resolution():
    source = _repo_text("trader/me/read_service.py")

    assert "resolve_owner_user_id" not in source
    assert "scope_user_id=user_id" in source


def test_owner_resolution_usage_is_limited_to_known_compatibility_paths():
    allowed_paths = {
        "trader/config/config_repo.py",
        "trader/trading/scheduler.py",
        "trader/app/p1_rehearsal.py",
        "tests/test_config_repo.py",
    }
    matches = {
        str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        for path in REPO_ROOT.rglob("*.py")
        if "node_modules" not in path.parts
        and ".next" not in path.parts
        and "logs" not in path.parts
        and path.name not in {"test_v3_compatibility_guards.py", "test_p1_rehearsal.py"}
        and "resolve_owner_user_id" in path.read_text(encoding="utf-8")
    }

    assert matches == allowed_paths


def test_f2_cleanup_plan_documents_remaining_compatibility_zones():
    doc = _repo_text("docs/f2_v3_compatibility_fallback_cleanup_plan_2026-05-16.md")

    assert "TradingScheduler(user_id=None)" in doc
    assert "trader/app/p1_rehearsal.py" in doc
    assert "--user-id" in doc
    assert "OPS_API_ADMIN_EMAILS" in doc
    assert "/api/me/*" in doc


def test_p1_rehearsal_owner_resolution_is_fallback_only():
    source = _repo_text("trader/app/p1_rehearsal.py")

    assert "--user-id" in source
    assert "_resolve_rehearsal_user_id" in source
    assert "if explicit_user_id is not None" in source
