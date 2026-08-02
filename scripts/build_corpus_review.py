#!/usr/bin/env python3
# ruff: noqa: T201  # CLI script: stdout is the interface
"""Build the ASTRALBench corpus review bundle from completed cycles.

Reads every ``data/cycles/cycle-N`` with transcripts.json + batch_report.json
and emits the interactive review HTML (chat + assignment + judge, side by
side), a flat transcripts JSON, and a combined Inspect eval. Rebuilds are
idempotent — rerun after new cycles land.

Usage:
    python scripts/build_corpus_review.py [--cycles-root data/cycles] [--out data/cycles/dataset]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from inspect_ai.log import (
    EvalConfig,
    EvalDataset,
    EvalLog,
    EvalSpec,
    EvalStats,
    read_eval_log,
    write_eval_log,
)
from inspect_ai.model import ModelUsage

TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "astral" / "assets" / "review_template.html"
)


def _qa_index(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Index batch scenarios by (pair_id, side)."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for pair in report.get("pairs") or []:
        for scenario in pair.get("scenarios") or []:
            out[(str(pair.get("pair_id") or ""), str(scenario.get("side") or ""))] = scenario
    return out


def _pair_id_of(sample_id: str) -> str:
    parts = str(sample_id).split(":")
    return f"{parts[1]}-{parts[2]}" if len(parts) >= 4 else ""


def _review_sample(entry: dict[str, Any], qa: dict[str, Any]) -> dict[str, Any]:
    """Project one transcripts.json entry plus batch QA into the review shape."""
    acceptance = qa.get("acceptance") or {}
    judgment = qa.get("judgment") or (entry.get("judgment") or {})
    messages = entry.get("messages") or []
    meta = {
        "id": entry["id"],
        "route_id": entry.get("route_id"),
        "side": entry.get("side"),
        "status": entry.get("status"),
        "turns": len(messages),
        "firewall": {"status": entry.get("firewall")},
        "jailbreak_method": entry.get("jailbreak_method"),
        "biotool": entry.get("biotool"),
        "tools_enabled": entry.get("tools_enabled"),
        "agent": entry.get("agent"),
        "agentless": entry.get("agentless"),
        "seed": entry.get("seed"),
        "cycle": entry.get("cycle"),
        "engine": entry.get("engine"),
        "objective": entry.get("objective"),
        "user_prompt": entry.get("user_prompt"),
        "variables": entry.get("variables"),
        "promotable": qa.get("promotable"),
        "acceptance": acceptance,
        "models": entry.get("models") or (entry.get("metadata") or {}).get("models"),
        "biotier_compliance": entry.get("biotier_compliance")
        or (entry.get("metadata") or {}).get("biotier_compliance"),
        "biotier_trajectory": entry.get("biotier_trajectory")
        or (entry.get("metadata") or {}).get("biotier_trajectory"),
        "kill_chain_stage": entry.get("kill_chain_stage")
        or (entry.get("metadata") or {}).get("kill_chain_stage"),
        "reasoning_effort": entry.get("reasoning_effort")
        or (entry.get("metadata") or {}).get("reasoning_effort"),
        "judge_agreement": qa.get("judge_agreement") or entry.get("judge_agreement"),
        "tool_calls": sum(1 for m in messages if "tool call" in str(m.get("content", ""))),
        "tool_results": sum(1 for m in messages if "tool result" in str(m.get("content", ""))),
        "card": {
            "side": entry.get("side"),
            "seed": entry.get("seed"),
            "objective": entry.get("objective"),
            "user_prompt": entry.get("user_prompt"),
            "jailbreak_method": entry.get("jailbreak_method"),
            "biotool": entry.get("biotool"),
            "tools_enabled": entry.get("tools_enabled"),
            "agent": entry.get("agent"),
            "variables": entry.get("variables"),
            "route": {"id": entry.get("route_id")},
        },
    }
    sample: dict[str, Any] = {
        "id": entry["id"],
        "epoch": str(entry.get("cycle") or "1"),
        "input": entry.get("objective") or "",
        "target": entry.get("side"),
        "messages": messages,
        "metadata": meta,
    }
    if judgment:
        sample["scores"] = {
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
    return sample


def collect_samples(
    cycles_root: Path, *, promotable_only: bool = True
) -> tuple[list[dict[str, Any]], list[str]]:
    """Gather review samples from every completed cycle directory."""
    samples: list[dict[str, Any]] = []
    included: list[str] = []
    for cycle_dir in sorted(
        cycles_root.iterdir(), key=lambda p: int(p.name[6:]) if p.name[6:].isdigit() else 0
    ):
        if not cycle_dir.name.startswith("cycle-") or not cycle_dir.name[6:].isdigit():
            continue
        transcripts = cycle_dir / "transcripts.json"
        report = cycle_dir / "batch_report.json"
        if not (transcripts.is_file() and report.is_file()):
            continue
        entries = json.loads(transcripts.read_text(encoding="utf-8")).get("transcripts") or []
        qa_by_key = _qa_index(json.loads(report.read_text(encoding="utf-8")))
        included.append(cycle_dir.name)
        for entry in entries:
            samples.append(
                _review_sample(
                    entry,
                    qa_by_key.get((_pair_id_of(entry["id"]), str(entry.get("side") or "")), {}),
                )
            )
    return samples, included


def build_bundle(samples: list[dict[str, Any]], cycles: list[str]) -> dict[str, Any]:
    """Assemble the review-bundle payload."""
    span = f"{cycles[0]}-{cycles[-1]}" if cycles else "none"
    return {
        "schema": "astral.review-bundle.v1",
        "source_schema": "astral.transcripts.v1",
        "description": f"ASTRALBench corpus review — cycles {span} ({len(samples)} transcripts)",
        "generated": datetime.now(UTC).strftime("%Y-%m-%d"),
        "legend": {
            "how_to_read": "One sample per cycle transcript; messages are the firewall surface.",
            "engine": "multi-cycle: rotation harnesses (see per-sample metadata)",
            "ratio": "2:2:2",
            "firewall": "pass = no private card material in visible turns",
            "status": "unit status from run.json (complete | incomplete | error)",
        },
        "count": len(samples),
        "cycle": "corpus",
        "samples": samples,
    }


def write_html(bundle: dict[str, Any], path: Path) -> None:
    """Render the interactive review HTML from the shared template."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__REVIEW_DATA__", json.dumps(bundle, indent=1))
    subtitle = f"Corpus review · {bundle['count']} transcripts · chat and assignment side by side"
    path.write_text(html.replace("__REVIEW_SUBTITLE__", subtitle), encoding="utf-8")


