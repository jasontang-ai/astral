"""Tests for the scanner rubric optimization surface."""

from __future__ import annotations

from astral.scanner.optimize import _ground_truth, _transcript_text, make_rubric_signature


def test_ground_truth_from_card_variables() -> None:
    sample = {
        "card": {
            "variables": {
                "scientific_capability": 3,
                "jailbreak": 1,
                "kill_chain": 2,
                "intended_scope": 2,
            }
        }
    }
    truth = _ground_truth(sample)
    assert truth["SC"] == "3"
    assert truth["JB"] == "1"
    assert truth["KC"] == "2"


def test_transcript_text_flattens_user_assistant() -> None:
    sample = {
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "note", "content": "[tool]"},
        ]
    }
    text = _transcript_text(sample)
    assert "[user] hi" in text
    assert "[assistant] hello" in text
    assert "[note]" not in text


def test_make_rubric_signature() -> None:
    sig = make_rubric_signature("rubric text")
    assert sig is not None
