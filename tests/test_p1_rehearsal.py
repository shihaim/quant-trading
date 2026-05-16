from __future__ import annotations

import sys

from trader.app import p1_rehearsal


class _ConfigRepoStub:
    def __init__(self, owner_user_id: int = 9):
        self.owner_user_id = owner_user_id
        self.resolve_calls = 0

    def resolve_owner_user_id(self) -> int:
        self.resolve_calls += 1
        return self.owner_user_id


def test_parse_args_accepts_explicit_user_id(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["p1_rehearsal", "--scenario", "smoke", "--user-id", "7"],
    )

    args = p1_rehearsal.parse_args()

    assert args.user_id == 7


def test_rehearsal_user_id_prefers_explicit_value():
    config_repo = _ConfigRepoStub(owner_user_id=9)

    user_id = p1_rehearsal._resolve_rehearsal_user_id(config_repo, explicit_user_id=7)

    assert user_id == 7
    assert config_repo.resolve_calls == 0


def test_rehearsal_user_id_falls_back_to_legacy_owner_when_omitted():
    config_repo = _ConfigRepoStub(owner_user_id=9)

    user_id = p1_rehearsal._resolve_rehearsal_user_id(config_repo, explicit_user_id=None)

    assert user_id == 9
    assert config_repo.resolve_calls == 1
