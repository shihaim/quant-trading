from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from trader.data.models import BotConfig, Candle, Fill, Order, OrderAttempt, TimeframeConfig, TradeMetric
from trader.migration.contracts import MigrationOptions, MigrationSummary, PrimaryTableName, TableStats
from trader.migration.engines import (
    bootstrap_target_database,
    build_runtime,
    dispose_runtime,
    list_tables,
)
from trader.migration.mappers import OrderIdMap
from trader.migration.readers import estimate_row_count, fetch_singleton, iter_rows_by_id
from trader.migration.rebuild import SnapshotTableSynchronizer

logger = logging.getLogger(__name__)
MAX_WARNING_COUNT = 10


def _assign_columns(target_row, source_row, exclude: tuple[str, ...] = ()) -> None:
    excluded = set(exclude)
    for column in source_row.__table__.columns:
        if column.name in excluded:
            continue
        setattr(target_row, column.name, getattr(source_row, column.name))


def _payload_from_row(source_row, exclude: tuple[str, ...] = ()) -> dict[str, object]:
    excluded = set(exclude)
    return {
        column.name: getattr(source_row, column.name)
        for column in source_row.__table__.columns
        if column.name not in excluded
    }


def _source_is_newer(source_value: datetime | None, target_value: datetime | None) -> bool:
    if source_value is None:
        return target_value is None
    if target_value is None:
        return True
    return source_value >= target_value


def _rows_differ(target_row, source_row, exclude: tuple[str, ...] = ()) -> bool:
    excluded = set(exclude)
    for column in source_row.__table__.columns:
        if column.name in excluded:
            continue
        if getattr(target_row, column.name) != getattr(source_row, column.name):
            return True
    return False


def _add_warning(stats: TableStats, message: str) -> None:
    if len(stats.warnings) < MAX_WARNING_COUNT:
        stats.warnings.append(message)


def _warn_or_raise(context: MigrationContext, stats: TableStats, message: str) -> None:
    if context.options.strict:
        raise ValueError(message)
    _add_warning(stats, message)


@dataclass
class MigrationContext:
    options: MigrationOptions
    source_session: Session
    target_session: Session
    order_id_map: OrderIdMap
    missing_target_tables: set[str]


class BaseTableMigrator:
    table_name: PrimaryTableName
    model = None

    def plan(self, context: MigrationContext) -> TableStats:
        return TableStats(
            table_name=self.table_name,
            source_rows=estimate_row_count(context.source_session, self.model),
            target_rows=0
            if self.table_name in context.missing_target_tables
            else estimate_row_count(context.target_session, self.model),
        )

    def run(self, context: MigrationContext) -> TableStats:
        raise NotImplementedError


class BotConfigMigrator(BaseTableMigrator):
    table_name: PrimaryTableName = "bot_config"
    model = BotConfig

    def run(self, context: MigrationContext) -> TableStats:
        stats = self.plan(context)
        source_row = fetch_singleton(context.source_session, BotConfig, 1)
        if source_row is None:
            return stats

        target_row = None if self.table_name in context.missing_target_tables else context.target_session.get(BotConfig, 1)
        if target_row is None:
            stats.inserted += 1
            if not context.options.dry_run:
                target_row = BotConfig(id=1, **_payload_from_row(source_row, exclude=("id",)))
                context.target_session.add(target_row)
        elif context.options.config_strategy == "source_wins" and _rows_differ(target_row, source_row, exclude=("id",)):
            stats.updated += 1
            if not context.options.dry_run:
                _assign_columns(target_row, source_row, exclude=("id",))
        else:
            stats.skipped += 1
        if context.options.dry_run:
            return stats
        context.target_session.commit()
        return stats


class TimeframeConfigMigrator(BaseTableMigrator):
    table_name: PrimaryTableName = "timeframe_config"
    model = TimeframeConfig

    def run(self, context: MigrationContext) -> TableStats:
        stats = self.plan(context)
        target_missing = self.table_name in context.missing_target_tables

        for batch in iter_rows_by_id(context.source_session, TimeframeConfig, context.options.batch_size):
            for source_row in batch:
                target_row = None
                if not target_missing:
                    target_row = context.target_session.scalar(
                        select(TimeframeConfig).where(TimeframeConfig.timeframe == source_row.timeframe)
                    )
                if target_row is None:
                    stats.inserted += 1
                    if not context.options.dry_run:
                        target_row = TimeframeConfig(**_payload_from_row(source_row, exclude=("id",)))
                        context.target_session.add(target_row)
                elif _rows_differ(target_row, source_row, exclude=("id", "timeframe")):
                    stats.updated += 1
                    if not context.options.dry_run:
                        _assign_columns(target_row, source_row, exclude=("id", "timeframe"))
                else:
                    stats.skipped += 1
            if not context.options.dry_run:
                context.target_session.commit()
        return stats


