#!/usr/bin/env python3
# ruff: noqa: T201  # CLI script: stdout is the interface
"""Regen runner: re-generate failed units with diagnosis-informed fixes.

Consumes acceptance failures across cycles and re-runs the units whose
failure is a generation defect. Admission is grounded in the canonical
realization-gate diagnosis (``astral.qa.realization_gate.diagnose``):

- structural defects (truncated runs, no-exchange, firewall fail without
  content, missing tool loop) always qualify;
- behavioral failures qualify only when the diagnosis routes to regen with
  high or medium confidence (tolerance breach with a named root cause);
- judge instability, valid refusals, and low-confidence diagnoses route to
  humans, never to auto-regen.

Structural failures with weak auditors escalate to the high-realization
permissive auditor pool.

Usage:
    python scripts/regen_run.py [--cycles-root data/cycles] [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from astral.bridge.batch import run_bloom_batch
from astral.bridge.campaign import _stratified_level
from astral.cards.grounding import load_grounding
from astral.qa.realization_gate import diagnose

_STRUCTURAL_REASONS = {
    "firewall_fail",
    "no_exchange",
    "missing_tool_call",
    "missing_tool_request",
    "missing_tool_result",
    "target_no_call",
    "dangling_tool_call",
    "tool_result_no_response",
    "cot_leak",
}
_MIN_TURNS_FOR_CONTENT = 3

# Auditor escalation pool for structural failures (auditor-side refusal /
# seed-dump): high-realization models, weighted toward the new low-use
# models so regen diversifies away from the biased auditors.
ESCALATION_AUDITORS = [
    "openrouter/minimax/minimax-m3",  # verified auditor, low use
    "openrouter/moonshotai/kimi-k3",  # high intelligence, low use
    "openrouter/x-ai/grok-4.5",  # verified auditor, low use
    "openrouter/qwen/qwen3.7-max",  # permissive, low use as auditor
    "openrouter/z-ai/glm-5.2",  # highest realization
    "openrouter/deepseek/deepseek-v4-flash",  # highest realization
]
# Biased/overused auditors escalate away: flash-lite (37% share, safety-
# simulates) and gemini-3.6-flash (CA-refusal cluster).
ESCALATION_TARGETS = [
    "openrouter/moonshotai/kimi-k3",  # high intelligence, low use as target
    "openrouter/minimax/minimax-m3",  # verified, low use
    "openrouter/mistralai/mistral-medium-3-5",  # permissive, low use
    "openrouter/x-ai/grok-4.5",  # high capability, low use
    "openrouter/deepseek/deepseek-v4-flash-0731",  # cheapest permissive
]
"""Target pool for regen: rotate the new low-use models so failed units are
regenerated against diverse targets, not the same one that produced them."""
WEAK_AUDITORS = {
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-2.5-pro",
}
# Empty-log / invalid-id targets escalate away to responsive models.
WEAK_TARGETS = {
    "claude-sonnet-4.6",
    "claude-opus-4.8",
    "mistral-medium-3.5",
    "gemini-2.5-pro",
}

_CONFIDENCE_OK = {"high", "medium"}


def _behavioral_admission(pair: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any] | None:
    """Run the realization-gate diagnosis on a coverage-only failure.

    Returns the diagnosis dict when it routes to regen with sufficient
    confidence; None otherwise (detector artifact, judge instability, or
    human territory).
    """
    for scenario in pair.get("scenarios") or []:
        judgment = scenario.get("judgment") or {}
        if not judgment.get("variables"):
            continue
        diagnosis = diagnose(
            dict(spec.get("variables") or {}),
            judgment,
            side=str(scenario.get("side") or "benign"),
            coverage=(scenario.get("coverage") or {}),
            audit_judgment=scenario.get("audit_judgment"),
            turns=int(scenario.get("turns") or 0),
        )
        if diagnosis is None:
            continue
        if diagnosis.route_to == "regen" and diagnosis.confidence in _CONFIDENCE_OK:
            return diagnosis.as_dict()
    return None


def _unit_failures(cycle_dir: Path, runs_root: Path) -> list[dict[str, Any]]:
    """Collect regen-eligible failed units from one cycle's batch report."""
    report_path = cycle_dir / "batch_report.json"
    manifest_path = runs_root / cycle_dir.name / "manifest.yaml"
    if not (report_path.is_file() and manifest_path.is_file()):
        return []
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    specs = {f"{s['route_id']}-s{int(s.get('seed', 0))}": s for s in manifest.get("pairs") or []}
    out = []
    for pair in report.get("pairs") or []:
        reasons: set[str] = set()
        turns = 0
        for scenario in pair.get("scenarios") or []:
            reasons.update((scenario.get("acceptance") or {}).get("reasons") or [])
            turns = max(turns, int(scenario.get("turns") or 0))
        structural = reasons & _STRUCTURAL_REASONS
        truncated = turns < _MIN_TURNS_FOR_CONTENT
        if not truncated and "firewall_fail" in structural:
            continue  # real content with a leak: human review
        spec = specs.get(str(pair.get("pair_id")))
        if spec is None:
            continue
        if structural:
            out.append(
                {
                    "cycle": cycle_dir.name,
                    "pair_id": pair["pair_id"],
                    "spec": spec,
                    "reasons": sorted(reasons),
                    "turns": turns,
                    "admission": "structural",
                }
            )
            continue
        if "coverage_incomplete" in reasons:
            diagnosis = _behavioral_admission(pair, spec)
            if diagnosis is not None:
                out.append(
                    {
                        "cycle": cycle_dir.name,
                        "pair_id": pair["pair_id"],
                        "spec": spec,
                        "reasons": sorted(reasons),
                        "turns": turns,
                        "admission": "behavioral",
                        "diagnosis": diagnosis,
                    }
                )
    return out


