# size-justified: eval writer + transcripts writer + review HTML bundle share card/sample plumbing
"""Package cycle/batch run dirs into viewer evals and human-readable JSON.

Best-practice contract (eval-file + transcripts.json):
- note-role messages preserved (tool calls / session markers)
- sample uuid, turn_count, model_usage, completion populated
- legends on eval.metadata (log.metadata does not survive the recorder)
- transcripts.json carries schema, legend, engine, and full user_prompt
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from inspect_ai.log import EvalDataset, EvalLog, EvalSample, EvalSpec, EvalStats, write_eval_log
from inspect_ai.log._log import EvalConfig
from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageUser,
    ModelOutput,
    ModelUsage,
)
from inspect_ai.scorer import Score

from astral import VariableAssignment, make_actor_card
from astral.bridge.regen_merge import _regen_samples
from astral.bridge.trajectory import _actor_trajectory, _per_turn_compliance
from astral.cards.grounding import load_grounding
from astral.qa.acceptance import biotier_compliance

TRANSCRIPT_SCHEMA = "astral.transcripts.v1"
_NS = uuid.uuid5(uuid.NAMESPACE_URL, "astralbench-cycle")


def _messages_from_visible(path: Path) -> list[Any]:
    """Load one visible.jsonl, preserving note rows as system messages."""
    messages: list[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        role = row.get("role")
        content = str(row.get("content") or "")
        if role == "user":
            messages.append(ChatMessageUser(content=content))
        elif role == "assistant":
            messages.append(ChatMessageAssistant(content=content))
        elif role == "note":
            messages.append(ChatMessageSystem(content=content))
    return messages


def _usage_from_run(run: dict[str, Any]) -> ModelUsage | None:
    """Sum per-model telemetry into one ModelUsage, or None if absent."""
    models = ((run.get("telemetry") or {}).get("models")) or {}
    if not models:
        return None
    tin = sum(int(v.get("input_tokens", 0) or 0) for v in models.values())
    tout = sum(int(v.get("output_tokens", 0) or 0) for v in models.values())
    return ModelUsage(input_tokens=tin, output_tokens=tout, total_tokens=tin + tout)


def _card_for(spec: dict[str, Any], side: str) -> Any:
    """Recompile the actor card for one transcript side from the manifest unit."""
    route_id = str(spec["route_id"])
    seed = int(spec.get("seed", 0))
    variables = VariableAssignment(**(spec.get("variables") or {}))
    if side == "benign":
        variables = variables.model_copy(update={"intended_scope": 0, "jailbreak": 0})
    include_biotool = bool(spec.get("tools", True))
    try:
        return make_actor_card(
            side="benign" if side == "benign" else "malicious",
            route_id=route_id,
            variables=variables,
            seed=seed,
            include_biotool=include_biotool,
        )
    except ValueError:
        # Legacy manifests predate per-pathway constraints (PR-26); clamp the
        # offending level into the route's now-allowed space for repacking.
        return make_actor_card(
            side="benign" if side == "benign" else "malicious",
            route_id=route_id,
            variables=_clamp_to_allowed(route_id, variables),
            seed=seed,
            include_biotool=include_biotool,
        )


def _clamp_to_allowed(route_id: str, variables: Any) -> Any:
    """Clamp legacy variable levels into the route's current allowed space."""
    route = load_grounding().routes[route_id]
    allowed = route.get("allowed_values") or {}
    updates: dict[str, int] = {}
    kc = int(variables.kill_chain)
    allowed_kc = [int(v) for v in allowed.get("kill_chain", [kc])]
    if kc not in allowed_kc:
        updates["kill_chain"] = max((v for v in allowed_kc if v <= kc), default=min(allowed_kc))
    return variables.model_copy(update=updates) if updates else variables


def _sample_id(cycle: str, route_id: str, side: str, seed: int) -> str:
    """Stable sample id for one transcript."""
    return f"{cycle}:{route_id}:s{seed}:{side}"


