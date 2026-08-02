"""Data shapes for actor cards and card pairs.

An actor card contains everything needed to run one side of an evaluation:
the objective, the variable assignment, the selected agent (or none, for
agentless routes), the route it is grounded in, the assembled prompt, and a
provenance hash. A card pair is the matched malicious and benign cards
produced from the same inputs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base model that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid")


class VariableAssignment(StrictModel):
    """The variables both sides of a pair share.

    Attributes:
        scientific_capability: The actor's capability level, 1 to 5.
        jailbreak: The evasion level, 0 to 2.
        kill_chain: One kill-chain position, 0 to 7.
        intended_scope: The targeting scope, 0 to 3.
    """

    scientific_capability: int = Field(ge=1, le=5)
    jailbreak: int = Field(ge=0, le=2)
    kill_chain: int = Field(ge=0, le=7)
    intended_scope: int = Field(ge=0, le=3)


class AgentRef(StrictModel):
    """A pathogen selected from the unified biological agent list.

    Attributes:
        high_risk: Whether the entry sits on the high-risk list.
        tags: Constraint tags (for example "mammal-infecting") used by route
            selectors.
    """

    id: str
    canonical_name: str
    agent_class: str
    high_risk: bool
    transmissibility: int
    virulence: int
    tags: list[str]
    aliases: list[str] = []


class BioToolRef(StrictModel):
    """A route-compatible simulated bio-tool or database."""

    id: str
    canonical_name: str
    kind: Literal["biotool", "database"]
    category_ids: list[str]
    source_ids: list[str]


class RouteRef(StrictModel):
    """The BioTIER route a card is grounded in.

    Attributes:
        category_text: The route's policy category text, quoted verbatim.
        agent_category_ref: Reference into biological_agent_list.agent_categories, or
            None for agentless routes.
        requires_agent: Whether the route selects a biological agent.
    """

    id: str
    set_name: str
    theme: str
    category_text: str
    applicability_label: str
    delivery: str | None
    agent_category_ref: str | None
    requires_agent: bool
    tool_category_ids: list[str]


class ActorCard(StrictModel):
    """One actor card: identity, private objective, and grounded guidance.

    Attributes:
        objective: The actor's private goal for the run.
        agent: The selected biological agent, or None for agentless routes.
        guidance: Verbatim guide blocks for the card's chosen levels, keyed by
            variable name. Malicious cards with jailbreak >= 1 also carry the
            selected technique instruction under the ``jailbreak`` key.
        user_prompt: The assembled private instruction prompt.
        source_hash: SHA-256 over every resolved input, the side, and the
            objective.
    """

    side: Literal["benign", "malicious"]
    objective: str
    variables: VariableAssignment
    agent: AgentRef | None
    biotool: BioToolRef | None
    route: RouteRef
    jailbreak_method: str
    workplace: str
    guidance: dict[str, str]
    user_prompt: str
    source_hash: str


class ActorCardPair(StrictModel):
    """A benign card and a malicious card compiled from the same inputs.

    Attributes:
        shared_hash: SHA-256 over the inputs both sides share: route,
            variables, agent, workplace, and seed.
    """

    pair_id: str
    benign: ActorCard
    malicious: ActorCard
    shared_hash: str
