"""Tests for the refusal benchmark surface."""

from __future__ import annotations

from astral.scanner.refusal import bench_refusal, refusal_run


def test_bench_refusal_defaults() -> None:
    # dry structure check — no live call
    assert callable(bench_refusal)
    assert callable(refusal_run)