class OrdersMigrator(BaseTableMigrator):
    table_name: PrimaryTableName = "orders"
    model = Order

    def run(self, context: MigrationContext) -> TableStats:
        stats = self.plan(context)
        target_missing = self.table_name in context.missing_target_tables

        for batch in iter_rows_by_id(context.source_session, Order, context.options.batch_size):
            for source_row in batch:
                target_row = None
                if not target_missing:
                    target_row = context.target_session.scalar(
                        select(Order).where(Order.client_order_id == source_row.client_order_id)
                    )
                if target_row is None:
                    stats.inserted += 1
                    if context.options.dry_run:
                        context.order_id_map.remember(source_row.id, -int(source_row.id))
                    else:
                        target_row = Order(**_payload_from_row(source_row, exclude=("id",)))
                        context.target_session.add(target_row)
                        context.target_session.flush()
                        context.order_id_map.remember(source_row.id, target_row.id)
                else:
                    identity_conflict = any(
                        getattr(target_row, field_name) != getattr(source_row, field_name)
                        for field_name in ("market", "side", "ord_type")
                    )
                    if identity_conflict:
                        stats.skipped += 1
                        _warn_or_raise(
                            context,
                            stats,
                            "Order conflict for client_order_id="
                            f"{source_row.client_order_id}: immutable identity fields differ between source and target",
                        )
                    elif _source_is_newer(source_row.updated_at, target_row.updated_at) and _rows_differ(
                        target_row,
                        source_row,
                        exclude=("id", "client_order_id"),
                    ):
                        stats.updated += 1
                        if not context.options.dry_run:
                            _assign_columns(target_row, source_row, exclude=("id", "client_order_id"))
                    else:
                        stats.skipped += 1
                    context.order_id_map.remember(source_row.id, target_row.id)
            if not context.options.dry_run:
                context.target_session.commit()
        return stats


class OrderAttemptsMigrator(BaseTableMigrator):
    table_name: PrimaryTableName = "order_attempts"
    model = OrderAttempt

    def run(self, context: MigrationContext) -> TableStats:
        stats = self.plan(context)
        target_missing = self.table_name in context.missing_target_tables

        for batch in iter_rows_by_id(context.source_session, OrderAttempt, context.options.batch_size):
            for source_row in batch:
                target_order_id = context.order_id_map.resolve(source_row.order_id)
                if target_order_id is None:
                    stats.skipped += 1
                    _warn_or_raise(
                        context,
                        stats,
                        "OrderAttempt skipped for source attempt_id="
                        f"{source_row.id}: missing order mapping for source order_id={source_row.order_id}",
                    )
                    continue

                target_row = None
                matched_by_fallback = False
                if not target_missing:
                    target_row = context.target_session.scalar(
                        select(OrderAttempt).where(
                            OrderAttempt.order_id == target_order_id,
                            OrderAttempt.attempt_no == source_row.attempt_no,
                        )
                    )
                    if target_row is None and source_row.upbit_uuid:
                        target_row = context.target_session.scalar(
                            select(OrderAttempt).where(OrderAttempt.upbit_uuid == source_row.upbit_uuid)
                        )
                        matched_by_fallback = target_row is not None
                    if target_row is None and source_row.upbit_identifier:
                        target_row = context.target_session.scalar(
                            select(OrderAttempt).where(OrderAttempt.upbit_identifier == source_row.upbit_identifier)
                        )
                        matched_by_fallback = target_row is not None

                if target_row is None:
                    stats.inserted += 1
                    if not context.options.dry_run:
                        payload = _payload_from_row(source_row, exclude=("id", "order_id"))
                        context.target_session.add(OrderAttempt(order_id=target_order_id, **payload))
                    continue

                if matched_by_fallback:
                    _add_warning(
                        stats,
                        "OrderAttempt matched by exchange reference instead of (order_id, attempt_no): "
                        f"source attempt_id={source_row.id}",
                    )

                if (
                    target_row.submit_reason != source_row.submit_reason
                    and source_row.submit_reason
                    and target_row.submit_reason
                ):
                    _add_warning(
                        stats,
                        "OrderAttempt submit_reason differs for "
                        f"target order_id={target_order_id} attempt_no={target_row.attempt_no}",
                    )

                if _source_is_newer(source_row.updated_at, target_row.updated_at) and _rows_differ(
                    target_row,
                    source_row,
                    exclude=("id", "order_id", "attempt_no"),
                ):
                    stats.updated += 1
                    if not context.options.dry_run:
                        _assign_columns(target_row, source_row, exclude=("id", "order_id", "attempt_no"))
                        target_row.order_id = target_order_id
                else:
                    stats.skipped += 1

            if not context.options.dry_run:
                context.target_session.commit()
        return stats


