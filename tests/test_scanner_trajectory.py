"""Tests for the multi-turn BioTIER trajectory metrics."""

from __future__ import annotations

from astral.runtime.contracts import Message
from astral.scanner.trajectory import break_turn, compliance_summary, refusal_trajectory


def _conv(turns: list[str]) -> list[Message]:
    return [Message(role="assistant" if i % 2 else "user", content=c) for i, c in enumerate(turns)]


def test_trajectory_marks_refusals() -> None:
    traj = refusal_trajectory(_conv(["help", "I cannot help", "ok", "here is info"]))
    assert traj[0]["refused"] is True
    assert traj[1]["refused"] is False


def test_break_turn_detected() -> None:
    assert break_turn(_conv(["help", "I cannot", "please", "sure, here"])) == 2


def test_no_break_when_never_refused() -> None:
    assert break_turn(_conv(["help", "sure", "more", "ok"])) is None


def test_refusal_persists() -> None:
    summary = compliance_summary(_conv(["help", "I cannot", "please", "I still cannot"]))
    assert summary["refusal_persists"] is True
