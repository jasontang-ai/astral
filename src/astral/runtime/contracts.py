"""Data shapes for recorded runs.

A run executes one actor card into a transcript. ``Message`` is one visible
message. ``VisibleLog`` is the complete visible transcript. ``TurnProvenance``
records which ground-truth fields a turn was assembled from. ``RunRecord``
links a run to its card, engine, seed, and per-turn provenance.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

DEFAULT_TURN_CAP = 10
# Safety ceiling for tool-bearing Bloom runs (soft stop ends earlier).
DEFAULT_AGENTIC_MAX_TURNS = 24
"""Default visible-message cap per transcript across all runtime arms.

Control and model arms count user and assistant messages together. Bloom
counts auditor turns, so its default is half the cap (about 10 visible
messages). Manifests and call sites may override per run; a dynamic policy can
later vary the cap by route or batch without changing this constant.
"""


class StrictModel(BaseModel):
    """Base model that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid")


class Message(StrictModel):
    """One message in the transcript, from the user or the assistant."""

    role: str
    content: str


class TurnProvenance(StrictModel):
    """A receipt for one turn, listing the ground-truth fields it was built from."""

    turn: int
    role: str
    sources: list[str]


class VisibleLog(StrictModel):
    """The full visible transcript of one run, and nothing else."""

    id: str
    messages: list[Message]


class RunRecord(StrictModel):
    """The receipt for one run.

    Records which card, engine, and seed produced the run, plus a provenance
    entry for every turn.

    Attributes:
        engine: Identifier of the runtime engine that produced the run.
        provenance: One entry per turn listing the ground-truth fields the
            turn was assembled from.
    """

    log_id: str
    card_hash: str
    pair_id: str | None
    side: str
    engine: str
    seed: int
    turns: int
    provenance: list[TurnProvenance]
