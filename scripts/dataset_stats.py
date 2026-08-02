#!/usr/bin/env python3
# ruff: noqa: T201  # CLI script: stdout is the interface
"""Dataset variable-representation statistics for the corpus.

Computes per-variable level distributions overall, by side (benign vs
malicious), and by family (CA vs BD vs RB) so representation gaps are visible.
Output is a table plus an optional JSON report.

Usage:
    python scripts/dataset_stats.py [--cycles-root data/cycles] [--json report.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

KEYS = {"sc": "SC", "jb": "JB", "kc": "KC", "sp": "SP"}
CUTS = ("overall", "benign", "malicious", "ca", "bd", "rb")


def compute(cycles_root: Path) -> dict[str, dict[str, Counter[int]]]:
    """Accumulate variable-level counters across all cycle transcripts."""
    rows: dict[str, dict[str, Counter[int]]] = {
        v: {cut: Counter() for cut in CUTS} for v in KEYS.values()
    }
    for cycle_dir in sorted(
        cycles_root.iterdir(), key=lambda p: int(p.name[6:]) if p.name[6:].isdigit() else 0
    ):
        if not cycle_dir.name.startswith("cycle-") or not cycle_dir.name[6:].isdigit():
            continue
        transcripts_path = cycle_dir / "transcripts.json"
        if not transcripts_path.is_file():
            continue
        entries = json.loads(transcripts_path.read_text(encoding="utf-8")).get("transcripts") or []
        for entry in entries:
            side = str(entry.get("side") or "benign")
            family = str(entry.get("route_id") or "").split(".")[0]
            variables = entry.get("variables") or {}
            for short, var in KEYS.items():
                value = variables.get(short)
                if isinstance(value, list):
                    value = max(value) if value else 0
                if value is None:
                    continue
                level = int(value)
                rows[var]["overall"][level] += 1
                rows[var][side][level] += 1
                if family in ("ca", "bd", "rb"):
                    rows[var][family][level] += 1
    return rows


def _dist(counter: Counter[int], total: int) -> str:
    """Format a level distribution as 'level:count (pct)'."""
    return "  ".join(
        f"{level}:{counter.get(level, 0)} ({counter.get(level, 0) / max(total, 1):.0%})"
        for level in sorted(counter)
    )


VAR_MAP = {"scientific_capability": "SC", "jailbreak": "JB", "kill_chain": "KC", "scope": "SP"}
TOLERANCE = {"SC": 1, "JB": 1, "KC": 1, "SP": 2}


def _count_scenario_deltas(
    deltas: dict[str, dict[str, Counter[int]]],
    scenario: dict[str, Any],
    assigned_vars: dict[str, Any],
    spec: dict[str, Any],
) -> bool:
    """Accumulate one scenario's deltas; return True when it breaches tolerance."""
    side = str(scenario.get("side") or "benign")
    assigned = (
        {**assigned_vars, "intended_scope": 0, "jailbreak": 0}
        if side == "benign"
        else assigned_vars
    )
    family = str(spec.get("route_id") or "").split(".")[0]
    judged = (scenario.get("judgment") or {}).get("variables") or {}
    breach = False
    for judged_var, var in VAR_MAP.items():
        block = judged.get(judged_var) or {}
        choice = block.get("choice")
        if isinstance(choice, list):
            choice = max(choice) if choice else 0
        if choice is None:
            continue
        key = "intended_scope" if judged_var == "scope" else judged_var
        target = assigned.get(key)
        if target is None:
            continue
        delta = abs(int(choice) - int(target))
        deltas[var]["overall"][delta] += 1
        deltas[var][side][delta] += 1
        if family in ("ca", "bd", "rb"):
            deltas[var][family][delta] += 1
        if delta > TOLERANCE[var]:
            breach = True
    return breach


def compute_deltas(cycles_root: Path) -> dict[str, Any]:
    """Realization error magnitude per variable: |judged - assigned| with tolerance.

    Returns delta counters per variable per cut plus the regen surface
    (fraction of sides breaching tolerance on any variable).
    """
    deltas: dict[str, dict[str, Counter[int]]] = {
        v: {cut: Counter() for cut in CUTS} for v in VAR_MAP.values()
    }
    breach = within = 0
    for cycle_dir in sorted(
        cycles_root.iterdir(), key=lambda p: int(p.name[6:]) if p.name[6:].isdigit() else 0
    ):
        if not cycle_dir.name.startswith("cycle-") or not cycle_dir.name[6:].isdigit():
            continue
        report_path = cycle_dir / "batch_report.json"
        manifest_path = Path("_runs") / cycle_dir.name / "manifest.yaml"
        if not (report_path.is_file() and manifest_path.is_file()):
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        specs = {
            f"{s['route_id']}-s{int(s.get('seed', 0))}": s for s in manifest.get("pairs") or []
        }
        for pair in report.get("pairs") or []:
            spec = specs.get(str(pair.get("pair_id"))) or {}
            assigned_vars = dict(spec.get("variables") or {})
            for scenario in pair.get("scenarios") or []:
                breach_flag = _count_scenario_deltas(deltas, scenario, assigned_vars, spec)
                if breach_flag:
                    breach += 1
                else:
                    within += 1
    return {"deltas": deltas, "within": within, "breach": breach}


def print_delta_section(deltas: dict[str, Any]) -> None:
    """Print the realization-error table with exact rate, MAE, and breach rate."""
    counts = deltas["deltas"]
    total = deltas["within"] + deltas["breach"]
    print(
        f"realization (sides scored: {total} | within tolerance: {deltas['within']} "
        f"| regen surface: {deltas['breach']} ({deltas['breach'] / max(total, 1):.0%}))\n"
    )
    for var in ("SC", "JB", "KC", "SP"):
        print(f"=== {var} (tolerance {TOLERANCE[var]}) ===")
        for cut in CUTS:
            counter = counts[var][cut]
            subtotal = sum(counter.values())
            if not subtotal:
                continue
            exact = counter.get(0, 0) / subtotal
            mae = sum(k * v for k, v in counter.items()) / subtotal
            breach = sum(v for k, v in counter.items() if k > TOLERANCE[var]) / subtotal
            dist = "  ".join(f"Δ{k}:{counter.get(k, 0)}" for k in sorted(counter))
            print(
                f"  {cut:10} n={subtotal:4} exact={exact:.0%} MAE={mae:.2f} "
                f"breach={breach:.0%}  {dist}"
            )
        print()


def main() -> int:
    """Print the representation table and optionally write JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles-root", type=Path, default=Path("data/cycles"))
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    rows = compute(args.cycles_root)
    total = sum(rows["SC"]["overall"].values())
    print_delta_section(compute_deltas(args.cycles_root))
    print(f"transcripts: {total}\n")
    report: dict[str, Any] = {"transcripts": total, "variables": {}}
    for var in ("SC", "JB", "KC", "SP"):
        print(f"=== {var} ===")
        report["variables"][var] = {}
        for cut in CUTS:
            counter = rows[var][cut]
            subtotal = sum(counter.values())
            print(f"  {cut:10} n={subtotal:4}  {_dist(counter, subtotal)}")
            report["variables"][var][cut] = dict(sorted(counter.items()))
        print()
    if args.json:
        args.json.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
