from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OrderIdMap:
    _source_to_target: dict[int, int] = field(default_factory=dict)

    def remember(self, source_order_id: int, target_order_id: int) -> None:
        self._source_to_target[int(source_order_id)] = int(target_order_id)

    def resolve(self, source_order_id: int) -> int | None:
        return self._source_to_target.get(int(source_order_id))

    def __len__(self) -> int:
        return len(self._source_to_target)
