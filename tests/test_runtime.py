"""Stage 2: the grounded deterministic control."""

from __future__ import annotations

import json
from pathlib import Path

from astral import VariableAssignment, make_actor_cards
from astral.runtime import run_card, run_pair
from astral.runtime.contracts import DEFAULT_TURN_CAP

ROUTE = "ca.immune_escape.01"
VARIABLES = VariableAssignment(scientific_capability=3, jailbreak=1, kill_chain=1, intended_scope=1)


def _pair():
    return make_actor_cards(route_id=ROUTE, variables=VARIABLES, seed=7)


def test_same_card_and_seed_give_identical_artifacts(tmp_path: Path) -> None:
    card = _pair().malicious
    first = tmp_path / "a"
    second = tmp_path / "b"
    run_card(card, seed=3, out_dir=first)
    run_card(card, seed=3, out_dir=second)
    for name in ("visible.jsonl", "card.json", "run.json"):
        files_a = sorted(p.name for p in first.rglob(name))
        files_b = sorted(p.name for p in second.rglob(name))
        assert files_a == files_b == [name]
        assert next(first.rglob(name)).read_bytes() == next(second.rglob(name)).read_bytes()


def test_every_turn_lists_its_grounding_sources() -> None:
    record = run_card(_pair().malicious)
    assert len(record.provenance) == record.turns == DEFAULT_TURN_CAP
    grounded = [p for p in record.provenance if p.sources]
    assert grounded, "turns must trace to ground-truth fields"
    opening = record.provenance[0]
    assert "route.category_text" in opening.sources
    assert "agent" in opening.sources


def test_agentless_run_handles_missing_agent() -> None:
    agentless_pair = make_actor_cards(
        route_id="ca.weaponization_general.01",
        variables=VariableAssignment(
            scientific_capability=3, jailbreak=1, kill_chain=1, intended_scope=1
        ),
        seed=7,
    )
    assert agentless_pair.malicious.agent is None
    record = run_card(agentless_pair.malicious)
    assert record.turns == DEFAULT_TURN_CAP
    sources = {s for p in record.provenance for s in p.sources}
    assert "route.category_text" in sources
    assert "agent" not in sources


def test_jailbreak_turn_only_when_level_positive() -> None:
    pair = _pair()
    malicious = run_card(pair.malicious)
    benign = run_card(pair.benign)
    jb_turns = [p.turn for p in malicious.provenance if "variables.jailbreak" in p.sources]
    assert jb_turns, "malicious JB=1 run must include the jailbreak move"
    assert not [p.turn for p in benign.provenance if "variables.jailbreak" in p.sources]


def test_pair_runs_share_settings_and_record_pair_id() -> None:
    benign, malicious = run_pair(_pair(), seed=11)
    assert benign.pair_id == malicious.pair_id
    assert benign.side == "benign"
    assert malicious.side == "malicious"
    assert benign.engine == "deterministic-fixture-v1"
    assert malicious.engine == "deterministic-fixture-v1"


def test_transcript_is_well_formed(tmp_path: Path) -> None:
    card = _pair().malicious
    run_card(card, out_dir=tmp_path)
    visible = next(tmp_path.rglob("visible.jsonl"))
    rows = [json.loads(line) for line in visible.read_text().splitlines()]
    assert [row["role"] for row in rows] == ["user", "assistant"] * (DEFAULT_TURN_CAP // 2)
    run = json.loads(next(tmp_path.rglob("run.json")).read_text())
    assert run["card_hash"] == card.source_hash


def test_default_turn_cap_is_ten() -> None:
    from astral.bridge.run import BloomHarness
    from astral.runtime.contracts import DEFAULT_TURN_CAP

    record = run_card(_pair().malicious)
    assert DEFAULT_TURN_CAP == 10
    assert record.turns == DEFAULT_TURN_CAP
    assert BloomHarness(auditor="a", target="b").max_turns == DEFAULT_TURN_CAP // 2
