"""Load the vendored ground-truth files.

Five files under ``assets/grounding`` provide the data every downstream stage
reads: the BioTIER routing registry, the variable roleplay lookup, the unified
biological agent list (with agent categories and fixed menus), the jailbreak
technique lookup, and the simulated bio-tool/database lookup. Files are loaded
byte-complete; their hashes are pinned in the test suite.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "grounding"


@dataclass(frozen=True)
class Grounding:
    """Parsed ground truth, ready for lookups.

    Attributes:
        routes: BioTIER routes by route id.
        set_policies: Set-level policies (for example the RB benign-only flag).
        agents: Pathogen directory entries by agent id.
        agent_categories: Category definitions by category ref, each with a
            set of agent classes.
        fixed_menus: Fixed menu definitions by menu ref, each with a stable
            list of agent ids.
        tag_vocabulary: The declared tag vocabulary used by route selectors.
        variables: Roleplay instructions by variable key and level number.
        jailbreak_levels: Jailbreak techniques by level number.
        biotool_categories: Bio-tool categories by stable category id.
        biotools: Bio-tool/database entries by stable tool id.
    """

    routes: dict[str, dict[str, Any]]
    set_policies: dict[str, dict[str, Any]]
    agents: dict[str, dict[str, Any]]
    agent_categories: dict[str, dict[str, Any]]
    fixed_menus: dict[str, dict[str, Any]]
    tag_vocabulary: set[str]
    variables: dict[str, dict[str, Any]]
    jailbreak_levels: dict[int, dict[str, Any]]
    biotool_categories: dict[str, dict[str, Any]]
    biotools: dict[str, dict[str, Any]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_hashes(root: Path | None = None) -> dict[str, str]:
    """Hash every ground-truth file for integrity checks.

    Args:
        root: Directory containing the ground-truth files. Defaults to the
            packaged assets directory.

    Returns:
        A mapping of file name to SHA-256 hex digest.
    """
    root = root or ASSETS
    return {p.name: _sha256(p) for p in sorted(root.iterdir()) if p.is_file()}


def resolve_route(grounding: Grounding, route_id: str) -> dict[str, Any]:
    """Return the route row, or raise a clear error.

    Args:
        grounding: The loaded ground truth.
        route_id: The BioTIER route id to look up.

    Returns:
        The route record.

    Raises:
        ValueError: If the route id is unknown.
    """
    route = grounding.routes.get(route_id)
    if route is None:
        raise ValueError(f"unknown route_id: {route_id} ({len(grounding.routes)} routes available)")
    return route


def variable_instruction(grounding: Grounding, key: str, level: int) -> dict[str, Any]:
    """Resolve one variable level to its roleplay instruction.

    Args:
        grounding: The loaded ground truth.
        key: The lookup key, e.g. "scientific_capability_levels".
        level: The selected level number.

    Returns:
        The level entry with ``label`` and ``actor_instruction``.

    Raises:
        ValueError: If the variable or level is unmapped.
    """
    variable = grounding.variables.get(key) or {}
    entry = (variable.get("levels") or {}).get(level)
    if entry is None:
        raise ValueError(f"unmapped roleplay level: {key} level {level}")
    return dict(entry)


def jailbreak_techniques(grounding: Grounding, level: int) -> list[dict[str, Any]]:
    """Return the technique list for a jailbreak level, ordered by id.

    Args:
        grounding: The loaded ground truth.
        level: The jailbreak level (1 or 2).

    Returns:
        The techniques, sorted by id for stable seeded draws.

    Raises:
        ValueError: If the level has no technique list.
    """
    entry = grounding.jailbreak_levels.get(level)
    if entry is None:
        raise ValueError(f"unmapped jailbreak level: {level}")
    return sorted(entry.get("techniques") or [], key=lambda t: str(t.get("id")))


def _load_agent_list(root: Path) -> dict[str, Any]:
    """Parse the unified biological agent list into a dict."""
    return yaml.safe_load((root / "biological_agent_list.yaml").read_text(encoding="utf-8")) or {}


def _build_agents(pathogens: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(e["id"]): e for e in pathogens.get("entries") or []}


def _build_categories(pathogens: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(k): dict(v or {}) for k, v in (pathogens.get("agent_categories") or {}).items()}


def _build_menus(pathogens: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(k): dict(v or {}) for k, v in (pathogens.get("fixed_menus") or {}).items()}


def _build_set_policies(routing: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(k): dict(v or {}) for k, v in (routing.get("set_policies") or {}).items()}


def _load_variables(root: Path) -> dict[str, dict[str, Any]]:
    """Parse the variable roleplay lookup into a key-indexed map."""
    doc = yaml.safe_load((root / "variable_roleplay_guide.yaml").read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for key, variable in (doc.get("variables") or {}).items():
        levels = {
            int(level): dict(entry) for level, entry in (variable.get("levels") or {}).items()
        }
        out[str(key)] = {"label": str(variable.get("label") or key), "levels": levels}
    return out


def _load_jailbreak_levels(root: Path) -> dict[int, dict[str, Any]]:
    """Parse the jailbreak technique lookup into a level-indexed map."""
    doc = yaml.safe_load((root / "jailbreak_list.yaml").read_text(encoding="utf-8"))
    return {int(level): dict(entry) for level, entry in (doc.get("levels") or {}).items()}


def _load_biotool_catalog(root: Path) -> dict[str, Any]:
    """Parse the simulated BioTIER tool/database lookup."""
    path = root / "biotool_and_database_list.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _build_biotool_categories(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index tool categories by their stable ids."""
    return {str(e["id"]): e for e in catalog.get("categories") or []}


def _build_biotools(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index tool/database entries by their stable ids."""
    return {str(e["id"]): e for e in catalog.get("entries") or []}


@lru_cache(maxsize=4)
def load_grounding(root: Path | None = None) -> Grounding:
    """Load every ground-truth file.

    Args:
        root: Directory containing the ground-truth files. Defaults to the
            packaged assets directory.

    Returns:
        The parsed ground truth, ready for lookups.

    Examples:
        >>> grounding = load_grounding()
        >>> len(grounding.routes)
        98
    """
    root = root or ASSETS
    routing = yaml.safe_load((root / "biotier_routing.yaml").read_text(encoding="utf-8")) or {}
    routes = {str(r["id"]): r for r in routing.get("routes") or []}
    pathogens = _load_agent_list(root)
    tag_vocabulary = {str(t) for t in pathogens.get("tag_vocabulary") or []}
    biotool_catalog = _load_biotool_catalog(root)
    return Grounding(
        routes=routes,
        set_policies=_build_set_policies(routing),
        agents=_build_agents(pathogens),
        agent_categories=_build_categories(pathogens),
        fixed_menus=_build_menus(pathogens),
        tag_vocabulary=tag_vocabulary,
        variables=_load_variables(root),
        jailbreak_levels=_load_jailbreak_levels(root),
        biotool_categories=_build_biotool_categories(biotool_catalog),
        biotools=_build_biotools(biotool_catalog),
    )
