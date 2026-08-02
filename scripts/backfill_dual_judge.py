#!/usr/bin/env python3
# ruff: noqa: T201  # CLI script: stdout is the interface
"""Backfill audit judgments on cycles that predate dual-grading.

Runs the rotating audit judge over every judged side that lacks an
``audit_judgment``, recomputes judge agreements, and writes the results back
into run.json and batch_report.json. After this pass, behavioral diagnoses
run with the judge-instability veto active across the whole corpus.

Usage:
    python scripts/backfill_dual_judge.py [--cycles-root data/cycles] [--limit N]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from astral import VariableAssignment, make_actor_card
from astral.bridge.rotation import cycle_audit_judge
from astral.qa.judge import judge_sample
from astral.runtime.contracts import Message


def _bare_model(model: str) -> str:
    """Strip provider prefixes for the judge chat call."""
    for prefix in ("openrouter/", "venice/"):
        if model.startswith(prefix):
            return model.removeprefix(prefix)
    return model


def _card_for(spec: dict[str, Any], side: str) -> Any:
    """Rebuild the actor card for one side."""
    variables = VariableAssignment(**(spec.get("variables") or {}))
    if side == "benign":
        variables = variables.model_copy(update={"intended_scope": 0, "jailbreak": 0})
    return make_actor_card(  # type: ignore[arg-type]
        side=side,
        route_id=str(spec["route_id"]),
        variables=variables,
        seed=int(spec.get("seed", 0)),
        include_biotool=bool(spec.get("tools", True)),
    )


def _audit_model(manifest: dict[str, Any], cycle: int, target: str) -> str:
    """The cycle's assigned audit judge, or the rotation default."""
    harness = manifest.get("harness") or {}
    if harness.get("audit_judge_model"):
        return str(harness["audit_judge_model"])
    return cycle_audit_judge(cycle - 1, target)


def _serialize(judgment: Any) -> dict[str, Any] | None:
    """Compact a Judgment for storage."""
    if judgment is None:
        return None
    return {
        "assistant_outcome": judgment.assistant_outcome,
        "assistant_outcome_rationale": judgment.assistant_outcome_rationale,
        "variables": {
            k: {
                "choice": v.choice,
                "confidence": v.confidence,
                "evidence_turns": v.evidence_turns,
                "rationale": v.rationale,
            }
            for k, v in judgment.variables.items()
        },
        "notes": judgment.notes,
        "model_error": judgment.model_error,
    }


def _agreement(
    judgment: dict[str, Any] | None, audit: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Outcome match and variable match rate between the two judgments."""
    if not judgment or not audit or audit.get("model_error"):
        return None
    shared = set(judgment.get("variables") or {}) & set(audit.get("variables") or {})
    matches = sum(
        1
        for name in shared
        if (judgment["variables"][name] or {}).get("choice")
        == (audit["variables"][name] or {}).get("choice")
    )
    return {
        "outcome_match": judgment.get("assistant_outcome") == audit.get("assistant_outcome"),
        "variable_match_rate": (matches / len(shared)) if shared else None,
        "variables_compared": len(shared),
    }


def backfill_cycle(cycle_dir: Path, runs_root: Path) -> dict[str, int]:
    """Audit-judge every un-audited side in one cycle."""
    report_path = cycle_dir / "batch_report.json"
    manifest_path = runs_root / cycle_dir.name / "manifest.yaml"
    if not (report_path.is_file() and manifest_path.is_file()):
        return {"graded": 0, "errors": 0}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    harness = manifest.get("harness") or {}
    target = str(harness.get("target_model") or "")
    cycle_num = int(cycle_dir.name.split("-")[1])
    audit_model = _bare_model(_audit_model(manifest, cycle_num, target))
    specs = {f"{s['route_id']}-s{int(s.get('seed', 0))}": s for s in manifest.get("pairs") or []}
    graded = errors = 0
    for pair in report.get("pairs") or []:
        spec = specs.get(str(pair.get("pair_id")))
        if spec is None:
            continue
        for scenario in pair.get("scenarios") or []:
            if scenario.get("audit_judgment") or not scenario.get("judgment"):
                continue
            side = str(scenario.get("side") or "benign")
            side_dir = runs_root / cycle_dir.name / str(pair.get("pair_id")) / side
            visible_path = side_dir / "visible.jsonl"
            if not visible_path.is_file():
                continue
            messages = [
                Message.model_validate(json.loads(line))
                for line in visible_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            card = _card_for(spec, side)
            audit_judgment = None
            with contextlib.suppress(Exception):
                audit_judgment = judge_sample(card, messages, model=audit_model)
            serialized = _serialize(audit_judgment)
            if serialized is None or serialized.get("model_error"):
                errors += 1
                continue
            scenario["audit_judgment"] = serialized
            scenario["judge_agreement"] = _agreement(scenario.get("judgment"), serialized)
            run_path = side_dir / "run.json"
            if run_path.is_file():
                run = json.loads(run_path.read_text(encoding="utf-8"))
                run["audit_judgment"] = serialized
                run["judge_agreement"] = scenario["judge_agreement"]
                run_path.write_text(
                    json.dumps(run, indent=1, sort_keys=True) + "\n", encoding="utf-8"
                )
            graded += 1
    report_path.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {"graded": graded, "errors": errors}


def main() -> int:
    """Backfill audit judgments across completed cycles."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles-root", type=Path, default=Path("data/cycles"))
    parser.add_argument("--runs-root", type=Path, default=Path("_runs"))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    total = {"graded": 0, "errors": 0}
    done = 0
    for cycle_dir in sorted(
        args.cycles_root.iterdir(), key=lambda p: int(p.name[6:]) if p.name[6:].isdigit() else 0
    ):
        if not cycle_dir.name.startswith("cycle-") or not cycle_dir.name[6:].isdigit():
            continue
        report = (
            json.loads((cycle_dir / "batch_report.json").read_text(encoding="utf-8"))
            if (cycle_dir / "batch_report.json").is_file()
            else {}
        )
        needs = any(
            s.get("judgment") and not s.get("audit_judgment")
            for p in report.get("pairs") or []
            for s in p.get("scenarios") or []
        )
        if not needs:
            continue
        result = backfill_cycle(cycle_dir, args.runs_root)
        total["graded"] += result["graded"]
        total["errors"] += result["errors"]
        done += 1
        print(f"{cycle_dir.name}: graded {result['graded']}, errors {result['errors']}")
        if args.limit and done >= args.limit:
            break
    print(f"TOTAL: graded {total['graded']}, errors {total['errors']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
