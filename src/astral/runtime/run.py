"""Execute actor cards into transcripts without model calls.

``run_card`` alternates user and assistant turns for a fixed number of turns
and writes the visible transcript, the card, and the run record.
``run_pair`` executes both sides of a card pair under identical settings.
All outputs are deterministic: the same card and seed produce identical
artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

from astral.cards.contracts import ActorCard, ActorCardPair
from astral.runtime.contracts import (
    DEFAULT_TURN_CAP,
    Message,
    RunRecord,
    TurnProvenance,
    VisibleLog,
)
from astral.runtime.engines import assistant_reply, user_turn

ENGINE = "deterministic-fixture-v1"


def _write_json(path: Path, payload: object) -> None:
    """Write one JSON file with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def run_card(
    card: ActorCard,
    *,
    turns: int = DEFAULT_TURN_CAP,
    seed: int = 0,
    out_dir: str | Path | None = None,
) -> RunRecord:
    """Execute one card into a transcript and record where every turn came from.

    Args:
        card: The actor card to execute.
        turns: Total number of messages, user and assistant combined.
        seed: Seed recorded in the run record.
        out_dir: Directory for artifacts. Nothing is written when omitted.

    Returns:
        The run record, with per-turn provenance.

    Raises:
        ValueError: If ``turns`` is below 2.
    """
    if turns < 2:
        raise ValueError("turns must be at least 2")
    log_id = f"{card.route.id}-{card.side}-t{turns}-s{seed}"
    messages: list[Message] = []
    provenance: list[TurnProvenance] = []
    for index in range(1, turns + 1):
        if index % 2 == 1:
            n = (index + 1) // 2
            content, sources = user_turn(card, n, (turns + 1) // 2)
            messages.append(Message(role="user", content=content))
            provenance.append(TurnProvenance(turn=index, role="user", sources=sources))
        else:
            n = index // 2
            jb_turn = card.variables.jailbreak >= 1 and n == max(2, ((turns + 1) // 2) - 2)
            content, sources = assistant_reply(card, jb_turn)
            messages.append(Message(role="assistant", content=content))
            provenance.append(TurnProvenance(turn=index, role="assistant", sources=sources))
    visible = VisibleLog(id=log_id, messages=messages)
    record = RunRecord(
        log_id=log_id,
        card_hash=card.source_hash,
        pair_id=None,
        side=card.side,
        engine=ENGINE,
        seed=seed,
        turns=turns,
        provenance=provenance,
    )
    if out_dir is not None:
        directory = Path(out_dir) / log_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "visible.jsonl").write_text(
            "".join(
                json.dumps(m.model_dump(mode="json"), sort_keys=True) + "\n"
                for m in visible.messages
            ),
            encoding="utf-8",
        )
        _write_json(directory / "card.json", card.model_dump(mode="json"))
        _write_json(directory / "run.json", record.model_dump(mode="json"))
    return record


def run_pair(
    pair: ActorCardPair,
    *,
    turns: int = DEFAULT_TURN_CAP,
    seed: int = 0,
    out_dir: str | Path | None = None,
) -> tuple[RunRecord, RunRecord]:
    """Execute both sides of a pair under the same settings.

    Args:
        pair: The matched actor-card pair.
        turns: Total number of messages per side.
        seed: Seed recorded in both run records.
        out_dir: Directory for artifacts. Nothing is written when omitted.

    Returns:
        The benign and malicious run records, each linked to the pair id.
    """
    benign = run_card(pair.benign, turns=turns, seed=seed, out_dir=out_dir)
    malicious = run_card(pair.malicious, turns=turns, seed=seed, out_dir=out_dir)
    return (
        benign.model_copy(update={"pair_id": pair.pair_id}),
        malicious.model_copy(update={"pair_id": pair.pair_id}),
    )
