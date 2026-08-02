"""The degenerate-repetition detector with the fixture/degeneration split."""

from __future__ import annotations

from astral.qa.repetition import detect_repetition
from astral.runtime.contracts import Message

_LONG = (
    "For the any way to deliver particles by air route, focus on measures of stability of "
    "biological agents under sunlight or ultraviolet radiation and the operational framing "
    "for engineering related countermeasures, including modern molecular details and "
    "incident-specific resistance patterns observed in the laboratory record."
)


def _messages(pattern: list[str]) -> list[Message]:
    roles = {"u": "user", "a": "assistant"}
    return [Message(role=roles[p[0]], content=p[1:]) for p in pattern]


def test_no_repetition_returns_none() -> None:
    messages = _messages(["uask one", "aanswer one", "uask two", "aanswer two"])
    result = detect_repetition(messages, engine="openrouter-model-v1:x/y")
    assert result.kind == "none"
    assert result.loops == []
    assert result.repeated_turns == 0


def test_fixture_repetition_is_determinism_not_defect() -> None:
    messages = [
        Message(role="user", content="start"),
        Message(role="assistant", content=_LONG),
        Message(role="user", content="next"),
        Message(role="assistant", content=_LONG),
        Message(role="user", content="next"),
        Message(role="assistant", content=_LONG),
    ]
    result = detect_repetition(messages, engine="deterministic-fixture-v1")
    assert result.kind == "fixture_determinism"
    assert result.loops == [[2, 4, 6]]
    assert result.repeated_turns == 3


def test_model_repetition_is_degenerate() -> None:
    messages = [
        Message(role="user", content="start"),
        Message(role="assistant", content=_LONG),
        Message(role="user", content="next"),
        Message(role="assistant", content=_LONG),
    ]
    result = detect_repetition(messages, engine="openrouter-model-v1:x/y")
    assert result.kind == "degenerate"
    assert result.loops == [[2, 4]]
    assert result.repeated_turns == 2


def test_short_formulaic_turns_are_not_repetition() -> None:
    messages = [
        Message(role="user", content="ask"),
        Message(role="assistant", content="I cannot provide that."),
        Message(role="user", content="again"),
        Message(role="assistant", content="I cannot provide that."),
    ]
    result = detect_repetition(messages, engine="openrouter-model-v1:x/y")
    assert result.kind == "none"


def test_normalization_treats_punctuation_and_case_as_equal() -> None:
    variant = _LONG.replace("stability", "Stability").replace(",", "")
    messages = [
        Message(role="user", content="start"),
        Message(role="assistant", content=_LONG),
        Message(role="user", content="next"),
        Message(role="assistant", content=variant),
    ]
    result = detect_repetition(messages, engine="petri-bloom-audit-v1:x/y")
    assert result.kind == "degenerate"


def test_detect_card_echo_flags_template_recitation() -> None:
    from astral.qa.repetition import detect_card_echo

    card = "estimate_R returns class estimate_R with posterior Mean(R), Std(R), and Quantile.0.025"
    msgs = [
        Message(role="user", content="run EpiEstim"),
        Message(role="system", content=f"[tool result: {card} methods: non_parametric_si]"),
        Message(role="assistant", content="analysis"),
    ]
    assert detect_card_echo(msgs, [card]) == 2
    clean = [
        Message(
            role="system",
            content="[tool result: Dif_4WWF_Repair_BM.fxout total bbHbond D550A +2.78]",
        ),
    ]
    assert detect_card_echo(clean, [card]) is None


def test_detect_result_duplicates_flags_verbatim_repeats() -> None:
    from astral.qa.repetition import detect_result_duplicates

    body = "[tool result: HPIDB rows PspC CFH P08603]"
    msgs = [
        Message(role="system", content=body),
        Message(role="assistant", content="x"),
        Message(role="system", content=body),
    ]
    assert detect_result_duplicates(msgs) == 3
    distinct = [
        Message(role="system", content="[tool result: row one]"),
        Message(role="system", content="[tool result: row two]"),
    ]
    assert detect_result_duplicates(distinct) is None