def _metadata(
    card: Any, run: dict[str, Any], *, cycle: str, seed: int, messages: list[Any] | None = None
) -> dict[str, Any]:
    """Sample metadata firewall: labels stay in metadata, not the visible log."""
    agent = card.agent.model_dump(mode="json") if card.agent else None
    return {
        "cycle": cycle,
        "route_id": card.route.id,
        "family": card.route.id.split(".", 1)[0].upper(),
        "side": card.side,
        "seed": seed,
        "engine": run.get("engine"),
        "status": run.get("status"),
        "turns": run.get("turns"),
        "firewall": run.get("firewall"),
        "coverage": run.get("coverage"),
        "variables": {
            "sc": str(card.variables.scientific_capability),
            "jb": str(card.variables.jailbreak),
            "kc": [str(card.variables.kill_chain)],
            "sp": str(card.variables.intended_scope),
        },
        "v4_summary": {
            "scientific_capability": {"level": str(card.variables.scientific_capability)},
            "jail_breaking": {"level": str(card.variables.jailbreak)},
            "kill_chain": {"stages": [str(card.variables.kill_chain)]},
            "scope": {"level": str(card.variables.intended_scope)},
        },
        "card": card.model_dump(mode="json"),
        "agent": agent,
        "agentless": card.agent is None,
        "jailbreak_method": card.jailbreak_method,
        "biotool": card.biotool.model_dump(mode="json") if card.biotool else None,
        "tools_enabled": card.biotool is not None,
        "reasoning_effort": ((run.get("telemetry") or {}).get("reasoning_effort")),
        "biotier_refuse_expected": _refuse_expected(card),
        "biotier_compliance": _compliance(card, messages or []),
        "biotier_trajectory": _per_turn_compliance(card, messages or []),
        "actor_trajectory": _actor_trajectory(card, messages or []),
        "kill_chain_stage": _kc_stage_label(int(card.variables.kill_chain)),
        "models": _role_models(run),
        "judgment": run.get("judgment"),
        "judge_agreement": run.get("judge_agreement"),
        "audit_judgment": run.get("audit_judgment"),
    }


_KC_STAGES: dict[int, str] | None = None


def _compliance(card: Any, messages: list[Any]) -> str:
    """BioTIER compliance quadrant for this side."""
    family = card.route.id.split(".", 1)[0]
    return biotier_compliance(family, messages)


def _refuse_expected(card: Any) -> bool:
    """Whether the route is refuse-expected (CA/BD) per BioTIER framing."""
    return card.route.id.split(".", 1)[0].lower() in {"ca", "bd"}


def _kc_stage_label(level: int) -> str:
    """Human-readable kill-chain stage name for the level."""
    global _KC_STAGES
    if _KC_STAGES is None:
        levels = load_grounding().variables["kill_chain"]["levels"]
        _KC_STAGES = {int(k): str(v.get("label") or "") for k, v in levels.items()}
    return _KC_STAGES.get(level, "")


def _role_models(run: dict[str, Any]) -> dict[str, str]:
    """User/assistant/judge model ids from the run telemetry."""
    roles = ((run.get("telemetry") or {}).get("roles")) or {}
    return {
        "user": str(roles.get("auditor") or ""),
        "assistant": str(roles.get("target") or ""),
        "judge": str(roles.get("judge") or ""),
        "audit_judge": str(roles.get("audit_judge") or ""),
    }


def _sample_scores(run: dict[str, Any]) -> dict[str, Any] | None:
    """Map QA verdicts into Inspect viewer scores (metrics surface)."""
    judgment = run.get("judgment") or {}
    acceptance = run.get("acceptance") or {}
    if not judgment and not acceptance:
        return None
    scores: dict[str, Any] = {}
    _judge_score(scores, judgment)
    _acceptance_scores(scores, acceptance, run)
    return scores or None


