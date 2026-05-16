from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ops_timezone_helper_only_drops_repo_managed_views():
    sql = (REPO_ROOT / "scripts/sql/ops_drop_views_set_timezone_asia_seoul.sql").read_text(encoding="utf-8")

    assert "FROM pg_views" not in sql
    assert "WHERE schemaname = 'public'" not in sql
    assert "CASCADE" not in sql
    assert "orders_kst" in sql
    assert "schema_column_docs_kst" in sql


def test_ops_timezone_helper_uses_current_database_and_user():
    sql = (REPO_ROOT / "scripts/sql/ops_drop_views_set_timezone_asia_seoul.sql").read_text(encoding="utf-8")

    assert "current_database()" in sql
    assert "current_user" in sql
    assert "format('ALTER DATABASE %I SET timezone TO %L'" in sql
    assert "format('ALTER ROLE %I SET timezone TO %L'" in sql
    assert "ALTER DATABASE trading" not in sql
    assert "ALTER ROLE trader" not in sql
