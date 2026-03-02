from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PrimaryTableName = Literal[
    "bot_config",
    "timeframe_config",
    "orders",
    "fills",
    "trade_metrics",
    "candles",
]

SnapshotTableName = Literal["positions", "paper_wallet", "daily_equity"]

DEFAULT_TABLES: tuple[PrimaryTableName, ...] = (
    "bot_config",
    "timeframe_config",
    "orders",
    "fills",
    "trade_metrics",
    "candles",
)

PRIMARY_TABLES = frozenset(DEFAULT_TABLES)
SNAPSHOT_TABLES = frozenset({"positions", "paper_wallet", "daily_equity"})


@dataclass(frozen=True)
class MigrationOptions:
    source_url: str
    target_url: str
    tables: tuple[PrimaryTableName, ...] = DEFAULT_TABLES
    batch_size: int = 1000
    dry_run: bool = False
    bootstrap_target: bool = True
    strict: bool = False
    copy_snapshot_tables: bool = False
    config_strategy: Literal["target_wins", "source_wins"] = "target_wins"


@dataclass
class TableStats:
    table_name: str
    source_rows: int = 0
    target_rows: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class MigrationSummary:
    options: MigrationOptions
    table_stats: list[TableStats] = field(default_factory=list)

    def add(self, stats: TableStats) -> None:
        self.table_stats.append(stats)