def _corpus_eval(cycles_root: Path, cycles: list[str], out_path: Path) -> Path:
    """Write the combined Inspect-native eval for all completed cycles."""
    samples = []
    total_in = total_out = 0
    for name in cycles:
        eval_path = cycles_root / name / f"astralbench-{name}.eval"
        if not eval_path.is_file():
            continue
        log = read_eval_log(str(eval_path))
        for sample in log.samples or []:
            metadata = dict(sample.metadata or {})
            metadata["split"] = _split_of(str(sample.id))
            sample.metadata = metadata
            samples.append(sample)
            for usage in (sample.model_usage or {}).values():
                total_in += usage.input_tokens
                total_out += usage.output_tokens
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    log = EvalLog(
        status="success",
        eval=EvalSpec(
            created=datetime.now(UTC).strftime("%Y-%m-%d"),
            task="dataset",
            dataset=EvalDataset(
                name=f"dataset ({len(samples)} transcripts, {len(cycles)} cycles)",
                location=out_path.name,
                samples=len(samples),
            ),
            model="multi-cycle rotation (see per-sample metadata)",
            config=EvalConfig(),
            metadata={
                "legend": {
                    "how_to_read": "Cycle transcripts; messages are the firewall surface.",
                    "ratio": "2:2:2",
                    "firewall": "pass = no private card material in visible turns",
                    "engine": "petri-bloom-audit-v1 with rotation harnesses",
                }
            },
        ),
        stats=EvalStats(
            started_at=now,
            completed_at=now,
            model_usage={
                "corpus": ModelUsage(
                    input_tokens=total_in,
                    output_tokens=total_out,
                    total_tokens=total_in + total_out,
                )
            },
        ),
        samples=samples,
    )
    write_eval_log(log, str(out_path))
    return out_path


def _split_of(sample_id: str) -> str:
    """Deterministic 50/50 train/test assignment by sample-id hash."""
    digest = hashlib.sha256(f"split|{sample_id}".encode()).hexdigest()
    return "train" if int(digest[:8], 16) % 2 == 0 else "test"


