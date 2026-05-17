from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class V3UserScopeSqlPlan:
    """Staged SQL plan for V3.1 user-scope migration."""

    expand_sql: tuple[str, ...]
    dual_path_sql: tuple[str, ...]
    cleanup_sql: tuple[str, ...]
    rollback_sql: tuple[str, ...]
    validation_sql: tuple[str, ...]


def build_v3_user_scope_sql_plan(legacy_user_id: int = 1) -> V3UserScopeSqlPlan:
    """
    Build SQL plan text for staged migration.

    The plan intentionally separates schema expansion from cleanup so runtime
    code can move to user-scoped reads/writes in controlled phases.
    """
    legacy = max(1, int(legacy_user_id))
    expand_sql = (
        "-- expand: additive schema updates",
        "ALTER TABLE orders ADD COLUMN user_id INTEGER DEFAULT 1;",
        "ALTER TABLE positions ADD COLUMN user_id INTEGER DEFAULT 1;",
        "ALTER TABLE daily_equity ADD COLUMN user_id INTEGER DEFAULT 1;",
        "ALTER TABLE paper_wallet ADD COLUMN user_id INTEGER DEFAULT 1;",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_user_client_order_id ON orders(user_id, client_order_id);",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_equity_user_date ON daily_equity(user_id, date_utc);",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_wallet_user ON paper_wallet(user_id);",
        "CREATE TABLE IF NOT EXISTS user_bot_config ("
        " id SERIAL PRIMARY KEY,"
        " user_id INTEGER NOT NULL UNIQUE,"
        " is_enabled BOOLEAN DEFAULT TRUE,"
        " timeframe VARCHAR(16) DEFAULT '15m',"
        " markets_json TEXT DEFAULT '[\"KRW-BTC\"]',"
        " target_exposure_pct NUMERIC(10,6) DEFAULT 0.10,"
        " daily_loss_basis VARCHAR(32) DEFAULT 'TOTAL',"
        " min_rebalance_threshold_pct NUMERIC(10,6) DEFAULT 0.05,"
        " min_order_krw_buffer NUMERIC(18,8) DEFAULT 0,"
        " fill_timeout_sec_entry INTEGER DEFAULT 10,"
        " fill_timeout_sec_exit INTEGER DEFAULT 4,"
        " fill_timeout_sec_rebalance INTEGER DEFAULT 10,"
        " max_reprice_attempts_entry INTEGER DEFAULT 2,"
        " max_reprice_attempts_exit INTEGER DEFAULT 1,"
        " max_reprice_attempts_rebalance INTEGER DEFAULT 1,"
        " reprice_step_bps INTEGER DEFAULT 10,"
        " slippage_budget_entry_pct NUMERIC(10,6) DEFAULT 0.0005,"
        " slippage_budget_exit_pct NUMERIC(10,6) DEFAULT 0.0020,"
        " slippage_budget_breach_halt_count INTEGER DEFAULT 0,"
        " status_notify_interval_seconds INTEGER DEFAULT 14400,"
        " max_daily_loss_pct NUMERIC(10,6) DEFAULT 0.02,"
        " max_weekly_loss_pct NUMERIC(10,6) DEFAULT 0,"
        " max_monthly_loss_pct NUMERIC(10,6) DEFAULT 0,"
        " cooldown_hours_on_halt INTEGER DEFAULT 0,"
        " max_new_orders_per_day INTEGER DEFAULT 0,"
        " max_orders_per_week INTEGER DEFAULT 0,"
        " min_edge_pct NUMERIC(10,6) DEFAULT 0,"
        " max_total_exposure_pct NUMERIC(10,6) DEFAULT 0.30,"
        " max_per_market_exposure_pct NUMERIC(10,6) DEFAULT 0.10,"
        " created_at TIMESTAMPTZ DEFAULT NOW(),"
        " updated_at TIMESTAMPTZ DEFAULT NOW()"
        ");",
        "CREATE TABLE IF NOT EXISTS user_bot_runtime ("
        " id SERIAL PRIMARY KEY,"
        " user_id INTEGER NOT NULL UNIQUE,"
        " is_enabled BOOLEAN DEFAULT TRUE,"
        " status VARCHAR(32) DEFAULT 'IDLE',"
        " last_tick_at TIMESTAMPTZ NULL,"
        " last_error TEXT NULL,"
        " consecutive_failures INTEGER DEFAULT 0,"
        " halt_reason VARCHAR(64) NULL,"
        " cooldown_until TIMESTAMPTZ NULL,"
        " halted_at TIMESTAMPTZ NULL,"
        " created_at TIMESTAMPTZ DEFAULT NOW(),"
        " updated_at TIMESTAMPTZ DEFAULT NOW()"
        ");",
        "CREATE TABLE IF NOT EXISTS audit_log ("
        " id SERIAL PRIMARY KEY,"
        " actor_user_id INTEGER NULL,"
        " action VARCHAR(64) NOT NULL,"
        " target_type VARCHAR(64) NOT NULL,"
        " target_id VARCHAR(128) NULL,"
        " metadata_json TEXT NOT NULL DEFAULT '{}',"
        " created_at TIMESTAMPTZ DEFAULT NOW()"
        ");",
        "CREATE INDEX IF NOT EXISTS ix_audit_log_actor_user_id ON audit_log(actor_user_id);",
        "CREATE INDEX IF NOT EXISTS ix_audit_log_action ON audit_log(action);",
        "CREATE INDEX IF NOT EXISTS ix_audit_log_target_type ON audit_log(target_type);",
        "CREATE INDEX IF NOT EXISTS ix_audit_log_target_id ON audit_log(target_id);",
        "CREATE INDEX IF NOT EXISTS ix_audit_log_created_at ON audit_log(created_at);",
        "ALTER TABLE user_exchange_credentials ADD COLUMN key_version VARCHAR(32) DEFAULT 'v1';",
        "CREATE INDEX IF NOT EXISTS ix_user_exchange_credentials_key_version ON user_exchange_credentials(key_version);",
        "CREATE TABLE IF NOT EXISTS user_api_budget ("
        " id SERIAL PRIMARY KEY,"
        " user_id INTEGER NOT NULL,"
        " scope VARCHAR(16) NOT NULL,"
        " window_started_at TIMESTAMPTZ DEFAULT NOW(),"
        " window_seconds INTEGER NOT NULL DEFAULT 60,"
        " request_count INTEGER NOT NULL DEFAULT 0,"
        " blocked_count INTEGER NOT NULL DEFAULT 0,"
        " created_at TIMESTAMPTZ DEFAULT NOW(),"
        " updated_at TIMESTAMPTZ DEFAULT NOW(),"
        " UNIQUE(user_id, scope)"
        ");",
        "CREATE INDEX IF NOT EXISTS ix_user_api_budget_user_id ON user_api_budget(user_id);",
        "CREATE INDEX IF NOT EXISTS ix_user_api_budget_scope ON user_api_budget(scope);",
        "CREATE INDEX IF NOT EXISTS ix_user_api_budget_window_started_at ON user_api_budget(window_started_at);",
        "CREATE TABLE IF NOT EXISTS user_risk_guard ("
        " id SERIAL PRIMARY KEY,"
        " user_id INTEGER NOT NULL UNIQUE,"
        " manual_halt BOOLEAN NOT NULL DEFAULT FALSE,"
        " emergency_kill_switch BOOLEAN NOT NULL DEFAULT FALSE,"
        " reason TEXT NULL,"
        " updated_by_user_id INTEGER NULL,"
        " created_at TIMESTAMPTZ DEFAULT NOW(),"
        " updated_at TIMESTAMPTZ DEFAULT NOW()"
        ");",
        "CREATE INDEX IF NOT EXISTS ix_user_risk_guard_user_id ON user_risk_guard(user_id);",
        "CREATE INDEX IF NOT EXISTS ix_user_risk_guard_manual_halt ON user_risk_guard(manual_halt);",
        "CREATE INDEX IF NOT EXISTS ix_user_risk_guard_emergency_kill_switch ON user_risk_guard(emergency_kill_switch);",
        "-- expand backfill",
        f"UPDATE orders SET user_id = COALESCE(user_id, {legacy});",
        f"UPDATE positions SET user_id = COALESCE(user_id, {legacy});",
        f"UPDATE daily_equity SET user_id = COALESCE(user_id, {legacy});",
        f"UPDATE paper_wallet SET user_id = COALESCE(user_id, {legacy});",
        "INSERT INTO user_bot_config ("
        " user_id, is_enabled, timeframe, markets_json, target_exposure_pct, daily_loss_basis,"
        " min_rebalance_threshold_pct, min_order_krw_buffer, fill_timeout_sec_entry, fill_timeout_sec_exit,"
        " fill_timeout_sec_rebalance, max_reprice_attempts_entry, max_reprice_attempts_exit,"
        " max_reprice_attempts_rebalance, reprice_step_bps, slippage_budget_entry_pct, slippage_budget_exit_pct,"
        " slippage_budget_breach_halt_count, status_notify_interval_seconds, max_daily_loss_pct,"
        " max_weekly_loss_pct, max_monthly_loss_pct, cooldown_hours_on_halt,"
        " max_new_orders_per_day, max_orders_per_week, min_edge_pct,"
        " max_total_exposure_pct, max_per_market_exposure_pct, created_at, updated_at"
        ")"
        " SELECT"
        f" {legacy}, is_enabled, timeframe, markets_json, target_exposure_pct, daily_loss_basis,"
        " min_rebalance_threshold_pct, min_order_krw_buffer, fill_timeout_sec_entry, fill_timeout_sec_exit,"
        " fill_timeout_sec_rebalance, max_reprice_attempts_entry, max_reprice_attempts_exit,"
        " max_reprice_attempts_rebalance, reprice_step_bps, slippage_budget_entry_pct, slippage_budget_exit_pct,"
        " slippage_budget_breach_halt_count, status_notify_interval_seconds, max_daily_loss_pct,"
        " max_weekly_loss_pct, max_monthly_loss_pct, cooldown_hours_on_halt,"
        " max_new_orders_per_day, max_orders_per_week, min_edge_pct,"
        " max_total_exposure_pct, max_per_market_exposure_pct, NOW(), NOW()"
        " FROM bot_config WHERE id = 1"
        f" AND NOT EXISTS (SELECT 1 FROM user_bot_config WHERE user_id = {legacy});",
    )
    dual_path_sql = (
        "-- dual-path: write both legacy and user-scoped paths",
        "Persist user_id on order create, fill application, position updates, and daily_equity snapshots.",
        "Use user-scoped idempotency key policy: (user_id, client_order_id).",
        "Read runtime config from user_bot_config; create a default user row if missing.",
        "Read runtime state from user_bot_runtime with fallback defaults.",
    )
    cleanup_sql = (
        "-- cleanup: remove legacy global assumptions after dual-path stabilizes",
        "Enforce NOT NULL and foreign key constraints for user_id on target tables.",
        "Add unique constraints scoped by user_id where required by business keys.",
        "Delete legacy bridge read paths and remove reliance on bot_config(id=1).",
    )
    rollback_sql = (
        "-- rollback: keep rollback scripts ready before production execution",
        "DROP TABLE IF EXISTS user_api_budget;",
        "DROP TABLE IF EXISTS user_risk_guard;",
        "DROP TABLE IF EXISTS audit_log;",
        "DROP TABLE IF EXISTS user_bot_runtime;",
        "DROP TABLE IF EXISTS user_bot_config;",
        "ALTER TABLE orders DROP COLUMN user_id;",
        "ALTER TABLE positions DROP COLUMN user_id;",
        "ALTER TABLE daily_equity DROP COLUMN user_id;",
        "ALTER TABLE paper_wallet DROP COLUMN user_id;",
    )
    validation_sql = (
        "SELECT user_id, COUNT(*) AS row_count FROM orders GROUP BY user_id ORDER BY user_id;",
        "SELECT user_id, COUNT(*) AS row_count FROM positions GROUP BY user_id ORDER BY user_id;",
        "SELECT user_id, COUNT(*) AS row_count FROM daily_equity GROUP BY user_id ORDER BY user_id;",
        "SELECT user_id, COUNT(*) AS row_count FROM paper_wallet GROUP BY user_id ORDER BY user_id;",
        "SELECT COALESCE(SUM(realized_pnl), 0) AS total_realized_pnl FROM positions;",
        "SELECT COALESCE(SUM(last_equity), 0) AS total_last_equity FROM daily_equity;",
    )
    return V3UserScopeSqlPlan(
        expand_sql=expand_sql,
        dual_path_sql=dual_path_sql,
        cleanup_sql=cleanup_sql,
        rollback_sql=rollback_sql,
        validation_sql=validation_sql,
    )


def build_backfill_report(session: Session) -> dict[str, list[dict[str, int]]]:
    """Return row-count report grouped by user_id for V3.1 acceptance checks."""
    report: dict[str, list[dict[str, int]]] = {}
    for table_name in ("orders", "positions", "daily_equity", "paper_wallet"):
        rows = session.execute(
            text(
                f"""
                SELECT user_id, COUNT(*) AS row_count
                FROM {table_name}
                GROUP BY user_id
                ORDER BY user_id
                """
            )
        ).mappings()
        report[table_name] = [{"user_id": int(row["user_id"]), "row_count": int(row["row_count"])} for row in rows]
    return report


def read_pnl_totals(session: Session) -> dict[str, Decimal]:
    """Read aggregate totals used for pre/post migration integrity checks."""
    total_realized = session.execute(text("SELECT COALESCE(SUM(realized_pnl), 0) FROM positions")).scalar_one()
    total_last_equity = session.execute(text("SELECT COALESCE(SUM(last_equity), 0) FROM daily_equity")).scalar_one()
    return {
        "positions_realized_pnl_total": Decimal(str(total_realized or 0)),
        "daily_equity_last_equity_total": Decimal(str(total_last_equity or 0)),
    }