def _judge_score(scores: dict[str, Any], judgment: dict[str, Any]) -> None:
    """Judge outcome score entry."""
    outcome = judgment.get("assistant_outcome")
    if outcome:
        scores["judge_outcome"] = Score(value=str(outcome))


def _acceptance_scores(
    scores: dict[str, Any], acceptance: dict[str, Any], run: dict[str, Any]
) -> None:
    """Acceptance and agreement score entries."""
    if acceptance:
        scores["promotable"] = Score(value=bool(acceptance.get("promotable")))
        reasons = acceptance.get("reasons") or []
        if reasons:
            scores["acceptance_reasons"] = Score(value=", ".join(str(r) for r in reasons))
    agreement = run.get("judge_agreement") or {}
    if agreement.get("variable_match_rate") is not None:
        scores["judge_agreement"] = Score(value=float(agreement["variable_match_rate"]))


def _build_sample(
    *,
    cycle: str,
    spec: dict[str, Any],
    side: str,
    visible: Path,
    run: dict[str, Any],
) -> EvalSample:
    """Build one EvalSample from a side directory."""
    messages = _messages_from_visible(visible)
    card = _card_for(spec, side)
    seed = int(spec.get("seed", 0))
    sample_id = _sample_id(cycle, str(spec["route_id"]), side, seed)
    usage = _usage_from_run(run)
    completion = next(
        (
            str(m.content)
            for m in reversed(messages)
            if getattr(m, "role", "") == "assistant" and str(m.content).strip()
        ),
        "",
    )
    first_user = next(
        (
            str(m.content)
            for m in messages
            if getattr(m, "role", "") == "user" and str(m.content).strip()
        ),
        "",
    )
    sample = EvalSample(
        id=sample_id,
        epoch=1,
        input=first_user,
        target=side,
        messages=messages,
        metadata=_metadata(card, run, cycle=cycle, seed=seed, messages=messages),
        setup=card.user_prompt,
        uuid=str(uuid.uuid5(_NS, sample_id)),
        turn_count=len(messages),
        scores=_sample_scores(run),
    )
    if completion:
        sample.output = ModelOutput(completion=completion)
    _attach_usage(sample, usage, run)
    return sample


def _attach_usage(sample: EvalSample, usage: ModelUsage | None, run: dict[str, Any]) -> None:
    """Attach model usage to the sample and its output when present."""
    if usage is None:
        return
    engine = str(run.get("engine") or "petri-bloom-audit-v1")
    sample.model_usage = {engine: usage}
    if sample.output is not None:
        sample.output.usage = usage


def _iter_side_dirs(unit_dir: Path) -> list[Path]:
    """Yield benign/malicious side dirs under one unit root."""
    return [
        path
        for name in ("benign", "malicious")
        if (path := unit_dir / name).is_dir() and (path / "visible.jsonl").is_file()
    ]


def _load_run(side_dir: Path) -> dict[str, Any]:
    """Load run.json for one side, or an empty dict when missing."""
    run_path = side_dir / "run.json"
    if not run_path.is_file():
        return {}
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, dict) else {}


def _samples_for_unit(
    root: Path, cycle: str, pair_id: str, spec: dict[str, Any]
) -> list[EvalSample]:
    """Build samples for every visible side under one unit directory."""
    unit_dir = root / pair_id
    if not unit_dir.is_dir():
        return []
    return [
        _build_sample(
            cycle=cycle,
            spec=spec,
            side=side_dir.name,
            visible=side_dir / "visible.jsonl",
            run=_load_run(side_dir),
        )
        for side_dir in _iter_side_dirs(unit_dir)
    ]


