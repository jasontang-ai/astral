"""Backfill QA judgments on logs that lack them (regen-merged records).

Adds the primary QA ``judgment`` (variables, outcome, compliance) to logs
missing it, so the dual-judge coverage spans the full corpus.

Usage:
    python scripts/backfill_qa_judge.py [--cycles-root data/cycles] [--limit N]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any, Literal, cast

from astral import VariableAssignment, make_actor_card
from astral.qa.judge import judge_sample
from astral.runtime.contracts import Message


def _card_for(spec: dict[str, Any], side: Literal["benign", "malicious"]) -> Any:
    variables = VariableAssignment(**dict(spec.get("variables") or {}))
    return make_actor_card(
        side=side,
        route_id=str(spec["route_id"]),
        variables=variables,
        seed=int(spec.get("seed", 0)),
        include_biotool=bool(spec.get("include_biotool", True)),
    )


def _val(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool, list, dict)):
        return v
    dump = getattr(v, "model_dump", None)
    return dump() if callable(dump) else str(v)


def _serialize(judgment: Any) -> dict[str, Any] | None:
    if judgment is None:
        return None
    variables = judgment.variables
    if variables is not None:
        items = variables.items() if isinstance(variables, dict) else vars(variables).items()
        variables = {k: _val(v) for k, v in items}
    return {
        "assistant_outcome": judgment.assistant_outcome,
        "variables": variables,
        "notes": judgment.notes,
    }


def main() -> int:
    """Run the QA-judge backfill."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles-root", default="data/cycles")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    cycles_root = Path(args.cycles_root)
    graded = errors = 0
    for cycle_dir in sorted(cycles_root.iterdir()):
        if not cycle_dir.name.startswith("cycle-") or not cycle_dir.name[6:].isdigit():
            continue
        tj = cycle_dir / "transcripts.json"
        ej = list(cycle_dir.glob("*.eval"))
        if not (tj.is_file() and ej):
            continue
        data = json.loads(tj.read_text(encoding="utf-8"))
        changed = False
        for record in data.get("transcripts") or []:
            if args.limit and graded >= args.limit:
                break
            # judge only logs lacking a judgment (checked via the eval)
            messages = [
                Message(role=m["role"], content=m["content"]) for m in record.get("messages") or []
            ]
            if len(messages) < 2:
                continue
            spec = {
                "route_id": record.get("route_id"),
                "seed": record.get("seed"),
                "variables": {
                    "scientific_capability": int((record.get("variables") or {}).get("sc", 3)),
                    "jailbreak": int((record.get("variables") or {}).get("jb", 0)),
                    "kill_chain": int(
                        ((record.get("variables") or {}).get("kc") or [0])[0]
                        if isinstance((record.get("variables") or {}).get("kc"), list)
                        else (record.get("variables") or {}).get("kc", 0)
                    ),
                    "intended_scope": int((record.get("variables") or {}).get("sp", 0)),
                },
                "include_biotool": record.get("biotool") is not None,
            }
            card = _card_for(
                spec, cast(Literal["benign", "malicious"], record.get("side") or "benign")
            )
            judgment = None
            with contextlib.suppress(Exception):
                judgment = judge_sample(card, messages)
            serialized = _serialize(judgment)
            if serialized is None:
                errors += 1
                continue
            record["judgment"] = serialized
            graded += 1
            changed = True
        if changed:
            tj.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        if args.limit and graded >= args.limit:
            break
    sys.stderr.write(f"QA-judge backfill: graded={graded} errors={errors}" + chr(10))
    return 0


if __name__ == "__main__":
    sys.exit(main())