def _write_splits(bundle: dict[str, Any], out: Path) -> dict[str, int]:
    """Write train/test transcripts.json files for the DSPy split."""
    splits: dict[str, list[dict[str, Any]]] = {"train": [], "test": []}
    for sample in bundle["samples"]:
        split = _split_of(str(sample["id"]))
        sample["metadata"]["split"] = split
        splits[split].append(sample)
    for name, rows in splits.items():
        payload = {**bundle, "split": name, "count": len(rows), "samples": rows}
        (out / f"dataset-{name}.json").write_text(
            json.dumps(payload, indent=1) + "\n", encoding="utf-8"
        )
    return {"train": len(splits["train"]), "test": len(splits["test"])}


def _write_manifest(bundle: dict[str, Any], out: Path, splits: dict[str, int]) -> None:
    """Write the corpus manifest: schema, artifact hashes, counts, provenance."""
    artifacts = {}
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.yaml":
            artifacts[path.name] = {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    manifest = {
        "schema": "astral.corpus_manifest.v1",
        "name": "ASTRALBench corpus",
        "generated": bundle.get("generated"),
        "transcripts": bundle["count"],
        "splits": splits,
        "split_rule": "deterministic 50/50 by sha256('split|'+sample_id) — stable across rebuilds",
        "artifacts": artifacts,
        "status": "dataset + eval corpus; benchmark protocol pending",
    }
    (out / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


def _write_card(bundle: dict[str, Any], splits: dict[str, int]) -> str:
    """Write the dataset card (README.md) for the corpus."""
    return f"""# ASTRALBench Corpus

Synthetic behavior-class-differentiated transcripts for scanner evaluation,
generated through the ASTRAL cycle pipeline (BioTIER-grounded cards, Petri
Bloom auditor-target, deterministic normalization, dual-judge QA).

## Contents

| Artifact | Purpose |
|---|---|
| astralbench-corpus.eval | combined Inspect-native eval (all transcripts) |
| transcripts.json | flat corpus bundle (promotable-first) |
| astralbench-corpus-train.json / -test.json | deterministic 50/50 DSPy split |
| astralbench-corpus-review.html | interactive human review app |
| manifest.yaml | schema, artifact hashes, counts |

## Counts

- transcripts: {bundle["count"]}
- train/test: {splits["train"]} / {splits["test"]}

## Labels

Each transcript carries: route_id (BioTIER route), side (benign/malicious),
assigned variables (scientific_capability, jailbreak, kill_chain,
intended_scope), agent, biotool, firewall verdict, acceptance verdicts, and
dual-judge outcomes (canonical + rotating audit judge with agreement).

## Status

Dataset + eval corpus. Benchmark protocol (task spec, scoring metrics,
baselines) is pending; do not cite as a validated benchmark.
"""


def main() -> int:
    """Build the corpus bundle artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles-root", type=Path, default=Path("data/cycles"))
    parser.add_argument("--out", type=Path, default=Path("data/cycles/dataset"))
    parser.add_argument("--downloads", type=Path, default=None, help="also copy artifacts here")
    parser.add_argument("--all", action="store_true", help="include non-promotable transcripts")
    args = parser.parse_args()

    samples, cycles = collect_samples(args.cycles_root, promotable_only=not args.all)
    if not samples:
        print("no completed cycles found", file=sys.stderr)
        return 1
    bundle = build_bundle(samples, cycles)
    args.out.mkdir(parents=True, exist_ok=True)
    artifacts = [
        args.out / "dataset.json",
        args.out / "review.html",
        _corpus_eval(args.cycles_root, cycles, args.out / "dataset.eval"),
    ]
    artifacts[0].write_text(json.dumps(bundle, indent=1) + "\n", encoding="utf-8")
    write_html(bundle, artifacts[1])
    splits = _write_splits(bundle, args.out)
    (args.out / "README.md").write_text(_write_card(bundle, splits), encoding="utf-8")
    _write_manifest(bundle, args.out, splits)
    print(f"cycles: {len(cycles)} ({cycles[0]}-{cycles[-1]})")
    print(f"transcripts: {bundle['count']}")
    for artifact in artifacts:
        print(f"wrote {artifact}")
    if args.downloads:
        args.downloads.mkdir(parents=True, exist_ok=True)
        for artifact in artifacts:
            (args.downloads / artifact.name).write_bytes(artifact.read_bytes())
            print(f"copied {args.downloads / artifact.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
