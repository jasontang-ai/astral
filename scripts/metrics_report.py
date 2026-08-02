#!/usr/bin/env python3
"""Repository code metrics: radon gates, trend ratchet, JSON reports.

Dev tooling — not part of the ``astral`` runtime package. Collects
per-module complexity and maintainability over ``src/astral``, checks
project gates, and writes versioned JSON under ``data/metrics/``.

Run::

    .venv/bin/python scripts/metrics_report.py
    .venv/bin/python scripts/metrics_report.py --check
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from radon.complexity import cc_visit  # type: ignore[import-untyped]
from radon.metrics import mi_rank, mi_visit  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "astral"
OUT_DIR = ROOT / "data" / "metrics"
SCHEMA = "astral.metrics_report.v1"
CC_CAP = 10
MI_MIN_RANK = "A"


def _git_commit() -> str:
    """The short commit hash, or 'unknown' outside a git worktree."""
    try:
        return subprocess.run(
            ["/usr/bin/git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _module_metrics(path: Path) -> dict[str, Any]:
    """Metrics for one module."""
    text = path.read_text(encoding="utf-8")
    blocks = [
        {"name": b.name, "complexity": b.complexity, "lineno": b.lineno} for b in cc_visit(text)
    ]
    mi = mi_visit(text, True)
    return {
        "path": str(path.relative_to(ROOT)),
        "nonblank_lines": sum(1 for line in text.splitlines() if line.strip()),
        "functions": len(blocks),
        "cc_max": max((b["complexity"] for b in blocks), default=0),
        "cc_mean": round(sum(b["complexity"] for b in blocks) / len(blocks), 2) if blocks else 0,
        "mi": round(mi, 1),
        "mi_rank": mi_rank(mi),
        "blocks": blocks,
    }


def _totals(modules: list[dict[str, Any]]) -> tuple[int, float]:
    """Worst complexity and lowest maintainability across modules."""
    cc = max((m["cc_max"] for m in modules), default=0)
    mi = min((m["mi"] for m in modules), default=100.0)
    return cc, mi


def _trend(modules: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare current metrics against the previous report, if one exists."""
    latest = OUT_DIR / "latest.json"
    if not latest.is_file():
        return {"previous": None, "pass": True, "note": "no previous report"}
    previous = json.loads(latest.read_text(encoding="utf-8"))
    if previous.get("commit") == _git_commit():
        return {"previous": previous["commit"], "pass": True, "note": "same commit"}
    prev_cc, prev_mi = _totals(previous.get("modules", []))
    cur_cc, cur_mi = _totals(modules)
    justification = os.environ.get("ASTRAL_METRICS_JUSTIFY", "").strip()
    regressions = []
    if cur_cc > prev_cc:
        regressions.append(f"cc_max {prev_cc} -> {cur_cc}")
    if cur_mi < prev_mi:
        regressions.append(f"min_mi {prev_mi:.1f} -> {cur_mi:.1f}")
    return {
        "previous": previous.get("commit"),
        "cc_max": {"before": prev_cc, "after": cur_cc},
        "mi_min": {"before": prev_mi, "after": cur_mi},
        "regressions": regressions,
        "justification": justification or None,
        "pass": not regressions or bool(justification),
    }


def collect() -> dict[str, Any]:
    """Collect per-module metrics, gates, and the trend ratchet."""
    modules = [_module_metrics(path) for path in sorted(SOURCE.rglob("*.py"))]
    worst_blocks = _worst_blocks(modules)
    gates = _gates(modules)
    return {
        "schema": SCHEMA,
        "commit": _git_commit(),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "distribution": _distribution(worst_blocks),
        "modules": [{k: v for k, v in m.items() if k != "blocks"} for m in modules],
        "totals": {
            "modules": len(modules),
            "functions": sum(m["functions"] for m in modules),
            "nonblank_lines": sum(m["nonblank_lines"] for m in modules),
        },
        "worst_blocks": worst_blocks[:10],
        "gates": gates,
        "pass": all(g["pass"] for g in gates.values()),
    }


def _worst_blocks(modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """All function blocks with their module paths, most complex first."""
    blocks = [{**block, "path": module["path"]} for module in modules for block in module["blocks"]]
    return sorted(blocks, key=lambda b: b["complexity"], reverse=True)


def _distribution(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Share of blocks at rank A, as an informational composition metric."""
    rank_a = sum(1 for b in blocks if b["complexity"] <= 5)
    return {
        "rank_a_share": round(rank_a / len(blocks), 3) if blocks else 1.0,
        "blocks": len(blocks),
        "note": "Informational composition metric; gates remain cc_cap and mi_rank.",
    }


def _gates(modules: list[dict[str, Any]]) -> dict[str, Any]:
    """The project gates: complexity cap, maintainability rank, and trend."""
    return {
        "cc_cap": {"limit": CC_CAP, "pass": all(m["cc_max"] <= CC_CAP for m in modules)},
        "mi_rank": {
            "minimum": MI_MIN_RANK,
            "pass": all(m["mi_rank"] == MI_MIN_RANK for m in modules),
        },
        "trend": _trend(modules),
    }


def write_report(report: dict[str, Any]) -> Path:
    """Write the timestamped report and refresh latest.json."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = report["generated_at"].replace(":", "").replace("-", "")
    path = OUT_DIR / f"{report['commit']}-{stamp}.json"
    path.write_text(json.dumps(report, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def print_summary(report: dict[str, Any], path: Path) -> None:
    """Print the per-module table and gate results."""
    totals = report["totals"]
    print(
        f"commit {report['commit']} · {totals['modules']} modules · "
        f"{totals['functions']} functions · {totals['nonblank_lines']} nonblank lines"
    )
    for m in report["modules"]:
        row = f"  {m['path']:44s} {m['nonblank_lines']:4d} loc  cc_max {m['cc_max']:2d}  "
        print(row + f"mi {m['mi']:5.1f} [{m['mi_rank']}]")
    dist = report.get("distribution") or {}
    if dist:
        print(
            f"distribution: {dist['rank_a_share'] * 100:.0f}% of {dist['blocks']} blocks at rank A"
        )
    for name, gate in report["gates"].items():
        print(f"gate {name}: {'PASS' if gate['pass'] else 'FAIL'}")
    trend: dict[str, Any] = report["gates"].get("trend") or {}
    if trend.get("regressions"):
        print(f"  regressions: {', '.join(trend['regressions'])}")
    print(f"report: {path}")


def main() -> int:
    """Run the reporter; exit 1 when any gate fails."""
    check = "--check" in sys.argv
    report = collect()
    path = write_report(report)
    print_summary(report, path)
    return 0 if report["pass"] or not check else 1


if __name__ == "__main__":
    sys.exit(main())
