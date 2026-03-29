from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from trader.auth.credentials import CredentialValidationError, UserCredentialService
from trader.data.db import Base
from trader.data.models import User, UserExchangeCredential


@dataclass
class UserAuditRow:
    user_id: int
    email: str
    status: str
    key_version: str | None
    detail: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit active-user UPBIT credential coverage and decrypt validity.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "sqlite:///./trading.db"),
        help="SQLAlchemy database URL (default: DATABASE_URL env or sqlite:///./trading.db).",
    )
    parser.add_argument(
        "--encryption-key",
        default=os.getenv("OPS_API_CREDENTIALS_ENCRYPTION_KEY", ""),
        help="Credential encryption key (default: OPS_API_CREDENTIALS_ENCRYPTION_KEY env).",
    )
    parser.add_argument(
        "--active-key-version",
        default=os.getenv("OPS_API_CREDENTIALS_ACTIVE_KEY_VERSION", "v1"),
        help="Active key version used for new writes.",
    )
    parser.add_argument(
        "--keyring-json",
        default=os.getenv("OPS_API_CREDENTIALS_KEYRING_JSON", "{}"),
        help="JSON object for key version map, e.g. {'v1':'old','v2':'new'}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max rows per bucket to print in text mode.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output instead of text table.",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit non-zero if any active user is missing UPBIT credentials.",
    )
    parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="Exit non-zero if any active user has invalid/decrypt-failed credentials.",
    )
    parser.add_argument(
        "--bootstrap-empty-schema",
        action="store_true",
        help="Create empty schema when core tables are missing (for CI/local reproducibility).",
    )
    return parser.parse_args()


def collect_rows(args: argparse.Namespace) -> dict[str, object]:
    engine = create_engine(args.database_url, future=True)
    if bool(args.bootstrap_empty_schema):
        _bootstrap_or_patch_schema(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    rows: list[UserAuditRow] = []
    key_versions: dict[str, int] = {}

    with Session() as session:
        service = UserCredentialService(
            session=session,
            encryption_key=args.encryption_key,
            active_key_version=args.active_key_version,
            keyring_json=args.keyring_json,
        )
        users = session.execute(select(User).where(User.is_active.is_(True)).order_by(User.id.asc())).scalars().all()
        for user in users:
            credential = session.execute(
                select(UserExchangeCredential).where(
                    UserExchangeCredential.user_id == user.id,
                    UserExchangeCredential.exchange == "UPBIT",
                )
            ).scalar_one_or_none()
            if credential is None:
                rows.append(
                    UserAuditRow(
                        user_id=int(user.id),
                        email=str(user.email),
                        status="missing",
                        key_version=None,
                        detail="credentials_required",
                    )
                )
                continue

            key_version = str(getattr(credential, "key_version", "v1") or "v1")
            key_versions[key_version] = int(key_versions.get(key_version, 0)) + 1
            try:
                service.get_exchange_credentials_by_user_id(user_id=user.id, exchange="UPBIT")
                rows.append(
                    UserAuditRow(
                        user_id=int(user.id),
                        email=str(user.email),
                        status="valid",
                        key_version=key_version,
                        detail=None,
                    )
                )
            except CredentialValidationError as exc:
                rows.append(
                    UserAuditRow(
                        user_id=int(user.id),
                        email=str(user.email),
                        status="invalid",
                        key_version=key_version,
                        detail=exc.code,
                    )
                )

    engine.dispose()

    valid = [row for row in rows if row.status == "valid"]
    missing = [row for row in rows if row.status == "missing"]
    invalid = [row for row in rows if row.status == "invalid"]
    return {
        "summary": {
            "active_users": len(rows),
            "valid_users": len(valid),
            "missing_users": len(missing),
            "invalid_users": len(invalid),
            "key_versions": key_versions,
        },
        "valid": valid,
        "missing": missing,
        "invalid": invalid,
    }


def _bootstrap_or_patch_schema(engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names or "user_exchange_credentials" not in table_names:
        Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())

    if "users" in table_names:
        user_cols = {col["name"] for col in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "token_version" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 1"))
            if "is_admin" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"))
            conn.execute(text("UPDATE users SET token_version = CASE WHEN token_version IS NULL OR token_version <= 0 THEN 1 ELSE token_version END"))
            conn.execute(text("UPDATE users SET is_admin = CASE WHEN is_admin IS NULL THEN 0 ELSE is_admin END"))

    if "user_exchange_credentials" in table_names:
        cred_cols = {col["name"] for col in inspector.get_columns("user_exchange_credentials")}
        if "key_version" not in cred_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE user_exchange_credentials ADD COLUMN key_version VARCHAR(32) DEFAULT 'v1'"))
                conn.execute(text("UPDATE user_exchange_credentials SET key_version = 'v1' WHERE key_version IS NULL OR TRIM(key_version) = ''"))


def _print_text(report: dict[str, object], limit: int) -> None:
    summary = report["summary"]
    missing: list[UserAuditRow] = report["missing"]  # type: ignore[assignment]
    invalid: list[UserAuditRow] = report["invalid"]  # type: ignore[assignment]
    print("== Credential Coverage Summary ==")
    print(f"active_users : {summary['active_users']}")
    print(f"valid_users  : {summary['valid_users']}")
    print(f"missing_users: {summary['missing_users']}")
    print(f"invalid_users: {summary['invalid_users']}")
    print(f"key_versions : {summary['key_versions']}")
    print("")

    def _print_bucket(title: str, bucket: list[UserAuditRow]) -> None:
        print(f"== {title} ({len(bucket)}) ==")
        for row in bucket[: max(0, int(limit))]:
            detail = f" detail={row.detail}" if row.detail else ""
            key_version = f" key_version={row.key_version}" if row.key_version else ""
            print(f"user_id={row.user_id} email={row.email} status={row.status}{key_version}{detail}")
        if len(bucket) > limit:
            print(f"... truncated {len(bucket) - limit} row(s)")
        print("")

    _print_bucket("MISSING", missing)
    _print_bucket("INVALID", invalid)


def main() -> int:
    args = parse_args()
    if not args.encryption_key:
        print("error: --encryption-key (or OPS_API_CREDENTIALS_ENCRYPTION_KEY env) is required")
        return 2

    report = collect_rows(args)
    if args.json:
        encoded = {
            "summary": report["summary"],
            "valid": [asdict(row) for row in report["valid"]],  # type: ignore[index]
            "missing": [asdict(row) for row in report["missing"]],  # type: ignore[index]
            "invalid": [asdict(row) for row in report["invalid"]],  # type: ignore[index]
        }
        print(json.dumps(encoded, ensure_ascii=False, indent=2))
    else:
        _print_text(report, args.limit)

    summary = report["summary"]  # type: ignore[assignment]
    has_missing = int(summary["missing_users"]) > 0
    has_invalid = int(summary["invalid_users"]) > 0
    if args.fail_on_missing and has_missing:
        return 3
    if args.fail_on_invalid and has_invalid:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
