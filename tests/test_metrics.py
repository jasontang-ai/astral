"""Code-metric gates via the scripts/metrics_report tooling."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "metrics_report.py"


def _load_metrics():
    """Load scripts/metrics_report.py as a module (not part of the astral package)."""
    spec = importlib.util.spec_from_file_location("metrics_report", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["metrics_report"] = module
    spec.loader.exec_module(module)
    return module


def test_report_is_well_formed() -> None:
    metrics = _load_metrics()
    report = metrics.collect()
    assert report["schema"] == "astral.metrics_report.v1"
    assert report["totals"]["modules"] >= 1
    assert all("cc_max" in m and "mi_rank" in m for m in report["modules"])


def test_metrics_gates_pass() -> None:
    metrics = _load_metrics()
    report = metrics.collect()
    path = metrics.write_report(report)
    assert path.is_file()
    assert report["gates"]["cc_cap"]["pass"], [
        (b["path"], b["name"], b["complexity"]) for b in report["worst_blocks"][:3]
    ]
    assert report["gates"]["mi_rank"]["pass"], [
        (m["path"], m["mi"], m["mi_rank"]) for m in report["modules"] if m["mi_rank"] != "A"
    ]
    assert report["gates"]["trend"]["pass"], report["gates"]["trend"].get("regressions")


def test_print_summary_and_main_succeed(capsys: object, monkeypatch: object) -> None:
    metrics = _load_metrics()
    report = metrics.collect()
    path = metrics.write_report(report)
    metrics.print_summary(report, path)
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "gate cc_cap" in out
    assert "report:" in out

    monkeypatch.setattr("sys.argv", ["metrics_report"])  # type: ignore[attr-defined]
    assert metrics.main() == 0


def test_main_check_mode_uses_report_pass(monkeypatch: object) -> None:
    metrics = _load_metrics()
    monkeypatch.setattr("sys.argv", ["metrics_report", "--check"])  # type: ignore[attr-defined]
    assert metrics.main() == 0
    latest = Path("data/metrics/latest.json")
    if latest.is_file():
        payload = json.loads(latest.read_text(encoding="utf-8"))
        assert payload["schema"] == "astral.metrics_report.v1"