class FillsMigrator(BaseTableMigrator):
    table_name: PrimaryTableName = "fills"
    model = Fill

    def run(self, context: MigrationContext) -> TableStats:
        stats = self.plan(context)
        target_missing = self.table_name in context.missing_target_tables

        for batch in iter_rows_by_id(context.source_session, Fill, context.options.batch_size):
            for source_row in batch:
                target_order_id = context.order_id_map.resolve(source_row.order_id)
                if target_order_id is None:
                    stats.skipped += 1
                    if len(stats.warnings) < 10:
                        stats.warnings.append(
                            f"Skipped fill trade_id={source_row.trade_id}: missing order mapping for source order_id={source_row.order_id}"
                        )
                    continue
                existing = None
                if not target_missing:
                    existing = context.target_session.scalar(select(Fill).where(Fill.trade_id == source_row.trade_id))
                if existing is not None:
                    fill_conflict = (
                        existing.order_id != target_order_id
                        or existing.price != source_row.price
                        or existing.volume != source_row.volume
                        or existing.fee != source_row.fee
                        or existing.is_applied != source_row.is_applied
                        or existing.executed_at != source_row.executed_at
                    )
                    if fill_conflict:
                        stats.skipped += 1
                        _warn_or_raise(
                            context,
                            stats,
                            f"Fill conflict for trade_id={source_row.trade_id}: existing row differs from source payload",
                        )
                        continue
                    stats.skipped += 1
                    continue
                stats.inserted += 1
                if not context.options.dry_run:
                    payload = _payload_from_row(source_row, exclude=("id", "order_id"))
                    context.target_session.add(Fill(order_id=target_order_id, **payload))
            if not context.options.dry_run:
                context.target_session.commit()
        return stats


class TradeMetricsMigrator(BaseTableMigrator):
    table_name: PrimaryTableName = "trade_metrics"
    model = TradeMetric

    def run(self, context: MigrationContext) -> TableStats:
        stats = self.plan(context)
        target_missing = self.table_name in context.missing_target_tables

        for batch in iter_rows_by_id(context.source_session, TradeMetric, context.options.batch_size):
            for source_row in batch:
                target_order_id = context.order_id_map.resolve(source_row.order_id)
                if target_order_id is None:
                    stats.skipped += 1
                    if len(stats.warnings) < 10:
                        stats.warnings.append(
                            f"Skipped trade_metrics id={source_row.id}: missing order mapping for source order_id={source_row.order_id}"
                        )
                    continue
                if target_missing or target_order_id < 0:
                    existing = None
                else:
                    existing = context.target_session.scalar(
                        select(TradeMetric).where(TradeMetric.order_id == target_order_id)
                    )
                if existing is None:
                    stats.inserted += 1
                    if not context.options.dry_run:
                        payload = _payload_from_row(source_row, exclude=("id", "order_id"))
                        context.target_session.add(TradeMetric(order_id=target_order_id, **payload))
                    continue
                rows_differ = _rows_differ(existing, source_row, exclude=("id", "order_id"))
                if _source_is_newer(source_row.created_at, existing.created_at) and rows_differ:
                    stats.updated += 1
                    if not context.options.dry_run:
                        _assign_columns(existing, source_row, exclude=("id", "order_id"))
                elif rows_differ:
                    stats.skipped += 1
                    _warn_or_raise(
                        context,
                        stats,
                        f"TradeMetric conflict for source order_id={source_row.order_id}: target row differs and is newer",
                    )
                else:
                    stats.skipped += 1
            if not context.options.dry_run:
                context.target_session.commit()
        return stats


