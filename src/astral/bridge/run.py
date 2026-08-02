# size-justified: Bloom audit run plus per-sample QA share the pair lifecycle
"""Run one card pair through the Petri Bloom audit engine.

The bridge emits the pair as a Bloom behavior directory; this module executes
Bloom's audit task with explicit model roles and a declared compaction policy,
then normalizes transcripts through the tool-call contract in
``bridge.normalize``. Engine receipts, statuses, firewall findings, and raw-log
hashes are recorded beside the visible transcripts.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from inspect_ai import eval as inspect_eval
from inspect_ai.model import GenerateConfig
from petri_bloom._evaluation.evaluation import bloom_audit

from astral.bridge.bloom import pair_to_behavior, single_to_behavior, write_behavior_dir
from astral.bridge.normalize import NormalizedSample, firewall_check, normalize_sample
from astral.cards.contracts import ActorCard, ActorCardPair
from astral.qa.acceptance import evaluate_side
from astral.qa.coverage import CoverageReport, check_coverage
from astral.qa.judge import Judgment, judge_sample
from astral.qa.realization_gate import diagnose
from astral.runtime.contracts import DEFAULT_AGENTIC_MAX_TURNS, DEFAULT_TURN_CAP

ENGINE = "petri-bloom-audit-v1"


@dataclass(frozen=True)
class BloomHarness:
    """Model roles and runtime policy for one Bloom audit run.

    Attributes:
        auditor: Model id for the Petri auditor (plays the card).
        target: Model id for the assistant under evaluation.
        judge: Model id for the canonical QA judge; defaults to the target.
        audit_judge: Optional rotating second judge for label-reliability
            measurement; runs on a seeded subset of sides.
        max_turns: Auditor turn cap per scenario; defaults to half the visible-message
            cap, which yields about ten visible messages per transcript.
        compaction: Compaction policy passed to ``bloom_audit``; disabled by
            default because ASTRAL pairs use short horizons.
        system_message: Optional target system message override.
        fallback_models: Inspect fallback models for provider errors.
        turn_counter: Whether Petri emits "Turn N of M" scaffolding turns;
            disabled by default so scaffolding never enters transcripts.
    """

    auditor: str
    target: str
    judge: str | None = None
    audit_judge: str | None = None
    max_turns: int = DEFAULT_TURN_CAP // 2
    compaction: bool | int | float = False
    system_message: str | None = None
    fallback_models: list[str] | None = None
    turn_counter: bool = False
    reasoning_effort: str | None = None


def _samples_from_eval(log: Any) -> list[Any]:
    """Normalize Inspect eval output into a flat sample list.

    ``inspect_ai.eval`` may return one log object or a list of logs. Tests may
    inject a simple namespace. This helper accepts all three shapes.
    """
    if log is None:
        return []
    if isinstance(log, list):
        samples: list[Any] = []
        for item in log:
            samples.extend(list(getattr(item, "samples", None) or []))
        return samples
    return list(getattr(log, "samples", None) or [])


def _usage(log: Any) -> dict[str, Any]:
    """Per-model token telemetry from the eval log when providers report it."""
    models: dict[str, Any] = {}
    for sample in _samples_from_eval(log):
        for model, usage in (getattr(sample, "model_usage", None) or {}).items():
            entry = models.setdefault(
                model, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            )
            entry["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
            entry["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
            entry["total_tokens"] += int(getattr(usage, "total_tokens", 0) or 0)
    return models


def _telemetry(log: Any, harness: BloomHarness) -> dict[str, Any]:
    """Telemetry block: declared role mapping plus model-level usage.

    Token usage is attributed per model id. When roles share a model, usage is
    reported at the shared model level and must not be split by role.
    """
    roles = {
        "auditor": harness.auditor,
        "target": harness.target,
        "judge": harness.judge or harness.target,
    }
    models = _usage(log)
    distinct = len(set(roles.values()))
    attribution = "role-level" if distinct == 3 else "model-level (roles share models)"
    return {
        "roles": roles,
        "models": models,
        "attribution": attribution,
        "reasoning_effort": harness.reasoning_effort,
    }


def _raw_log_ref(out_root: Path) -> dict[str, str]:
    """Path and hash of the newest raw Inspect log for this run, if present."""
    logs = sorted(
        (out_root / "inspect_logs").glob("*.eval"),
        key=lambda p: p.stat().st_mtime,
    )
    if not logs:
        return {}
    raw = logs[-1]
    return {"path": str(raw), "sha256": hashlib.sha256(raw.read_bytes()).hexdigest()}


def _write_sample(  # noqa: PLR0913  # explicit keyword-only side artifacts
    normalized: NormalizedSample,
    *,
    side_dir: Path,
    engine: str,
    firewall: list[str],
    raw_log: dict[str, str],
    telemetry: dict[str, Any],
    coverage: dict[str, Any] | None = None,
    acceptance: dict[str, Any] | None = None,
    judgment: dict[str, Any] | None = None,
    audit_judgment: dict[str, Any] | None = None,
    judge_agreement: dict[str, Any] | None = None,
    diagnosis: dict[str, Any] | None = None,
) -> None:
    """Write visible turns, receipts, and the run record for one sample."""
    side_dir.mkdir(parents=True, exist_ok=True)
    (side_dir / "visible.jsonl").write_text(
        "".join(
            json.dumps(m.model_dump(mode="json"), sort_keys=True) + "\n" for m in normalized.visible
        ),
        encoding="utf-8",
    )
    (side_dir / "receipts.jsonl").write_text(
        "".join(
            json.dumps(r.model_dump(mode="json"), sort_keys=True) + "\n"
            for r in normalized.receipts
        ),
        encoding="utf-8",
    )
    record = {
        "engine": engine,
        "scenario": normalized.scenario,
        "side": normalized.side,
        "status": normalized.status,
        "turns": normalized.turns,
        "user_turns": normalized.user_turns,
        "assistant_turns": normalized.assistant_turns,
        "truncated_turns": normalized.truncated_turns,
        "firewall": {"status": "fail" if firewall else "pass", "findings": firewall},
        "telemetry": telemetry,
        "raw_log": raw_log,
        "coverage": coverage,
        "acceptance": acceptance,
        "judgment": judgment,
        "audit_judgment": audit_judgment,
        "judge_agreement": judge_agreement,
        "diagnosis": diagnosis,
    }
    (side_dir / "run.json").write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def resolve_max_turns(card: ActorCard, harness: BloomHarness) -> int:
    """Safety ceiling for one run: agentic cards get a higher Petri max_turns.

    Soft stop (checklist) should end the conversation earlier; this value only
    prevents tool-bearing runs from dying mid-exchange at a chat-era floor.
    """
    requested = harness.max_turns
    if card.biotool is None:
        return requested
    return max(requested, DEFAULT_AGENTIC_MAX_TURNS)


def run_bloom_single(
    card: ActorCard,
    *,
    harness: BloomHarness,
    out_dir: str | Path,
    eval_fn: Any | None = None,
) -> dict[str, Any]:
    """Execute one benign-only card (RB) through Bloom's engine.

    Args:
        card: The single actor card (benign, from a benign-only route).
        harness: Model roles and runtime policy for the audit.
        out_dir: Artifact root for normalized transcripts.
        eval_fn: Inspect eval callable (injected for tests).

    Returns:
        A summary of the run: scenario status, turns, firewall, telemetry.
    """
    pair = ActorCardPair(
        pair_id=f"{card.route.id}-{card.side}-single",
        benign=card,
        malicious=card,
        shared_hash=card.source_hash,
    )
    return run_bloom_arm(pair, harness=harness, out_dir=out_dir, eval_fn=eval_fn)


def _task_config(harness: BloomHarness) -> GenerateConfig | None:
    """Assemble the generation config for one audit task."""
    config: dict[str, Any] = {}
    if harness.fallback_models:
        config["fallback_models"] = harness.fallback_models
    if harness.reasoning_effort:
        config["reasoning_effort"] = harness.reasoning_effort
    return GenerateConfig(**config) if config else None


def _serialize_judgment(judgment: Judgment | None) -> dict[str, Any] | None:
    """Compact judgment for run.json and batch reports; None when judge failed."""
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


def _serialize_coverage(coverage: CoverageReport) -> dict[str, Any]:
    """Compact coverage report for run.json and batch reports."""
    return {
        "covered": coverage.covered,
        "total_deterministic": coverage.total_deterministic,
        "fully_covered": coverage.fully_covered,
        "aspects": [
            {
                "aspect": a.aspect,
                "addressed": a.addressed,
                "evidence_turn": a.evidence_turn,
                "method": a.method,
            }
            for a in coverage.aspects
        ],
    }


def _audit_subset(scenario: str, rate: float = 1.0) -> bool:
    """Seeded selection of sides for the second-judge reliability pass.

    Defaults to full dual-grading (rate 1.0): the audit judge is cheap and
    full overlap yields per-cycle agreement metrics and a judge-drift
    tripwire. Lower rates are available for cost-constrained campaigns.
    """
    if rate >= 1.0:
        return True
    digest = hashlib.sha256(scenario.encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF < rate


def _judge_agreement(judgment: Judgment | None, audit: Judgment | None) -> dict[str, Any] | None:
    """Pairwise agreement between canonical and audit judge on one side."""
    if judgment is None or audit is None or audit.model_error:
        return None
    variables = set(judgment.variables) & set(audit.variables)
    matches = sum(1 for v in variables if judgment.variables[v].choice == audit.variables[v].choice)
    return {
        "outcome_match": judgment.assistant_outcome == audit.assistant_outcome,
        "variable_match_rate": (matches / len(variables)) if variables else None,
        "variables_compared": len(variables),
    }


def _diagnose_side(
    card: ActorCard,
    normalized: NormalizedSample,
    judgment: Judgment | None,
    audit_judgment: Judgment | None,
    coverage: CoverageReport,
) -> dict[str, Any] | None:
    """Realization-gate diagnosis for one side; None when within tolerance."""
    judgment_dict = _serialize_judgment(judgment) or {}
    coverage_dict = _serialize_coverage(coverage)
    audit_dict = _serialize_judgment(audit_judgment)
    diagnosis = diagnose(
        dict(card.variables.model_dump(mode="json")),
        judgment_dict,
        side=normalized.side,
        card=card,
        coverage=coverage_dict,
        audit_judgment=audit_dict,
        turns=len(normalized.visible),
        messages=normalized.visible,
    )
    return diagnosis.as_dict() if diagnosis else None


def _consume_one_sample(
    sample: Any,
    *,
    pair: ActorCardPair,
    out_root: Path,
    engine: str,
    raw_log: dict[str, str],
    telemetry: dict[str, Any],
    judge_model: str,
    audit_judge_model: str | None = None,
) -> dict[str, Any]:
    """Normalize, evaluate, judge, and persist one Bloom sample."""
    normalized = normalize_sample(sample)
    card = pair.benign if normalized.side == "benign" else pair.malicious
    firewall = firewall_check(normalized.visible, card)
    coverage = check_coverage(card, normalized.visible)
    acceptance = evaluate_side(card, normalized.visible, firewall=firewall, coverage=coverage)
    judgment = None
    with contextlib.suppress(Exception):
        judgment = judge_sample(card, normalized.visible, model=judge_model)
    audit_judgment = None
    if audit_judge_model and _audit_subset(normalized.scenario):
        with contextlib.suppress(Exception):
            audit_judgment = judge_sample(card, normalized.visible, model=audit_judge_model)
    agreement = _judge_agreement(judgment, audit_judgment)
    diagnosis = _diagnose_side(card, normalized, judgment, audit_judgment, coverage)
    _write_sample(
        normalized,
        side_dir=out_root / normalized.side,
        engine=engine,
        firewall=firewall,
        coverage=_serialize_coverage(coverage),
        acceptance=acceptance.as_dict(),
        judgment=_serialize_judgment(judgment),
        audit_judgment=_serialize_judgment(audit_judgment),
        judge_agreement=agreement,
        diagnosis=diagnosis,
        raw_log=raw_log,
        telemetry=telemetry,
    )
    return {
        "scenario": normalized.scenario,
        "side": normalized.side,
        "status": normalized.status,
        "turns": normalized.turns,
        "truncated_turns": normalized.truncated_turns,
        "firewall": "fail" if firewall else "pass",
        "acceptance": acceptance.as_dict(),
        "promotable": acceptance.promotable,
        "judgment": _serialize_judgment(judgment),
        "audit_judgment": _serialize_judgment(audit_judgment),
        "judge_agreement": agreement,
        "diagnosis": diagnosis,
    }


def run_bloom_arm(
    pair: ActorCardPair,
    *,
    harness: BloomHarness,
    out_dir: str | Path,
    eval_fn: Any | None = None,
) -> dict[str, Any]:
    """Execute both sides of a pair through Bloom's auditor/target engine.

    Args:
        pair: The matched actor-card pair.
        harness: Model roles and runtime policy for the audit.
        out_dir: Artifact root for normalized transcripts.
        eval_fn: Inspect eval callable (injected for tests).

    Returns:
        A summary of the run: per-scenario statuses, turns, firewall results,
        telemetry, and the raw-log reference.
    """
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    if pair.malicious is pair.benign:
        behavior = single_to_behavior(pair.benign)
        card = pair.benign
    else:
        behavior = pair_to_behavior(pair)
        card = pair.malicious
    workdir = out_root / "behavior" / behavior.name
    write_behavior_dir(behavior, workdir, card)

    if eval_fn is None:
        eval_fn = inspect_eval
    task = bloom_audit(
        behavior=str(workdir),
        max_turns=resolve_max_turns(card, harness),
        compaction=harness.compaction,
        system_message=harness.system_message,
        turn_counter=harness.turn_counter,
    )
    config = _task_config(harness)
    if config:
        task.config = config
    log = eval_fn(
        task,
        model_roles={
            "auditor": harness.auditor,
            "target": harness.target,
            "judge": harness.judge or harness.target,
        },
        log_dir=str(out_root / "inspect_logs"),
    )
    engine = f"{ENGINE}:{harness.auditor}/{harness.target}"
    telemetry = _telemetry(log, harness)
    raw_log = _raw_log_ref(out_root)
    judge_model = harness.judge or harness.target
    results = [
        _consume_one_sample(
            sample,
            pair=pair,
            out_root=out_root,
            engine=engine,
            raw_log=raw_log,
            telemetry=telemetry,
            judge_model=judge_model,
            audit_judge_model=harness.audit_judge,
        )
        for sample in _samples_from_eval(log)
    ]
    return {
        "engine": engine,
        "behavior_dir": str(workdir),
        "out_dir": str(out_root),
        "scenarios": results,
        "telemetry": telemetry,
        "raw_log": raw_log,
    }


def _is_clean(summary: dict[str, Any]) -> bool:
    """Whether scenarios exist and all completed with passing firewalls."""
    scenarios = summary["scenarios"]
    return bool(scenarios) and all(
        s["status"] == "complete" and s["firewall"] == "pass" for s in scenarios
    )


def run_bloom_arm_with_fallback(
    pair: ActorCardPair,
    *,
    harness: BloomHarness,
    fallback_harness: BloomHarness | None,
    out_dir: str | Path,
    eval_fn: Any | None = None,
) -> dict[str, Any]:
    """Run the arm, retrying once with the fallback harness when incomplete.

    Provider errors are handled inside Inspect via ``fallback_models`` on the
    harness. Empty or truncated target responses are not errors, so a run whose
    scenarios do not complete cleanly is retried once with the fallback
    harness. Retry provenance is recorded in the summary.

    Args:
        pair: The matched actor-card pair.
        harness: Primary model roles and runtime policy.
        fallback_harness: Harness used for one retry when the primary run is
            not clean; ``None`` disables retry.
        out_dir: Artifact root for normalized transcripts.
        eval_fn: Inspect eval callable (injected for tests).

    Returns:
        The primary or fallback summary, with a ``retry`` record when a retry
        occurred.
    """
    primary = run_bloom_arm(pair, harness=harness, out_dir=out_dir, eval_fn=eval_fn)
    if _is_clean(primary) or fallback_harness is None:
        primary["retry"] = None
        return primary
    retry = run_bloom_arm(pair, harness=fallback_harness, out_dir=out_dir, eval_fn=eval_fn)
    retry["retry"] = {
        "reason": [
            {"scenario": s["scenario"], "status": s["status"], "firewall": s["firewall"]}
            for s in primary["scenarios"]
        ],
        "from": {"auditor": harness.auditor, "target": harness.target},
        "to": {"auditor": fallback_harness.auditor, "target": fallback_harness.target},
    }
    return retry
