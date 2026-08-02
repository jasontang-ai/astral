#!/usr/bin/env python3
# ruff: noqa: T201  # CLI script: stdout is the interface
"""Build the human-review queue from expected-cost routing across cycles.

Runs the router over every completed cycle's sides and emits the ranked
human-review queue (highest expected cost-avoided first), the regen queue,
and campaign-level counts. This is the daily triage artifact for the human
review bottleneck.

Usage:
    python scripts/review_queue.py [--cycles-root data/cycles] [--out data/cycles/review_queue.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from astral.qa.routing_score import RegenSuccessModel, route_side


def _sides(cycle_dir: Path) -> list[dict[str, Any]]:
    """Flatten batch-report scenarios with card payloads for routing."""
    report_path = cycle_dir / "batch_report.json"
    if not report_path.is_file():
        return []
    report = json.loads(report_path.read_text(encoding="utf-8"))
    out = []
    for pair in report.get("pairs") or []:
        for scenario in pair.get("scenarios") or []:
            judgment = scenario.get("judgment") or {}
            variables = judgment.get("variables") or {}
            card = {
                "variables": {
                    "scientific_capability": (variables.get("scientific_capability") or {}).get(
                        "choice", 2
                    ),
                    "jailbreak": (variables.get("jailbreak") or {}).get("choice", 0),
                    "kill_chain": max((variables.get("kill_chain") or {}).get("choice", [0]) or [0])
                    if isinstance((variables.get("kill_chain") or {}).get("choice"), list)
                    else (variables.get("kill_chain") or {}).get("choice", 0),
                    "intended_scope": (variables.get("scope") or {}).get("choice", 0),
                },
                "agent": {},
            }
            out.append(
                {
                    "id": f"{pair.get('pair_id')}/{scenario.get('side')}",
                    "cycle": cycle_dir.name,
                    "card": card,
                    "judgment": judgment,
                    "judge_agreement": scenario.get("judge_agreement"),
                    "diagnosis": scenario.get("diagnosis"),
                    "promotable": scenario.get("promotable"),
                }
            )
    return out


def main() -> int:
    """Emit the ranked human-review and regen queues."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles-root", type=Path, default=Path("data/cycles"))
    parser.add_argument("--out", type=Path, default=Path("data/cycles/review_queue.json"))
    args = parser.parse_args()

    model = RegenSuccessModel()
    human_queue: list[dict[str, Any]] = []
    regen_queue: list[dict[str, Any]] = []
    counts: dict[str, int] = {"ship": 0, "regen": 0, "human_review": 0, "rejudge": 0}
    for cycle_dir in sorted(
        args.cycles_root.iterdir(), key=lambda p: int(p.name[6:]) if p.name[6:].isdigit() else 0
    ):
        if not cycle_dir.name.startswith("cycle-") or not cycle_dir.name[6:].isdigit():
            continue
        for side in _sides(cycle_dir):
            decision = route_side(
                side["card"],
                judgment=side["judgment"],
                judge_agreement=side["judge_agreement"],
                diagnosis=side["diagnosis"],
                success_model=model,
            )
            counts[decision.route] = counts.get(decision.route, 0) + 1
            record = {
                "id": side["id"],
                "cycle": side["cycle"],
                **decision.as_dict(),
            }
            if decision.route == "human_review":
                human_queue.append(record)
            elif decision.route == "regen":
                regen_queue.append(record)

    human_queue.sort(key=lambda r: -r["expected_costs"]["ship"])
    regen_queue.sort(key=lambda r: r["expected_costs"]["regen"])
    payload = {
        "schema": "astral.review_queue.v1",
        "counts": counts,
        "human_queue": human_queue,
        "regen_queue": regen_queue,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"routes: {counts}")
    print(f"human queue: {len(human_queue)} sides (top expected harm first)")
    for row in human_queue[:5]:
        print(f"  {row['id']:50} ship-cost {row['expected_costs']['ship']:>6.1f} {row['reasons']}")
    print(f"regen queue: {len(regen_queue)} sides")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