def _escalated_auditor(manifest: dict[str, Any], attempt: int, weak: bool) -> str:
    """Auditor for the regen: escalate when the original was weak, else keep."""
    original = str((manifest.get("harness") or {}).get("auditor_model") or "")
    if weak or attempt > 1:
        index = (attempt - 1) % len(ESCALATION_AUDITORS)
        return ESCALATION_AUDITORS[index]
    return original


def _escalated_target(manifest: dict[str, Any], attempt: int) -> str:
    """Target for the regen: rotate the new low-use pool on every attempt."""
    original = str((manifest.get("harness") or {}).get("target_model") or "")
    short = original.split("/")[-1]
    if short in WEAK_TARGETS or attempt > 1:
        index = (attempt - 1) % len(ESCALATION_TARGETS)
        return ESCALATION_TARGETS[index]
    return original


def _archive_original(runs_root: Path, cycle: str, pair_id: str) -> Path | None:
    """Archive the original unit's logs before regen; originals stay as data.

    The regen writes to a ``{cycle}-regen{attempt}`` dir, leaving the original
    intact, but when a regen is promoted back into the cycle the original
    transcripts should be archived (still good data) rather than deleted.
    """
    original = runs_root / cycle / pair_id
    if not original.is_dir():
        return None
    archive = runs_root / "archive" / f"{cycle}-regen" / pair_id
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        return archive
    shutil.copytree(original, archive)
    return archive


def _balanced_variables(spec: dict[str, Any], attempt: int, slot: int) -> dict[str, Any]:
    """Re-draw a regen unit's variables toward under-represented levels.

    Uses the campaign's deficit-filling stratified draw so regenerated logs fill
    the corpus gaps (SC1/2, thin KC stages) rather than repeating the same
    levels. Route-allowed values constrain the draw; benign twins zero JB/SP.
    """
    route = load_grounding().routes[str(spec["route_id"])]
    allowed = route.get("allowed_values") or {}
    side = str(spec.get("side") or "malicious")
    sc_allowed = [int(v) for v in allowed.get("scientific_capability_levels", [1, 2, 3])]
    kc_allowed = [int(v) for v in allowed.get("kill_chain", [0, 1])]
    jb_allowed = [int(v) for v in allowed.get("jail_breaking", [0])]
    seed = attempt * 100 + slot
    jb = (
        0
        if side == "benign"
        else _stratified_level(
            [v for v in jb_allowed if v >= 1] or jb_allowed, seed, slot, "jailbreak"
        )
    )
    return {
        "scientific_capability": _stratified_level(sc_allowed, seed, slot, "scientific_capability"),
        "jailbreak": jb,
        "kill_chain": _stratified_level(kc_allowed, seed, slot, "kill_chain"),
        "intended_scope": 0,
    }