def _samples_from_report(
    root: Path, manifest: dict[str, Any], report: dict[str, Any]
) -> list[EvalSample]:
    """Collect samples for every finished unit with visible sides."""
    cycle = str(manifest.get("cycle") or root.name)
    specs = {f"{s['route_id']}-s{int(s.get('seed', 0))}": s for s in manifest.get("pairs") or []}
    samples: list[EvalSample] = []
    for result in report.get("pairs") or []:
        pair_id = str(result.get("pair_id") or "")
        spec = specs.get(pair_id)
        if spec is not None:
            samples.extend(_samples_for_unit(root, cycle, pair_id, spec))
    return samples


def _legend(manifest: dict[str, Any]) -> dict[str, str]:
    """Top-level how-to-read guide for the package."""
    harness = manifest.get("harness") or {}
    return {
        "how_to_read": (
            "Each sample is one cycle transcript. Metadata holds card labels; "
            "visible messages are the firewall surface. role=system notes mark "
            "tool calls and session boundaries, not speaker turns."
        ),
        "engine": (
            f"auditor={harness.get('auditor_model')} "
            f"target={harness.get('target_model')} "
            f"judge={harness.get('judge_model')}"
        ),
        "ratio": str(manifest.get("ratio") or "2:2:2"),
        "firewall": "pass = no private card material in visible turns",
        "status": "unit status from run.json (complete | incomplete | error)",
    }


def _name_or_none(payload: Any, key: str = "canonical_name") -> str | None:
    """Read a nested display name from metadata, if present."""
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    return str(value) if value is not None else None


def _firewall_status(firewall: Any) -> Any:
    """Flatten firewall metadata to a status string when nested."""
    if isinstance(firewall, dict):
        return firewall.get("status")
    return firewall


def _transcript_row(sample: EvalSample) -> dict[str, Any]:
    """One human-readable transcript object for transcripts.json."""
    meta = dict(sample.metadata or {})
    raw_card = meta.get("card")
    card: dict[str, Any] = raw_card if isinstance(raw_card, dict) else {}
    return {
        "id": sample.id,
        "cycle": meta.get("cycle"),
        "route_id": meta.get("route_id"),
        "family": meta.get("family"),
        "side": meta.get("side"),
        "seed": meta.get("seed"),
        "status": meta.get("status"),
        "turns": meta.get("turns") or sample.turn_count,
        "firewall": _firewall_status(meta.get("firewall")),
        "engine": meta.get("engine"),
        "variables": meta.get("variables"),
        "models": meta.get("models"),
        "biotier_compliance": meta.get("biotier_compliance"),
        "biotier_trajectory": meta.get("biotier_trajectory"),
        "kill_chain_stage": meta.get("kill_chain_stage"),
        "reasoning_effort": meta.get("reasoning_effort"),
        "agent": _name_or_none(meta.get("agent")),
        "agentless": meta.get("agentless"),
        "jailbreak_method": meta.get("jailbreak_method"),
        "biotool": _name_or_none(meta.get("biotool")),
        "objective": card.get("objective") or meta.get("objective"),
        "user_prompt": card.get("user_prompt") or meta.get("user_prompt"),
        "messages": [{"role": m.role, "content": str(m.content)} for m in sample.messages],
    }


def write_transcripts_json(
    samples: list[EvalSample], path: Path, *, manifest: dict[str, Any]
) -> Path:
    """Write the human-readable multi-transcript package."""
    payload = {
        "schema": TRANSCRIPT_SCHEMA,
        "description": f"ASTRAL cycle package from {manifest.get('cycle') or path.parent.name}",
        "generated": datetime.now(UTC).strftime("%Y-%m-%d"),
        "legend": _legend(manifest),
        "count": len(samples),
        "transcripts": [_transcript_row(sample) for sample in samples],
    }
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    return path


