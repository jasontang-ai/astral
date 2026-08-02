"""Merge regen transcripts into a cycle's samples so repacks keep regen logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inspect_ai.log import EvalSample
from inspect_ai.model import ChatMessageAssistant, ChatMessageSystem, ChatMessageUser

_KEYS = (
    "cycle",
    "route_id",
    "family",
    "side",
    "seed",
    "status",
    "turns",
    "firewall",
    "engine",
    "variables",
    "agent",
    "agentless",
    "jailbreak_method",
    "biotool",
    "models",
    "biotier_compliance",
    "biotier_trajectory",
    "kill_chain_stage",
    "reasoning_effort",
    "biotier_refuse_expected",
    "user_prompt",
    "objective",
)


def _sample_from_record(record: dict[str, Any]) -> EvalSample:
    """Build an EvalSample from a transcripts.json record."""
    cls = {"user": ChatMessageUser, "assistant": ChatMessageAssistant}
    messages = [
        cls.get(m.get("role"), ChatMessageSystem)(content=str(m.get("content") or ""))
        for m in record.get("messages") or []
    ]
    metadata = {k: record.get(k) for k in _KEYS if record.get(k) is not None}
    return EvalSample(
        id=str(record.get("id") or ""),
        epoch=1,
        input="",
        target="",
        messages=messages,
        metadata=metadata,
    )


def _regen_samples(root_path: Path, samples: list[EvalSample]) -> list[EvalSample]:
    """Collect samples from sibling <cycle>-*regen* dirs not already present.

    Args:
        root_path: The original cycle run dir.
        samples: The already-collected samples (for id dedup).

    Returns:
        New samples from the regen dirs.
    """
    seen_ids = {str(getattr(sm, "id", "")) for sm in samples}
    parent = root_path.parent
    out: list[EvalSample] = []
    if not parent.is_dir():
        return out
    for regen_dir in sorted(parent.glob(f"{root_path.name}-*regen*")):
        tj = regen_dir / "transcripts.json"
        if not tj.is_file():
            continue
        try:
            regen_data = json.loads(tj.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for record in regen_data.get("transcripts") or []:
            rid = str(record.get("id") or "")
            if rid and rid not in seen_ids:
                seen_ids.add(rid)
                out.append(_sample_from_record(record))
    return out
