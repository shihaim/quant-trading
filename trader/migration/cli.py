from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from trader.migration.contracts import DEFAULT_TABLES, PRIMARY_TABLES, MigrationOptions, PrimaryTableName
from trader.migration.merge import MigrationService

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate quant-trading data between SQLAlchemy-compatible databases.")
    parser.add_argument("--source-url", required=True, help="SQLAlchemy URL for the source database.")
    parser.add_argument("--target-url", required=True, help="SQLAlchemy URL for the target database.")
    parser.add_argument(
        "--tables",
        default=",".join(DEFAULT_TABLES),
        help="Comma-separated primary tables to migrate. Snapshot tables are controlled by --copy-snapshot-tables.",
    )
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for id-based table scans.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect counts and planned tables without writing.")
    parser.add_argument(
        "--skip-bootstrap-target",
        action="store_true",
        help="Skip Base.metadata.create_all() and target-side bootstrap helpers before migration.",
    )
    parser.add_argument(
        "--copy-snapshot-tables",
        action="store_true",
        help="Also copy positions, paper_wallet, and daily_equity after primary event tables.",
    )
    parser.add_argument(
        "--config-strategy",
        choices=("target_wins", "source_wins"),
        default="target_wins",
        help="Conflict policy for bot_config.",
    )
    parser.add_argument("--strict", action="store_true", help="Fail immediately if a selected table is missing.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    _configure_logging(verbose=args.verbose)

    try:
        options = MigrationOptions(
            source_url=args.source_url,
            target_url=args.target_url,
            tables=_parse_tables(args.tables),
            batch_size=max(1, args.batch_size),
            dry_run=bool(args.dry_run),
            bootstrap_target=not bool(args.skip_bootstrap_target),
            strict=bool(args.strict),
            copy_snapshot_tables=bool(args.copy_snapshot_tables),
            config_strategy=args.config_strategy,
        )
        summary = MigrationService().run(options)
        _log_summary(summary)
        return 0
    except Exception:
        logging.getLogger(__name__).exception("migration_failed")
        return 1


def _configure_logging(*, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT)


def _parse_tables(raw_tables: str) -> tuple[PrimaryTableName, ...]:
    parsed: list[PrimaryTableName] = []
    seen: set[str] = set()
    for raw in raw_tables.split(","):
        table_name = raw.strip()
        if not table_name or table_name in seen:
            continue
        if table_name not in PRIMARY_TABLES:
            allowed = ", ".join(DEFAULT_TABLES)
            raise ValueError(f"Unsupported table '{table_name}'. Allowed primary tables: {allowed}")
        parsed.append(table_name)
        seen.add(table_name)
    if not parsed:
        raise ValueError("At least one primary table must be selected")
    return tuple(parsed)


def _log_summary(summary) -> None:
    logger = logging.getLogger(__name__)
    action_label = "projected" if summary.options.dry_run else "applied"
    total_inserted = sum(stats.inserted for stats in summary.table_stats)
    total_updated = sum(stats.updated for stats in summary.table_stats)
    total_skipped = sum(stats.skipped for stats in summary.table_stats)
    logger.info(
        "migration_summary mode=%s tables=%s inserted=%s updated=%s skipped=%s",
        action_label,
        len(summary.table_stats),
        total_inserted,
        total_updated,
        total_skipped,
    )
    for stats in summary.table_stats:
        logger.info(
            "table=%s mode=%s source_rows=%s target_rows=%s inserted=%s updated=%s skipped=%s",
            stats.table_name,
            action_label,
            stats.source_rows,
            stats.target_rows,
            stats.inserted,
            stats.updated,
            stats.skipped,
        )
        for warning in stats.warnings:
            logger.warning("table=%s warning=%s", stats.table_name, warning)
