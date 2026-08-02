"""Deterministic simulated bio-tool/database selection for one route."""

from __future__ import annotations

import random
from typing import Any

from astral.cards.grounding import Grounding


def _route_categories(route: dict[str, Any]) -> set[str]:
    """Return the BioTIER tool categories permitted by one route."""
    association = route.get("tool_association") or {}
    return {str(category) for category in association.get("allowed_category_ids") or []}


def _active(entry: dict[str, Any]) -> bool:
    """Return whether an entry is selectable in simulated conversation context."""
    return bool(entry.get("active", False))


def _validate_categories(grounding: Grounding, route: dict[str, Any], categories: set[str]) -> None:
    """Fail closed when a route references an unmapped BioTIER category."""
    unknown = categories - set(grounding.biotool_categories)
    if unknown:
        raise ValueError(
            f"route {route['id']} references unknown tool categories: {sorted(unknown)}"
        )


def _candidates(
    grounding: Grounding, route: dict[str, Any], categories: set[str]
) -> list[dict[str, Any]]:
    """Return stable-id-sorted active entries compatible with a route."""
    candidates = [
        entry
        for entry in grounding.biotools.values()
        if _active(entry)
        and categories & {str(category) for category in entry.get("category_ids") or []}
    ]
    if not candidates:
        raise ValueError(f"no active bio-tool or database satisfies route {route['id']}")
    return sorted(candidates, key=lambda entry: str(entry["id"]))


def select_biotool(
    grounding: Grounding, route: dict[str, Any], tool_id: str | None, seed: int
) -> dict[str, Any] | None:
    """Select one permitted tool/database, validate an explicit id, or return None.

    A route with no ``allowed_category_ids`` receives no selected tool and
    rejects explicit tool ids. Selection is deterministic and represents only
    simulated conversation context; it does not execute a tool or grant access
    to a tool account, API, database, or laboratory.
    """
    categories = _route_categories(route)
    if not categories:
        if tool_id is not None:
            raise ValueError(f"route {route['id']} permits no bio-tool or database")
        return None
    _validate_categories(grounding, route, categories)
    candidates = _candidates(grounding, route, categories)
    if tool_id is not None:
        entry = grounding.biotools.get(tool_id)
        if entry is None:
            raise ValueError(f"unknown biotool_id: {tool_id}")
        if entry not in candidates:
            raise ValueError(f"biotool {tool_id} does not satisfy route {route['id']}")
        return entry
    rng = random.Random(f"biotool_database|{route['id']}|{seed}")  # noqa: S311
    return candidates[rng.randrange(len(candidates))]
