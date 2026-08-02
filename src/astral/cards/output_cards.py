"""Simulated-tool output cards: resolution and loading.

The cards teach the auditor what a tool's raw output looks like so fabricated
``send_tool_call_result`` content is structurally plausible. Resolution order:
per-tool card, then the card for the tool's first grounding category, then the
default card. Cards are a policy asset; pinned BioTIER grounding is untouched.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from astral.cards.contracts import BioToolRef

CARDS_PATH = Path(__file__).resolve().parents[1] / "assets" / "biotool_output_cards.yaml"


@lru_cache(maxsize=1)
def load_output_cards(path: Path | None = None) -> dict[str, Any]:
    """Load the output-cards asset (cached)."""
    data = yaml.safe_load((path or CARDS_PATH).read_text(encoding="utf-8"))
    return dict(data or {})


def _merge_card_layers(
    biotool: BioToolRef, cards: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    """Merge default, category, and per-tool card layers."""
    tools = cards.get("tools") or {}
    categories = cards.get("categories") or {}
    default = dict(cards.get("default") or {})
    tool_card = dict(tools.get(biotool.id) or {})
    category_id = tool_card.get("category") or (
        biotool.category_ids[0] if biotool.category_ids else None
    )
    category_card = dict(categories.get(str(category_id)) or {}) if category_id else {}
    return {**default, **category_card, **tool_card}, category_id


def _apply_real_example(merged: dict[str, Any]) -> None:
    """Override the approximate example with the documented real one."""
    real = merged.get("real_example")
    if isinstance(real, dict) and real.get("text"):
        merged["example_output"] = str(real.get("text") or "")
        merged["example_source"] = str(real.get("source") or "")
        merged["example_verbatim"] = bool(real.get("verbatim", False))


def resolve_output_card(biotool: BioToolRef, cards: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve the output card for one selected biotool.

    Args:
        biotool: The card's selected simulated tool/database.
        cards: Pre-loaded cards mapping; loaded from disk when omitted.

    Returns:
        The resolved card with ``output_format``, ``example_output``, and
        ``realism_notes`` keys, merged over its category card when a per-tool
        card only carries overrides.
    """
    cards = cards or load_output_cards()
    merged, category_id = _merge_card_layers(biotool, cards)
    merged["category_id"] = category_id
    merged["style_rules"] = list(cards.get("style_rules") or [])
    _apply_real_example(merged)
    return merged


def style_rules(cards: dict[str, Any] | None = None) -> list[str]:
    """Global simulation style rules from the cards asset."""
    cards = cards or load_output_cards()
    return [str(rule) for rule in cards.get("style_rules") or []]