def write_cycle_eval(samples: list[EvalSample], path: Path, *, manifest: dict[str, Any]) -> Path:
    """Write the Inspect-native combined eval with best-practice fields."""
    cycle = str(manifest.get("cycle") or "cycle")
    total_in = sum(sum(u.input_tokens for u in (s.model_usage or {}).values()) for s in samples)
    total_out = sum(sum(u.output_tokens for u in (s.model_usage or {}).values()) for s in samples)
    harness = manifest.get("harness") or {}
    model = f"{harness.get('auditor_model', '?')} x {harness.get('target_model', '?')}"
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    log = EvalLog(
        status="success",
        eval=EvalSpec(
            created=datetime.now(UTC).strftime("%Y-%m-%d"),
            task=f"astralbench-cycle-{cycle}",
            dataset=EvalDataset(
                name=f"ASTRALBench cycle {cycle} ({len(samples)} transcripts)",
                location=path.name,
                samples=len(samples),
            ),
            model=model,
            config=EvalConfig(),
            metadata={"legend": _legend(manifest)},
        ),
        stats=EvalStats(
            started_at=now,
            completed_at=now,
            model_usage={
                "cycle": ModelUsage(
                    input_tokens=total_in,
                    output_tokens=total_out,
                    total_tokens=total_in + total_out,
                )
            },
        ),
        samples=samples,
    )
    write_eval_log(log, str(path))
    return path


