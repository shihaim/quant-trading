from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_me_read_service_never_uses_owner_resolution():
    source = _repo_text("trader/me/read_service.py")

    assert "resolve_owner_user_id" not in source
    assert "scope_user_id=user_id" in source


def test_owner_resolution_usage_is_limited_to_known_compatibility_paths():
    matches = {
        str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        for path in REPO_ROOT.rglob("*.py")
        if "node_modules" not in path.parts
        and ".next" not in path.parts
        and "logs" not in path.parts
        and path.name not in {"test_v3_compatibility_guards.py", "test_p1_rehearsal.py"}
        and "resolve_owner_user_id" in path.read_text(encoding="utf-8")
    }

    assert matches == set()


def test_f2_cleanup_plan_documents_remaining_compatibility_zones():
    doc = _repo_text("docs/reports/f2_v3_compatibility_fallback_cleanup_plan_2026-05-16.md")

    assert "TradingScheduler(user_id=None)" in doc
    assert "hard error" in doc
    assert "trader/app/p1_rehearsal.py" in doc
    assert "--user-id" in doc
    assert "OPS_API_ADMIN_EMAILS" in doc
    assert "/api/me/*" in doc


def test_p1_rehearsal_requires_explicit_user_id_without_owner_fallback():
    source = _repo_text("trader/app/p1_rehearsal.py")

    assert "--user-id" in source
    assert "_resolve_rehearsal_user_id" in source
    assert 'raise ValueError("user_id_required")' in source
    assert "resolve_owner_user_id" not in source


def test_web_no_longer_displays_owner_user_compatibility_scope():
    web_root = REPO_ROOT / "apps" / "web"
    web_files = []
    for relative_root in ("app", "components", "lib"):
        for suffix in ("*.ts", "*.tsx"):
            web_files.extend((web_root / relative_root).rglob(suffix))
    offenders = []
    for path in web_files:
        source = path.read_text(encoding="utf-8")
        if "owner_user_id" in source or "compatibility user" in source:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []


def test_ops_service_uses_scope_user_naming_not_owner_user():
    source = _repo_text("trader/ops/service.py")

    assert "owner_user_id" not in source
    assert "scope_user_id" in source


def test_load_for_user_does_not_fallback_to_global_bot_config():
    source = _repo_text("trader/config/config_repo.py")
    start = source.index("    def load_for_user")
    end = source.index("    def get_runtime_state", start)
    method = source[start:end]

    assert "self.load()" not in method
    assert "UserBotConfig(user_id=normalized_user_id)" in method
