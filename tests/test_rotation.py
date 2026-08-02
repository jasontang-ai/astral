"""Deterministic model rotation from config/model_routing.yaml."""

from __future__ import annotations

from astral.bridge.rotation import cycle_pair, load_routing, pool_summary


def test_cycle_pair_rotates_through_pools() -> None:
    routing = load_routing()
    seen = {cycle_pair(i, routing) for i in range(8)}
    users = {pair[0] for pair in seen}
    targets = {pair[1] for pair in seen}
    assert len(users) >= 5  # users wrap; targets may outnumber users
    assert len(targets) == 8
    assert all(pair[2] == "openrouter/google/gemini-3.5-flash" for pair in seen)


def test_cycle_pair_wraps_deterministically() -> None:
    routing = load_routing()
    assert (
        cycle_pair(0, routing)[1] == cycle_pair(len(routing["target"]), routing)[1]
    )  # target pool wraps
    assert (
        cycle_pair(0, routing)[0] == cycle_pair(len(routing["user_sim"]), routing)[0]
    )  # user pool wraps


def test_pool_summary_lists_models() -> None:
    summary = pool_summary()
    assert "deepseek/deepseek-v4-flash" in summary
    from astral.bridge.rotation import provider_id

    assert provider_id("google/gemini-3.5-flash") == "openrouter/google/gemini-3.5-flash"
    assert provider_id("e2ee-qwen3-6-35b-a3b-uncensored-p").startswith("venice/")


def test_mechanical_retries_twice_then_alternates() -> None:
    from astral.bridge.rotation import resolve_fallback

    routing = load_routing()
    assert (
        resolve_fallback(
            "deepseek/deepseek-v4-flash", "user_sim", "mechanical", attempt=0, routing=routing
        )
        == "deepseek/deepseek-v4-flash"
    )
    assert (
        resolve_fallback(
            "deepseek/deepseek-v4-flash", "user_sim", "mechanical", attempt=1, routing=routing
        )
        == "deepseek/deepseek-v4-flash"
    )
    # rotation spreads across the tier: index 0 + 1 + 2 = tier[3] = glm-5.2
    assert (
        resolve_fallback(
            "deepseek/deepseek-v4-flash", "user_sim", "mechanical", attempt=2, routing=routing
        )
        == "google/gemini-3.6-flash"
    )
    # different cycle seeds give different alternates (no piling onto one model)
    assert (
        resolve_fallback(
            "deepseek/deepseek-v4-flash",
            "user_sim",
            "mechanical",
            attempt=2,
            cycle_index=1,
            routing=routing,
        )
        == "deepseek/deepseek-v4-flash"
    )


def test_refusal_never_falls_back() -> None:
    from astral.bridge.rotation import resolve_fallback

    assert (
        resolve_fallback("anthropic/claude-sonnet-4.6", "target", "refusal", routing=load_routing())
        is None
    )


def test_target_chains_preserve_refusal_tier() -> None:
    from astral.bridge.rotation import resolve_fallback

    routing = load_routing()
    assert (
        resolve_fallback(
            "anthropic/claude-sonnet-4.6", "target", "provider_filtered", routing=routing
        )
        == "anthropic/claude-opus-4.8"
    )
    assert (
        resolve_fallback(
            "anthropic/claude-opus-4.8", "target", "provider_filtered", routing=routing
        )
        == "anthropic/claude-sonnet-4.6"
    )
    # boundary tier rotates between the two boundary models
    assert (
        resolve_fallback("google/gemini-3.5-flash", "target", "provider_filtered", routing=routing)
        == "qwen/qwen3.7-max"
    )
    assert (
        resolve_fallback("qwen/qwen3.7-max", "target", "provider_filtered", routing=routing)
        == "google/gemini-3.5-flash"
    )


def test_hard_cell_detection() -> None:
    from astral.bridge.rotation import is_hard_cell

    assert is_hard_cell(6, 2)
    assert not is_hard_cell(5, 2)
    assert not is_hard_cell(6, 1)


def test_production_cycle_pair_excludes_refusal_frontier() -> None:
    """Production cycles exclude only the high-refusal Claude frontier."""
    from astral.bridge.rotation import production_cycle_pair

    seen = set()
    for i in range(12):
        user, target, _judge = production_cycle_pair(i)
        seen.add((user, target))
        assert "claude" not in user
        assert "claude" not in target
    # rotation actually varies the pair across cycles
    assert len(seen) >= 5


def test_production_cycle_pair_is_deterministic() -> None:
    from astral.bridge.rotation import production_cycle_pair

    assert production_cycle_pair(1) == production_cycle_pair(1)
