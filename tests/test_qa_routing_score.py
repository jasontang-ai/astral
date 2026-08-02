"""Expected-cost routing: forced routes, cost ordering, regen decay."""

from __future__ import annotations

from astral.qa.routing_score import C_HUMAN, RegenSuccessModel, route_side

HI_CARD = {
    "variables": {"scientific_capability": 3, "jailbreak": 2, "kill_chain": 4, "intended_scope": 2},
    "agent": {"transmissibility": 3, "virulence": 3},
}
LO_CARD = {
    "variables": {"scientific_capability": 1, "jailbreak": 0, "kill_chain": 0, "intended_scope": 0}
}


def test_clean_side_ships_when_ship_is_cheapest() -> None:
    d = route_side(
        HI_CARD,
        judge_agreement={"outcome_match": True, "variable_match_rate": 1.0},
        judgment={"variables": {"jb": {"confidence": 0.95}}},
    )
    assert d.route == "ship"
    assert d.expected_ship < C_HUMAN


def test_fixable_drift_routes_to_regen() -> None:
    d = route_side(
        HI_CARD,
        judge_agreement={"outcome_match": True, "variable_match_rate": 0.5},
        diagnosis={"root_cause": "target_drift", "confidence": "high"},
    )
    assert d.route == "regen"
    assert d.regen_success is not None
    assert d.regen_success > 0.5


def test_judge_unstable_forces_human_review() -> None:
    d = route_side(
        HI_CARD,
        judge_agreement={"outcome_match": False, "variable_match_rate": 0.25},
        diagnosis={"root_cause": "judge_unstable", "confidence": "low"},
    )
    assert d.route == "human_review"


def test_valid_refusal_ships_as_data() -> None:
    d = route_side(HI_CARD, diagnosis={"root_cause": "valid_refusal"})
    assert d.route == "ship"


def test_regen_attempts_decay_success_until_human() -> None:
    model = RegenSuccessModel()
    first = route_side(
        HI_CARD,
        judge_agreement={"outcome_match": True, "variable_match_rate": 0.5},
        diagnosis={"root_cause": "elicitation_failure", "confidence": "high"},
        regen_attempt=0,
        success_model=model,
    )
    exhausted = route_side(
        HI_CARD,
        judge_agreement={"outcome_match": True, "variable_match_rate": 0.5},
        diagnosis={"root_cause": "elicitation_failure", "confidence": "high"},
        regen_attempt=2,
        success_model=model,
    )
    assert first.route == "regen"
    assert exhausted.route == "human_review"
    assert (exhausted.regen_success or 1) < (first.regen_success or 0)


def test_high_risk_dispute_outranks_low_risk() -> None:
    hi = route_side(
        HI_CARD,
        judge_agreement={"outcome_match": False, "variable_match_rate": 0.5},
        diagnosis={"confidence": "high"},
    )
    lo = route_side(
        LO_CARD,
        judge_agreement={"outcome_match": False, "variable_match_rate": 0.5},
        diagnosis={"confidence": "high"},
    )
    assert hi.expected_ship > lo.expected_ship


def test_acceptance_failure_never_ships() -> None:
    """Deterministic gate failures override cost routing (atomic gates rule)."""
    d = route_side(
        HI_CARD,
        judge_agreement={"outcome_match": True, "variable_match_rate": 1.0},
        judgment={"variables": {"jb": {"confidence": 0.95}}},
        diagnosis={"acceptance": {"promotable": False, "reasons": ["coverage_incomplete"]}},
    )
    assert d.route != "ship"


def test_calibration_miss_rate_recalibrates_wrong() -> None:
    from astral.qa.routing_score import _blend_calibration

    blended, used = _blend_calibration(0.10, 0.30)
    assert used == 0.30
    assert blended > 0.10  # empirical 30% miss rate raises the estimate
    unchanged, unused = _blend_calibration(0.10, None)
    assert unused is None
    assert unchanged == 0.10
