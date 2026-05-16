from __future__ import annotations

import sys

from trader.app import p1_rehearsal


def test_parse_args_accepts_explicit_user_id(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["p1_rehearsal", "--scenario", "smoke", "--user-id", "7"],
    )

    args = p1_rehearsal.parse_args()

    assert args.user_id == 7


def test_rehearsal_user_id_prefers_explicit_value():
    user_id = p1_rehearsal._resolve_rehearsal_user_id(explicit_user_id=7)

    assert user_id == 7


def test_rehearsal_user_id_requires_explicit_value_in_paper(monkeypatch):
    monkeypatch.setattr(p1_rehearsal.settings, "trade_mode", "PAPER")

    try:
        p1_rehearsal._resolve_rehearsal_user_id(explicit_user_id=None)
    except ValueError as exc:
        assert str(exc) == "user_id_required"
    else:
        raise AssertionError("expected user_id_required")


def test_rehearsal_user_id_requires_explicit_value_outside_paper(monkeypatch):
    monkeypatch.setattr(p1_rehearsal.settings, "trade_mode", "REAL")

    try:
        p1_rehearsal._resolve_rehearsal_user_id(explicit_user_id=None)
    except ValueError as exc:
        assert str(exc) == "user_id_required"
    else:
        raise AssertionError("expected user_id_required")
