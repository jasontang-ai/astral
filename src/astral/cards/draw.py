"""Seeded draws from the routing registry.

The draw functions sample one coherent assignment from the ground truth: a
route in a seeded random order, then one value per variable from that route's
allowed space. Every field is drawn from the route's own list, so jailbreak
values honor the per-route RB safety invariants without a global fallback.
Everything is deterministic; the same seed and index always produce the same
draw.
"""

from __future__ import annotations

import random
from typing import Any

from astral.cards.contracts import VariableAssignment
from astral.cards.grounding import Grounding, load_grounding, resolve_route


def _allowed_ints(route: dict[str, Any], field: str) -> list[int]:
    """Return the sorted list of int values a route allows for ``field``."""
    values = (route.get("allowed_values") or {}).get(field)
    if not values:
        raise ValueError(f"route {route['id']} has no allowed values for {field}")
    return sorted(int(v) for v in values)


def allowed_jailbreak_levels(route: dict[str, Any]) -> list[int]:
    """Return the route's allowed jail_breaking levels, sorted."""
    return _allowed_ints(route, "jail_breaking")


def route_order(*, seed: int, grounding: Grounding | None = None) -> list[str]:
    """Return all route ids in a seeded random order.

    Args:
        seed: Seed for the shuffle.
        grounding: Pre-loaded ground truth. Loaded on first use when omitted.

    Returns:
        All route ids in a random order fixed by the seed.

    Examples:
        >>> len(route_order(seed=3))
        98
    """
    grounding = grounding or load_grounding()
    ids = sorted(grounding.routes)
    random.Random(seed).shuffle(ids)  # noqa: S311  # reproducible ordering
    return ids


def draw_assignment_for_route(
    route_id: str, *, seed: int, index: int = 0, grounding: Grounding | None = None
) -> VariableAssignment:
    """Draw one value per variable from a route's allowed space.

    Args:
        route_id: The BioTIER route to draw from.
        seed: Seed for the draw.
        index: Draw position in the seeded route order; part of the seed so
            repeated cycles draw different values.
        grounding: Pre-loaded ground truth. Loaded on first use when omitted.

    Returns:
        A variable assignment whose values are all legal on the route.

    Raises:
        ValueError: If the route id is unknown or the route lacks allowed
            values for a variable.

    Examples:
        >>> variables = draw_assignment_for_route("ca.immune_escape.01", seed=3)
    """
    grounding = grounding or load_grounding()
    route = resolve_route(grounding, route_id)
    rng = random.Random(f"{route_id}|{seed}|{index}")  # noqa: S311  # reproducible sampling
    scope_levels = [v for v in _allowed_ints(route, "intended_scope_levels") if v >= 1]
    return VariableAssignment(
        scientific_capability=rng.choice(_allowed_ints(route, "scientific_capability_levels")),
        jailbreak=rng.choice(allowed_jailbreak_levels(route)),
        kill_chain=rng.choice(_allowed_ints(route, "kill_chain")),
        intended_scope=rng.choice(scope_levels or _allowed_ints(route, "intended_scope_levels")),
    )


def draw_assignment(
    *, seed: int, index: int = 0, grounding: Grounding | None = None
) -> tuple[str, VariableAssignment]:
    """Draw the route at ``index`` in the seeded order, plus its variables.

    Args:
        seed: Seed for the route order and the variable draw.
        index: Position in the seeded route order.
        grounding: Pre-loaded ground truth. Loaded on first use when omitted.

    Returns:
        The drawn route id and a legal variable assignment for it.

    Examples:
        >>> route_id, variables = draw_assignment(seed=3, index=0)
    """
    grounding = grounding or load_grounding()
    order = route_order(seed=seed, grounding=grounding)
    candidates = [
        rid
        for rid in order
        if any(
            v >= 1
            for v in (grounding.routes[rid].get("allowed_values") or {}).get(
                "intended_scope_levels", []
            )
        )
    ]
    route_id = (candidates or order)[index % len(candidates or order)]
    return route_id, draw_assignment_for_route(
        route_id, seed=seed, index=index, grounding=grounding
    )
