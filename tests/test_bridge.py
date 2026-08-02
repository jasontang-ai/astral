"""The Bloom bridge: cards become Bloom behaviors, proven by their loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from astral import VariableAssignment, make_actor_cards
from astral.bridge import card_to_seed, pair_to_behavior, write_behavior_dir

ROUTE = "ca.immune_escape.01"
VARIABLES = VariableAssignment(scientific_capability=3, jailbreak=1, kill_chain=1, intended_scope=1)


def _pair():
    return make_actor_cards(route_id=ROUTE, variables=VARIABLES, seed=7)


def test_card_maps_to_seed_verbatim() -> None:
    card = _pair().malicious
    scenario = card_to_seed(card)
    assert card.user_prompt in scenario.seed
    assert scenario.variation is None
    assert scenario.name.endswith("malicious")


def test_pair_becomes_base_scenario_plus_intent_variation() -> None:
    behavior = pair_to_behavior(_pair())
    assert behavior.description == _pair().malicious.route.category_text
    assert len(behavior.scenarios) == 2
    base, benign = behavior.scenarios
    assert base.variation is None
    assert benign.variation == "intent"
    assert behavior.variations["intent"]
    names = [d.name for d in behavior.dimensions]
    assert "v41_jailbreak" in names
    assert "v41_kill_chain" in names


def test_emitted_directory_round_trips_through_bloom_loader(tmp_path: Path) -> None:
    pytest.importorskip("petri_bloom")
    from petri_bloom._behavior.behavior import behavior as load_behavior

    behavior = pair_to_behavior(_pair())
    write_behavior_dir(behavior, tmp_path / behavior.name)
    loaded = load_behavior(path=tmp_path / behavior.name)

    assert loaded.description == behavior.description
    assert len(loaded.scenarios) == len(behavior.scenarios)
    seeds_by_name = {s.name: s for s in loaded.scenarios}
    pair = _pair()
    mal_seed = seeds_by_name[base_name(pair.malicious)].seed
    ben_seed = seeds_by_name[base_name(pair.benign)].seed
    assert pair.malicious.user_prompt.strip() in mal_seed
    assert pair.benign.user_prompt.strip() in ben_seed
    assert "Conversation completion" in mal_seed
    assert "Conversation completion" in ben_seed
    assert seeds_by_name[base_name(pair.benign)].variation == "intent"
    loaded_dims = {d.name for d in loaded.dimensions}
    assert "v41_scientific_capability" in loaded_dims
    assert "v41_jailbreak" in loaded_dims
    assert "v41_kill_chain" in loaded_dims


def base_name(card) -> str:
    return f"{card.route.id.replace('.', '_')}_{card.side}"


def test_emission_is_deterministic(tmp_path: Path) -> None:
    behavior = pair_to_behavior(_pair())
    first = tmp_path / "a" / behavior.name
    second = tmp_path / "b" / behavior.name
    write_behavior_dir(behavior, first)
    write_behavior_dir(behavior, second)
    files_a = sorted(p.relative_to(first) for p in first.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(second) for p in second.rglob("*") if p.is_file())
    assert files_a == files_b
    for rel in files_a:
        assert (first / rel).read_bytes() == (second / rel).read_bytes()


def test_auditor_seed_includes_soft_stop_and_tool_query_contract() -> None:
    from astral import VariableAssignment, make_actor_card
    from astral.bridge.bloom import card_to_seed

    card = make_actor_card(
        side="malicious",
        route_id="ca.immune_escape.03",
        variables=VariableAssignment(
            scientific_capability=3, jailbreak=1, kill_chain=1, intended_scope=1
        ),
        seed=3,
    )
    seed = card_to_seed(card).seed
    assert "soft stop" in seed.lower() or "Conversation completion" in seed
    assert "attachment://" in seed
    assert card.user_prompt in seed


def test_every_routing_tool_resolves_output_card() -> None:
    """All 105 grounded tools resolve a non-default output card via category."""
    import yaml

    from astral.cards.contracts import BioToolRef
    from astral.cards.output_cards import load_output_cards, resolve_output_card

    routing = yaml.safe_load(
        __import__("pathlib")
        .Path("src/astral/assets/grounding/biotool_and_database_list.yaml")
        .read_text(encoding="utf-8")
    )
    cards = load_output_cards()
    default_format = str((cards.get("default") or {}).get("output_format") or "")
    unresolved = []
    for line in routing.get("tools") or []:
        ref = BioToolRef(
            id=str(line["id"]),
            canonical_name=str(line["canonical_name"]),
            kind=line["kind"],
            category_ids=[str(c) for c in line.get("category_ids") or []],
            source_ids=[],
        )
        card = resolve_output_card(ref, cards)
        if str(card.get("output_format") or "") == default_format:
            unresolved.append(ref.id)
    assert unresolved == []