class CandlesMigrator(BaseTableMigrator):
    table_name: PrimaryTableName = "candles"
    model = Candle

    def run(self, context: MigrationContext) -> TableStats:
        stats = self.plan(context)
        target_missing = self.table_name in context.missing_target_tables

        for batch in iter_rows_by_id(context.source_session, Candle, context.options.batch_size):
            for source_row in batch:
                target_row = None
                if not target_missing:
                    target_row = context.target_session.scalar(
                        select(Candle).where(
                            Candle.market == source_row.market,
                            Candle.timeframe == source_row.timeframe,
                            Candle.candle_time_utc == source_row.candle_time_utc,
                        )
                    )
                if target_row is None:
                    stats.inserted += 1
                    if not context.options.dry_run:
                        context.target_session.add(Candle(**_payload_from_row(source_row, exclude=("id",))))
                elif _rows_differ(
                    target_row,
                    source_row,
                    exclude=("id", "market", "timeframe", "candle_time_utc"),
                ):
                    stats.updated += 1
                    if not context.options.dry_run:
                        _assign_columns(
                            target_row,
                            source_row,
                            exclude=("id", "market", "timeframe", "candle_time_utc"),
                        )
                else:
                    stats.skipped += 1
            if not context.options.dry_run:
                context.target_session.commit()
        return stats


TABLE_MIGRATORS: dict[PrimaryTableName, BaseTableMigrator] = {
    "bot_config": BotConfigMigrator(),
    "timeframe_config": TimeframeConfigMigrator(),
    "orders": OrdersMigrator(),
    "order_attempts": OrderAttemptsMigrator(),
    "fills": FillsMigrator(),
    "trade_metrics": TradeMetricsMigrator(),
    "candles": CandlesMigrator(),
}


class MigrationService:
    def run(self, options: MigrationOptions) -> MigrationSummary:
        source_runtime = build_runtime(options.source_url)
        target_runtime = build_runtime(options.target_url)
        summary = MigrationSummary(options=options)

        try:
            if options.bootstrap_target and not options.dry_run:
                bootstrap_target_database(target_runtime)

            source_tables = list_tables(source_runtime)
            target_tables = list_tables(target_runtime)
            logger.info(
                "migration_start dry_run=%s tables=%s batch_size=%s bootstrap_target=%s copy_snapshot_tables=%s",
                options.dry_run,
                ",".join(options.tables),
                options.batch_size,
                options.bootstrap_target,
                options.copy_snapshot_tables,
            )

            with source_runtime.create_session() as source_session, target_runtime.create_session() as target_session:
                context = MigrationContext(
                    options=options,
                    source_session=source_session,
                    target_session=target_session,
                    order_id_map=OrderIdMap(),
                    missing_target_tables={table_name for table_name in options.tables if table_name not in target_tables},
                )

                if "orders" not in options.tables and any(
                    name in options.tables for name in ("order_attempts", "fills", "trade_metrics")
                ):
                    self._hydrate_order_id_map(context)

                for table_name in options.tables:
                    if table_name not in source_tables:
                        stats = TableStats(table_name=table_name)
                        message = f"Source table '{table_name}' is missing"
                        if options.strict:
                            raise ValueError(message)
                        stats.warnings.append(message)
                        summary.add(stats)
                        continue
                    if table_name not in target_tables and not options.bootstrap_target and not options.dry_run:
                        stats = TableStats(table_name=table_name)
                        message = f"Target table '{table_name}' is missing and bootstrap_target is disabled"
                        if options.strict:
                            raise ValueError(message)
                        stats.warnings.append(message)
                        summary.add(stats)
                        continue

                    migrator = TABLE_MIGRATORS[table_name]
                    stats = migrator.run(context)
                    if table_name in context.missing_target_tables:
                        stats.warnings.append(
                            "Target table is missing; dry-run treated it as an empty table."
                        )
                    summary.add(stats)

                if options.copy_snapshot_tables:
                    synchronizer = SnapshotTableSynchronizer()
                    missing_snapshot_tables = {
                        table_name
                        for table_name in ("positions", "paper_wallet", "daily_equity")
                        if table_name not in target_tables
                    }
                    for stats in synchronizer.run(
                        source_session,
                        target_session,
                        dry_run=options.dry_run,
                        missing_target_tables=missing_snapshot_tables,
                    ):
                        if stats.table_name in missing_snapshot_tables:
                            stats.warnings.append(
                                "Target table is missing; dry-run treated it as an empty table."
                            )
                        summary.add(stats)

            logger.info("migration_done mapped_orders=%s", len(context.order_id_map))
            return summary
        finally:
            dispose_runtime(source_runtime)
            dispose_runtime(target_runtime)

    @staticmethod
    def _hydrate_order_id_map(context: MigrationContext) -> None:
        if "orders" in context.missing_target_tables:
            return
        for batch in iter_rows_by_id(context.source_session, Order, context.options.batch_size):
            for source_row in batch:
                target_id = context.target_session.scalar(
                    select(Order.id).where(Order.client_order_id == source_row.client_order_id)
                )
                if target_id is not None:
                    context.order_id_map.remember(source_row.id, target_id)
