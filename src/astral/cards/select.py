"""Agent selection against normalized BioTIER route constraints.

Selection resolves which agents a route permits by combining category, fixed
menu, tag, and active-status rules from the biological agent list. Agentless routes
return no agent; explicit requests are validated against the same rules and
fail closed on any unknown reference or empty pool.
"""

from __future__ import annotations

import random
from typing import Any

from astral.cards.grounding import Grounding


def _resolve_category(grounding: Grounding, route: dict[str, Any]) -> set[str]:
    """Resolve the route's agent_category_ref to a set of agent classes."""
    selector = route.get("agent_selector") or {}
    ref = selector.get("agent_category_ref")
    if not ref:
        raise ValueError(f"route {route['id']} is missing agent_category_ref")
    category = grounding.agent_categories.get(str(ref))
    if category is None:
        raise ValueError(f"route {route['id']} references unknown agent_category_ref: {ref}")
    classes = {str(c) for c in category.get("agent_classes") or []}
    if not classes:
        raise ValueError(f"agent_category_ref {ref} declares no agent_classes")
    return classes


def _resolve_menu(grounding: Grounding, route: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Resolve the route's pathogen_menu_ref to a list of directory entries.

    Returns None when the route uses no menu.
    """
    selector = route.get("agent_selector") or {}
    ref = selector.get("pathogen_menu_ref")
    if not ref:
        return None
    menu = grounding.fixed_menus.get(str(ref))
    if menu is None:
        raise ValueError(f"route {route['id']} references unknown pathogen menu: {ref}")
    entries: list[dict[str, Any]] = []
    for agent_id in menu.get("agent_ids") or []:
        entry = grounding.agents.get(str(agent_id))
        if entry is None:
            raise ValueError(f"pathogen menu {ref} lists unknown agent_id: {agent_id}")
        entries.append(entry)
    if not entries:
        raise ValueError(f"pathogen menu {ref} is empty")
    return entries


def _validate_tags(grounding: Grounding, route: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Validate required/excluded tags against the declared vocabulary."""
    selector = route.get("agent_selector") or {}
    required = {str(t) for t in selector.get("required_pathogen_tags") or []}
    excluded = {str(t) for t in selector.get("excluded_pathogen_tags") or []}
    for tag in required | excluded:
        if tag not in grounding.tag_vocabulary:
            raise ValueError(f"route {route['id']} uses unknown pathogen tag: {tag}")
    return required, excluded


def _is_active(entry: dict[str, Any]) -> bool:
    """Return True when the pathogen entry is active (default: active)."""
    status = entry.get("status")
    return status is None or str(status) == "active"


def _matches(
    entry: dict[str, Any],
    *,
    classes: set[str],
    required: set[str],
    excluded: set[str],
) -> bool:
    """Return True when the entry satisfies class, tag, and status filters."""
    if str(entry.get("agent_class")) not in classes:
        return False
    tags = {str(t) for t in entry.get("tags") or []}
    if not required <= tags:
        return False
    if excluded & tags:
        return False
    return _is_active(entry)


def _candidate_pool(grounding: Grounding, route: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the legal agents for a route, sorted for stable draws."""
    classes = _resolve_category(grounding, route)
    required, excluded = _validate_tags(grounding, route)
    menu_entries = _resolve_menu(grounding, route)
    if menu_entries is not None:
        pool = menu_entries
    else:
        pool = [e for e in grounding.agents.values() if bool(e.get("broad_eligible"))]
    filtered = [
        entry
        for entry in pool
        if _matches(entry, classes=classes, required=required, excluded=excluded)
    ]
    if not filtered:
        raise ValueError(f"no agent satisfies the selector of route {route['id']}")
    return sorted(filtered, key=lambda e: str(e["id"]))


def _requires_agent(route: dict[str, Any]) -> bool:
    """Return True when the route selects a biological agent."""
    selector = route.get("agent_selector") or {}
    return bool(selector.get("requires_pathogen_selection", True))


def _check_explicit(
    grounding: Grounding, route: dict[str, Any], entry: dict[str, Any]
) -> dict[str, Any]:
    """Validate a caller-supplied agent against the route's rules."""
    if entry not in _candidate_pool(grounding, route):
        raise ValueError(
            f"agent {entry['id']} does not satisfy the selector of route {route['id']}"
        )
    return entry


def select_agent(
    grounding: Grounding, route: dict[str, Any], agent_id: str | None, seed: int
) -> dict[str, Any] | None:
    """Pick an agent that the route allows, check a requested one, or return None.

    Agentless routes (``requires_pathogen_selection: false``) always return
    ``None``; a caller-supplied ``agent_id`` on such a route fails closed.
    Selection-enabled routes resolve the pool from the biological agent list using
    ``agent_category_ref``, any ``pathogen_menu_ref``, required and excluded
    tags, and the entry's active status. The pool is sorted by stable id
    before deterministic selection.

    Args:
        grounding: The loaded ground truth.
        route: The route record from the routing registry.
        agent_id: An explicit pathogen id, or None to select from the pool.
        seed: Seed for a deterministic pool draw.

    Returns:
        The selected directory entry, or ``None`` for agentless routes.

    Raises:
        ValueError: If the agent is unknown, off-menu, outside the selector,
            an explicit agent is supplied to an agentless route, or no
            candidate satisfies the route.
    """
    if not _requires_agent(route):
        if agent_id is not None:
            raise ValueError(f"route {route['id']} is agentless; agent_id must be omitted")
        return None
    if agent_id is not None:
        entry = grounding.agents.get(agent_id)
        if entry is None:
            raise ValueError(f"unknown agent_id: {agent_id}")
        return _check_explicit(grounding, route, entry)
    candidates = _candidate_pool(grounding, route)
    rng = random.Random(f"{route['id']}|{seed}")  # noqa: S311  # reproducible sampling
    return candidates[rng.randrange(len(candidates))]