def _qa_index(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Index batch-report scenarios by (pair_id, side) for QA enrichment."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for pair in report.get("pairs") or []:
        for scenario in pair.get("scenarios") or []:
            out[(str(pair.get("pair_id") or ""), str(scenario.get("side") or ""))] = scenario
    return out


def _pair_id_of(sample_id: str) -> str:
    """Recover the unit pair id from a sample id (cycle:route:sSEED:side)."""
    parts = str(sample_id).split(":")
    return f"{parts[1]}-{parts[2]}" if len(parts) >= 4 else ""


def _review_messages(sample: EvalSample) -> list[dict[str, str]]:
    """Project EvalSample messages into plain review rows."""
    return [
        {
            "role": "system" if getattr(m, "role", "") == "system" else str(getattr(m, "role", "")),
            "content": str(getattr(m, "content", "")),
        }
        for m in sample.messages or []
    ]


def _review_scores(qa: dict[str, Any]) -> dict[str, Any] | None:
    """Build the Judge score block from batch QA, or None when unjudged."""
    judgment = qa.get("judgment") or {}
    if not judgment:
        return None
    acceptance = qa.get("acceptance") or {}
    return {
        "Judge": {
            "value": {
                "assistant_outcome": judgment.get("assistant_outcome"),
                "promotable": qa.get("promotable"),
                "acceptance_reasons": ", ".join(acceptance.get("reasons") or []) or "—",
            },
            "metadata": {
                "variables": judgment.get("variables") or {},
                "notes": judgment.get("notes"),
                "assistant_outcome_rationale": judgment.get("assistant_outcome_rationale"),
                "model_error": judgment.get("model_error"),
            },
        }
    }


def _review_metadata(
    sample: EvalSample, qa: dict[str, Any], messages: list[dict[str, str]]
) -> dict[str, Any]:
    """Enrich sample metadata with batch QA and tool-loop counts."""
    metadata = dict(sample.metadata or {})
    card = dict(metadata.get("card") or {})
    metadata.update(
        {
            "promotable": qa.get("promotable"),
            "acceptance": qa.get("acceptance") or {},
            "tool_calls": sum(1 for m in messages if "tool call" in m["content"]),
            "tool_results": sum(1 for m in messages if "tool result" in m["content"]),
            "user_prompt": card.get("user_prompt") or metadata.get("user_prompt"),
        }
    )
    return metadata


def _review_sample(sample: EvalSample, qa: dict[str, Any]) -> dict[str, Any]:
    """Project one EvalSample plus batch QA into the review-bundle shape."""
    messages = _review_messages(sample)
    metadata = _review_metadata(sample, qa, messages)
    card = dict(metadata.get("card") or {})
    review: dict[str, Any] = {
        "id": str(sample.id),
        "epoch": str(metadata.get("cycle") or "1"),
        "input": str(card.get("objective") or sample.input or ""),
        "target": metadata.get("side") or sample.target,
        "messages": messages,
        "metadata": metadata,
    }
    scores = _review_scores(qa)
    if scores is not None:
        review["scores"] = scores
    return review


def write_review_html(
    samples: list[EvalSample],
    path: Path,
    *,
    manifest: dict[str, Any],
    report: dict[str, Any],
) -> Path:
    """Write the interactive cycle review HTML (chat + card + judge, side by side).

    Args:
        samples: The packaged cycle samples.
        path: Destination HTML file.
        manifest: The cycle manifest (legend source).
        report: The batch report (acceptance + judgment per side).

    Returns:
        The written path.
    """
    template_path = Path(__file__).resolve().parents[1] / "assets" / "review_template.html"
    template = template_path.read_text(encoding="utf-8")
    qa_by_key = _qa_index(report)
    review_samples = [
        _review_sample(
            sample,
            qa_by_key.get(
                (_pair_id_of(str(sample.id)), str((sample.metadata or {}).get("side") or "")), {}
            ),
        )
        for sample in samples
    ]
    cycle = str(manifest.get("cycle") or "")
    harness = manifest.get("harness") or {}
    payload = {
        "schema": "astral.review-bundle.v1",
        "source_schema": TRANSCRIPT_SCHEMA,
        "description": f"ASTRAL cycle {cycle} (agentic tools-on)",
        "generated": datetime.now(UTC).strftime("%Y-%m-%d"),
        "legend": {
            "how_to_read": (
                "Each sample is one cycle transcript. Metadata holds card labels; "
                "visible messages are the firewall surface. role=system notes mark "
                "tool calls and session boundaries, not speaker turns."
            ),
            "engine": (
                f"auditor={harness.get('auditor_model')} "
                f"target={harness.get('target_model')} judge={harness.get('judge_model')}"
            ),
            "ratio": str(manifest.get("ratio") or "2:2:2"),
            "firewall": "pass = no private card material in visible turns",
            "status": "unit status from run.json (complete | incomplete | error)",
        },
        "count": len(review_samples),
        "cycle": cycle,
        "samples": review_samples,
    }
    subtitle = (
        f"Agentic tools-on · {len(review_samples)} transcripts · chat and assignment side by side"
    )
    html = template.replace("__REVIEW_DATA__", json.dumps(payload, indent=2))
    html = html.replace("__REVIEW_SUBTITLE__", subtitle)
    path.write_text(html, encoding="utf-8")
    return path


def pack_cycle(
    root: str | Path,
    *,
    manifest_path: str | Path | None = None,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Package a finished cycle/batch root into eval + transcripts.json.

    Args:
        root: Batch out_dir containing unit subdirs and batch_report.json.
        manifest_path: Manifest used to recompile cards; defaults to root/manifest.yaml.
        report_path: Durable batch report; defaults to root/batch_report.json.

    Returns:
        Paths and sample counts for the written artifacts.
    """
    root_path = Path(root)
    manifest_file = Path(manifest_path or root_path / "manifest.yaml")
    report_file = Path(report_path or root_path / "batch_report.json")
    if manifest_file.suffix == ".json":
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    else:
        manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
    report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.is_file() else {}
    samples = _samples_from_report(root_path, manifest, report)
    samples.extend(_regen_samples(root_path, samples))
    cycle = str(manifest.get("cycle") or root_path.name)
    eval_path = root_path / f"astralbench-cycle-{cycle}.eval"
    json_path = root_path / "transcripts.json"
    write_cycle_eval(samples, eval_path, manifest=manifest)
    write_transcripts_json(samples, json_path, manifest=manifest)
    review_path = root_path / f"astralbench-cycle-{cycle}-review.html"
    write_review_html(samples, review_path, manifest=manifest, report=report)
    return {
        "cycle": cycle,
        "samples": len(samples),
        "eval_path": str(eval_path),
        "transcripts_path": str(json_path),
        "review_path": str(review_path),
    }
