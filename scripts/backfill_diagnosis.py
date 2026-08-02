#!/usr/bin/env python3
# ruff: noqa: T201  # CLI script: stdout is the interface
"""Re-diagnosis backfill: populate the diagnosis field on older cycles.

Runs the realization-gate diagnosis over every judged side that lacks a
``diagnosis`` record, using the existing judgments, coverage reports, audit
judgments, and visible transcripts. Fully deterministic — no model calls.

Usage:
    python scripts/backfill_diagnosis.py [--cycles-root data/cycles] [--runs-root _runs]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from astral.qa.realization_gate import diagnose
from astral.runtime.contracts import Message


def _card_variables(spec: dict[str, Any], side: str) -> dict[str, Any]:
    """Assigned variable levels for one side from the manifest spec."""
    variables = dict(spec.get("variables") or {})
    if side == "benign":
        variables["intended_scope"] = 0
        variables["jailbreak"] = 0
    return variables


def _load_messages(side_dir: Path) -> list[Message]:
    """Load the visible transcript for cited excerpts."""
    path = side_dir / "visible.jsonl"
    if not path.is_file():
        return []
    return [
        Message.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def backfill_cycle(cycle_dir: Path, runs_root: Path) -> dict[str, int]:
    """Write diagnoses for every un-diagnosed side in one cycle."""
    report_path = cycle_dir / "batch_report.json"
    manifest_path = runs_root / cycle_dir.name / "manifest.yaml"
    if not (report_path.is_file() and manifest_path.is_file()):
        return {"diagnosed": 0, "skipped": 0}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    specs = {f"{s['route_id']}-s{int(s.get('seed', 0))}": s for s in manifest.get("pairs") or []}
    diagnosed = skipped = 0
    for pair in report.get("pairs") or []:
        spec = specs.get(str(pair.get("pair_id")))
        if spec is None:
            continue
        for scenario in pair.get("scenarios") or []:
            if scenario.get("diagnosis") or not scenario.get("judgment"):
                skipped += 1
                continue
            side = str(scenario.get("side") or "benign")
            side_dir = runs_root / cycle_dir.name / str(pair.get("pair_id")) / side
            messages = _load_messages(side_dir)
            diagnosis = diagnose(
                _card_variables(spec, side),
                scenario.get("judgment") or {},
                side=side,
                coverage=scenario.get("coverage"),
                audit_judgment=scenario.get("audit_judgment"),
                turns=int(scenario.get("turns") or 0),
                messages=messages,
            )
            if diagnosis is None:
                skipped += 1
                continue
            record = diagnosis.as_dict()
            scenario["diagnosis"] = record
            run_path = side_dir / "run.json"
            if run_path.is_file():
                run = json.loads(run_path.read_text(encoding="utf-8"))
                run["diagnosis"] = record
                run_path.write_text(
                    json.dumps(run, indent=1, sort_keys=True) + "\n", encoding="utf-8"
                )
            diagnosed += 1
    report_path.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {"diagnosed": diagnosed, "skipped": skipped}


def main() -> int:
    """Backfill diagnoses across completed cycles."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles-root", type=Path, default=Path("data/cycles"))
    parser.add_argument("--runs-root", type=Path, default=Path("_runs"))
    args = parser.parse_args()

    totals = {"diagnosed": 0, "skipped": 0}
    for cycle_dir in sorted(
        args.cycles_root.iterdir(), key=lambda p: int(p.name[6:]) if p.name[6:].isdigit() else 0
    ):
        if not cycle_dir.name.startswith("cycle-") or not cycle_dir.name[6:].isdigit():
            continue
        result = backfill_cycle(cycle_dir, args.runs_root)
        if result["diagnosed"]:
            print(f"{cycle_dir.name}: diagnosed {result['diagnosed']}, skipped {result['skipped']}")
        totals["diagnosed"] += result["diagnosed"]
        totals["skipped"] += result["skipped"]
    print(f"TOTAL: diagnosed {totals['diagnosed']}, skipped {totals['skipped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