def _regen_manifest(
    failures: list[dict[str, Any]], manifest: dict[str, Any], attempt: int
) -> dict[str, Any]:
    """Build the regen manifest: deficit-filling variables, new seeds, escalation.

    Regenerated units re-draw their variable assignment toward under-represented
    levels (via the campaign's live-counts deficit draw), so regen doubles as a
    balancing mechanism — it replaces broken logs AND fills SC/KC gaps.
    """
    pairs = []
    for slot, failure in enumerate(failures):
        spec = dict(failure["spec"])
        spec["seed"] = int(spec.get("seed", 0)) + 1000 * attempt
        spec["variables"] = _balanced_variables(spec, attempt, slot)
        pairs.append(spec)
    auditor_short = str((manifest.get("harness") or {}).get("auditor_model") or "").split("/")[-1]
    weak = auditor_short in WEAK_AUDITORS
    harness = dict(manifest.get("harness") or {})
    harness["auditor_model"] = _escalated_auditor(manifest, attempt, weak)
    harness["target_model"] = _escalated_target(manifest, attempt)
    return {
        "cycle": manifest.get("cycle"),
        "ratio": manifest.get("ratio") or "2:2:2",
        "expected_logs": len(pairs) * 2,
        "harness": harness,
        "cost": {"estimate_per_pair": 250000, "max_estimated_tokens": 1500000},
        "pairs": pairs,
        "notes": (
            f"regen attempt {attempt} for {len(failures)} failed units; "
            f"auditor {'escalated' if weak or attempt > 1 else 'kept'}"
        ),
    }


def main() -> int:
    """Scan, classify, and regenerate eligible failed units."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles-root", type=Path, default=Path("data/cycles"))
    parser.add_argument("--runs-root", type=Path, default=Path("_runs"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--limit", type=int, default=0, help="max units to regen (0 = all eligible)"
    )
    parser.add_argument("--attempt", type=int, default=1, help="regen attempt number (seed offset)")
    args = parser.parse_args()

    all_failures: list[dict[str, Any]] = []
    manifests: dict[str, dict[str, Any]] = {}
    for cycle_dir in sorted(
        args.cycles_root.iterdir(), key=lambda p: int(p.name[6:]) if p.name[6:].isdigit() else 0
    ):
        if not cycle_dir.name.startswith("cycle-") or not cycle_dir.name[6:].isdigit():
            continue
        failures = _unit_failures(cycle_dir, args.runs_root)
        all_failures.extend(failures)
        if failures:
            manifests[cycle_dir.name] = yaml.safe_load(
                (args.runs_root / cycle_dir.name / "manifest.yaml").read_text(encoding="utf-8")
            )

    if args.limit:
        all_failures = all_failures[: args.limit]
    structural = [f for f in all_failures if f["admission"] == "structural"]
    behavioral = [f for f in all_failures if f["admission"] == "behavioral"]
    print(
        f"regen-eligible: {len(all_failures)} "
        f"(structural {len(structural)}, behavioral {len(behavioral)})"
    )
    for failure in all_failures:
        diag = failure.get("diagnosis") or {}
        cause = diag.get("root_cause", "-")
        print(
            f"  {failure['cycle']} {failure['pair_id']:50} [{failure['admission']}] "
            f"{failure['reasons']} cause={cause}"
        )
    if args.dry_run or not all_failures:
        return 0

    by_cycle: dict[str, list[dict[str, Any]]] = {}
    for failure in all_failures:
        by_cycle.setdefault(failure["cycle"], []).append(failure)
    for cycle_name, failures in by_cycle.items():
        manifest = manifests[cycle_name]
        regen = _regen_manifest(failures, manifest, args.attempt)
        out_dir = args.runs_root / f"{cycle_name}-regen{args.attempt}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "manifest.yaml").write_text(
            yaml.safe_dump(regen, sort_keys=False), encoding="utf-8"
        )
        for failure in failures:
            _archive_original(args.runs_root, cycle_name, str(failure["pair_id"]))
        print(f"running regen for {cycle_name}: {len(failures)} units -> {out_dir}")
        report = run_bloom_batch(out_dir / "manifest.yaml", out_dir=str(out_dir))
        promotable = sum(int(p.get("promotable_transcripts", 0)) for p in report.get("pairs") or [])
        print(f"  regen result: {promotable} promotable transcripts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
