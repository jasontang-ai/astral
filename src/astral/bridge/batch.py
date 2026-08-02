"""Manifest-driven Bloom batch runner.

Runs a list of card pairs through ``run_bloom_arm`` with per-pair failure
isolation, an estimated-token cost ceiling, and an atomic batch report. One
pair's failure never aborts the batch and never vanishes from the report.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import yaml

from astral import VariableAssignment, make_actor_card, make_actor_cards
from astral.bridge.pack import pack_cycle
from astral.bridge.run import BloomHarness, run_bloom_arm, run_bloom_single
from astral.runtime.contracts import DEFAULT_TURN_CAP

DEFAULT_ESTIMATE_PER_PAIR = 160_000


def _load_manifest(path: Path) -> dict[str, Any]:
    """Load a JSON or YAML batch manifest."""
    if path.suffix == ".json":
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def _unit_from_spec(spec: dict[str, Any]) -> tuple[str, Any, str]:
    """Compile one manifest unit into a pair or single and its run mode.

    Returns:
        A ``(unit_id, card_or_pair, mode)`` triple where mode is ``pair`` or
        ``single``. Benign-only RB routes and explicit ``side: benign`` units
        run as singles.
    """
    route_id = str(spec["route_id"])
    seed = int(spec.get("seed", 0))
    variables = spec.get("variables")
    assignment = VariableAssignment(**variables) if variables else None
    side = str(spec.get("side") or "").lower()
    family = route_id.split(".", 1)[0].lower()
    unit_id = f"{route_id}-s{seed}"
    include_biotool = bool(spec.get("tools", True))
    if side == "benign" or family == "rb":
        card = make_actor_card(
            side="benign",
            route_id=route_id,
            variables=assignment
            or VariableAssignment(
                scientific_capability=3, jailbreak=0, kill_chain=0, intended_scope=0
            ),
            seed=seed,
            include_biotool=include_biotool,
        )
        return unit_id, card, "single"
    pair = make_actor_cards(
        route_id=route_id,
        variables=assignment,
        seed=seed,
        include_biotool=include_biotool,
    )
    return unit_id, pair, "pair"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically via a temporary sibling file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _harness_from_manifest(harness: dict[str, Any]) -> BloomHarness:
    """Build a BloomHarness from a batch manifest harness block."""
    return BloomHarness(
        auditor=str(harness["auditor_model"]),
        target=str(harness["target_model"]),
        judge=harness.get("judge_model"),
        audit_judge=harness.get("audit_judge_model"),
        max_turns=int(harness.get("max_turns", DEFAULT_TURN_CAP // 2)),
        compaction=harness.get("compaction", False),
        system_message=harness.get("system_message"),
        fallback_models=harness.get("fallback_models"),
        reasoning_effort=harness.get("reasoning_effort", "high"),
    )


def _unit_status(scenarios: list[dict[str, Any]]) -> str:
    """Batch unit status from per-side promotion, not truncation alone."""
    statuses = {s["status"] for s in scenarios}
    if "error" in statuses:
        return "error"
    if scenarios and all(bool(s.get("promotable")) for s in scenarios):
        return "ok"
    return "incomplete"


def _result_from_summary(pair_id: str, summary: dict[str, Any], estimate: int) -> dict[str, Any]:
    """Build the durable per-unit batch result from a bloom summary."""
    scenarios = summary["scenarios"]
    return {
        "pair_id": pair_id,
        "status": _unit_status(scenarios),
        "estimated_tokens": estimate,
        "out_dir": summary["out_dir"],
        "scenarios": scenarios,
        "telemetry": summary["telemetry"],
        "complete_transcripts": sum(
            1 for s in scenarios if s.get("promotable") or s.get("status") == "complete"
        ),
        "promotable_transcripts": sum(1 for s in scenarios if s.get("promotable")),
        "judge_agreements": [s["judge_agreement"] for s in scenarios if s.get("judge_agreement")],
    }


def _run_one_pair(
    spec: dict[str, Any],
    harness: dict[str, Any],
    root: Path,
    eval_fn: Any | None,
    estimate: int,
) -> dict[str, Any]:
    """Run one manifest pair with failure isolation and return its result."""
    pair_id = str(spec.get("route_id", "pair")) + f"-s{int(spec.get('seed', 0))}"
    try:
        pair_id, unit, mode = _unit_from_spec(spec)
        bloom = _harness_from_manifest(harness)
        runner = run_bloom_single if mode == "single" else run_bloom_arm
        summary = runner(unit, harness=bloom, out_dir=root / pair_id, eval_fn=eval_fn)
        return _result_from_summary(pair_id, summary, estimate)
    except Exception as exc:  # batch isolation must record failures
        return {
            "pair_id": pair_id,
            "status": "error",
            "estimated_tokens": estimate,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _merge_usage(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-model token usage across pairs when providers report it."""
    models: dict[str, Any] = {}
    for result in results:
        telemetry = result.get("telemetry") or {}
        for model, usage in (telemetry.get("models") or {}).items():
            entry = models.setdefault(
                model, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            )
            entry["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
            entry["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
            entry["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
    return models


def _pair_id(spec: dict[str, Any]) -> str:
    """Return the stable report key for one manifest pair specification."""
    return str(spec.get("route_id", "pair")) + f"-s{int(spec.get('seed', 0))}"


def _cost_block(
    results: list[dict[str, Any]], estimated: int, cost: dict[str, Any]
) -> dict[str, Any]:
    """Assemble the batch cost report from pair results."""
    complete = sum(int(r.get("complete_transcripts", 0)) for r in results)
    actual_models = _merge_usage(results)
    actual_total = sum(m["total_tokens"] for m in actual_models.values())
    return {
        "estimated_tokens": estimated,
        "ceiling": cost.get("max_estimated_tokens"),
        "estimate_per_pair": int(cost.get("estimate_per_pair", DEFAULT_ESTIMATE_PER_PAIR)),
        "actual_models": actual_models,
        "actual_total_tokens": actual_total if actual_models else None,
        "complete_transcripts": complete,
        "tokens_per_complete_transcript": (
            round(actual_total / complete) if actual_models and complete else None
        ),
    }


def _report(
    manifest_path: Path,
    root: Path,
    results: list[dict[str, Any]],
    estimated: int,
    cost: dict[str, Any],
) -> dict[str, Any]:
    """Build the durable batch report after each completed or skipped pair."""
    return {
        "manifest": str(manifest_path),
        "out_dir": str(root),
        "pairs": results,
        "cost": _cost_block(results, estimated, cost),
    }


def _completed_results(root: Path, manifest_path: Path) -> dict[str, dict[str, Any]]:
    """Load successfully completed pairs from the matching durable report."""
    report_path = root / "batch_report.json"
    if not report_path.is_file():
        return {}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if report.get("manifest") != str(manifest_path):
        return {}
    return {
        str(result["pair_id"]): result
        for result in report.get("pairs") or []
        if result.get("status") == "ok" and result.get("pair_id")
    }


def _run_specs(
    specs: list[dict[str, Any]],
    harness: dict[str, Any],
    cost: dict[str, Any],
    root: Path,
    manifest_path: Path,
    prior: dict[str, dict[str, Any]],
    eval_fn: Any | None,
) -> tuple[list[dict[str, Any]], int]:
    """Run or resume manifest pairs, persisting progress after every pair."""
    ceiling = cost.get("max_estimated_tokens")
    estimate = int(cost.get("estimate_per_pair", DEFAULT_ESTIMATE_PER_PAIR))
    results: list[dict[str, Any]] = []
    estimated = 0
    for spec in specs:
        pair_id = _pair_id(spec)
        result = prior.get(pair_id)
        if result is not None:
            estimated += int(result.get("estimated_tokens", estimate))
        elif ceiling is not None and estimated + estimate > int(ceiling):
            result = {"pair_id": pair_id, "status": "skipped_cost_ceiling", "estimated_tokens": 0}
        else:
            estimated += estimate
            result = _run_one_pair(spec, harness, root, eval_fn, estimate)
        results.append(result)
        _atomic_write_json(
            root / "batch_report.json", _report(manifest_path, root, results, estimated, cost)
        )
    return results, estimated


def run_bloom_batch(
    manifest_path: str | Path,
    *,
    out_dir: str | Path | None = None,
    eval_fn: Any | None = None,
) -> dict[str, Any]:
    """Run every pair in a Bloom batch manifest with failure isolation.

    Args:
        manifest_path: JSON or YAML manifest with ``pairs`` plus optional
            ``harness`` and ``cost`` sections.
        out_dir: Artifact root; defaults to the ``out_dir`` key or a
            ``bloom-batch`` directory beside the manifest.
        eval_fn: Inspect eval callable (injected for tests).

    Returns:
        The batch report: per-pair statuses, errors, and cost bookkeeping.
    """
    manifest_path = Path(manifest_path)
    manifest = _load_manifest(manifest_path)
    harness = manifest.get("harness") or {}
    cost = manifest.get("cost") or {}
    root = Path(out_dir or manifest.get("out_dir") or manifest_path.parent / "bloom-batch")
    root.mkdir(parents=True, exist_ok=True)

    prior = _completed_results(root, manifest_path)
    results, estimated = _run_specs(
        manifest.get("pairs") or [], harness, cost, root, manifest_path, prior, eval_fn
    )
    report = _report(manifest_path, root, results, estimated, cost)
    try:
        report["package"] = pack_cycle(root, manifest_path=manifest_path)
    except Exception as exc:  # packaging must not erase the durable batch report
        report["package"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
    _atomic_write_json(root / "batch_report.json", report)
    return report
