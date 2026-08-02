"""Model-backed runtime, tested offline through an injected chat function."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from astral import VariableAssignment, make_actor_cards
from astral.runtime import run_card_model, run_pair_model
from astral.runtime.model import ProviderError, openrouter_chat

ROUTE = "ca.immune_escape.01"
VARIABLES = VariableAssignment(scientific_capability=3, jailbreak=1, kill_chain=1, intended_scope=1)


def _pair():
    return make_actor_cards(route_id=ROUTE, variables=VARIABLES, seed=7)


def _fake_chat(system: str, messages: list[dict[str, str]], model: str) -> tuple[str, dict]:
    return f"[{model}] reply {len(messages) + 1}", {"finish_reason": "stop"}


def test_user_sees_card_assistant_never_does() -> None:
    seen: list[tuple[str, str]] = []

    def spy(system: str, messages: list[dict[str, str]], model: str) -> tuple[str, dict]:
        seen.append((model, system))
        return "ok", {"finish_reason": "stop"}

    card = _pair().malicious
    run_card_model(card, user_model="user-x", assistant_model="assistant-y", turns=4, chat_fn=spy)
    user_systems = [s for m, s in seen if m == "user-x"]
    assistant_systems = [s for m, s in seen if m == "assistant-y"]
    assert all(system == card.user_prompt for system in user_systems)
    assert all(card.objective not in system for system in assistant_systems)
    assert all(card.route.category_text not in system for system in assistant_systems)


def test_alternation_and_provenance() -> None:
    record = run_card_model(
        _pair().malicious,
        user_model="user-x",
        assistant_model="assistant-y",
        turns=6,
        chat_fn=_fake_chat,
    )
    assert record.turns == 6
    assert [p.role for p in record.provenance] == ["user", "assistant"] * 3
    assert "openrouter-model-v1" in record.engine


def test_pair_runs_share_settings(tmp_path: Path) -> None:
    benign, malicious = run_pair_model(
        _pair(),
        user_model="user-x",
        assistant_model="assistant-y",
        turns=4,
        chat_fn=_fake_chat,
        out_dir=tmp_path,
    )
    assert benign.pair_id == malicious.pair_id
    assert benign.side == "benign"
    assert malicious.side == "malicious"
    assert list(tmp_path.rglob("visible.jsonl"))
    assert list(tmp_path.rglob("run.json"))


def test_run_card_model_passes_fallback_to_default_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str | None]] = []

    def _chat(system, messages, model, fallback_model=None):
        seen.append((model, fallback_model))
        return "ok", {"finish_reason": "stop"}

    monkeypatch.setattr("astral.runtime.model.openrouter_chat", _chat)
    run_card_model(
        _pair().malicious,
        user_model="user-x",
        assistant_model="assistant-y",
        turns=2,
        fallback_model="z-ai/glm-5.2",
    )
    assert seen[0] == ("user-x", "z-ai/glm-5.2")


def test_run_card_model_writes_usage_totals(tmp_path: Path) -> None:
    def _chat(system, messages, model):
        return "ok", {
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "cost": 0.001,
                "prompt_tokens_details": {"cached_tokens": 4, "cache_write_tokens": 2},
                "completion_tokens_details": {"reasoning_tokens": 3},
            },
        }

    run_card_model(
        _pair().malicious,
        user_model="user-x",
        assistant_model="assistant-y",
        turns=4,
        chat_fn=_chat,
        out_dir=tmp_path,
    )
    run_json = json.loads(next(tmp_path.rglob("run.json")).read_text())
    assert run_json["usage"] == {
        "input_tokens": 40,
        "output_tokens": 20,
        "total_tokens": 60,
        "cost_usd": 0.004,
        "cache_read_tokens": 16,
        "cache_write_tokens": 8,
        "reasoning_tokens": 12,
    }
    assert run_json["finish_reasons"] == ["stop", "stop", "stop", "stop"]


def test_over_cap_status_when_transcript_exceeds_cap(tmp_path: Path) -> None:
    def verbose(system, messages, model):
        return "ok", {"finish_reason": "stop"}

    card = _pair().malicious
    record = run_card_model(
        card,
        user_model="user-x",
        assistant_model="assistant-y",
        turns=4,
        chat_fn=verbose,
        out_dir=tmp_path,
    )
    assert record.turns == 4
    # status is complete at cap; over_cap triggers only beyond the declared cap
    run_json = json.loads(next(tmp_path.rglob("run.json")).read_text())
    assert run_json["status"] == "complete"

    from astral.runtime.contracts import Message
    from astral.runtime.model import _derive_status

    long_log = [Message(role="user", content="q"), Message(role="assistant", content="a")] * 6
    assert _derive_status(long_log, turn_cap=10) == "over_cap"


def test_provider_special_tokens_are_stripped() -> None:
    from astral.runtime.model import _strip_provider_tokens

    assert _strip_provider_tokens("<\uff5cend\u2581of\u2581sentence\uff5c>") == ""
    assert _strip_provider_tokens("answer<|im_end|>") == "answer"


def test_classify_failure_distinguishes_three_classes() -> None:
    from astral.runtime.model import classify_failure, is_refusal_lead

    assert classify_failure({}, ProviderError("openrouter HTTP 429")) == "mechanical"
    assert classify_failure({}, ProviderError("Gemini blocked the response: OTHER")) == "filtered"
    assert classify_failure({"finish_reason": "content_filter"}, None) == "filtered"
    assert classify_failure({"finish_reason": "error"}, None) == "filtered"
    assert classify_failure({"finish_reason": "stop"}, None) == "mechanical"
    assert is_refusal_lead("I cannot assist with that.")
    assert is_refusal_lead("\n I'm not able to help here.")
    assert not is_refusal_lead("Here is the analysis you asked for.")


def test_status_derivation_from_visible_behavior(tmp_path: Path) -> None:
    calls = {"n": 0}

    def refusing_assistant(system, messages, model):
        calls["n"] += 1
        if model == "assistant-y":
            return "I cannot provide that.", {"finish_reason": "stop"}
        return "ok", {"finish_reason": "stop"}

    run_card_model(
        _pair().malicious,
        user_model="user-x",
        assistant_model="assistant-y",
        turns=6,
        chat_fn=refusing_assistant,
        out_dir=tmp_path,
    )
    run_json = json.loads(next(tmp_path.rglob("run.json")).read_text())
    assert run_json["status"] == "refusal_dominated"
    assert any(e["class"] == "refusal" for e in run_json["failure_events"])


def test_topic_level_refusal_status(tmp_path: Path) -> None:
    def declining_user(system, messages, model):
        if model == "user-x":
            return "I cannot assist with planning that.", {"finish_reason": "stop"}
        return "ok", {"finish_reason": "stop"}

    run_card_model(
        _pair().benign,
        user_model="user-x",
        assistant_model="assistant-y",
        turns=2,
        chat_fn=declining_user,
        out_dir=tmp_path,
    )
    run_json = json.loads(next(tmp_path.rglob("run.json")).read_text())
    assert run_json["status"] == "topic_level_refusal"


def test_empty_response_stops_the_run_with_a_flag() -> None:
    calls = {"n": 0}

    def empty_on_third(system: str, messages: list[dict[str, str]], model: str) -> tuple[str, dict]:
        calls["n"] += 1
        text = "" if calls["n"] == 3 else "real content"
        return text, {"finish_reason": "stop"}

    record = run_card_model(
        _pair().malicious,
        user_model="user-x",
        assistant_model="assistant-y",
        turns=6,
        chat_fn=empty_on_third,
    )
    assert record.turns == 3
    last = record.provenance[-1]
    assert "empty_response" in last.sources


def test_turns_must_be_at_least_two() -> None:
    with pytest.raises(ValueError, match="turns must be at least 2"):
        run_card_model(
            _pair().malicious,
            user_model="user-x",
            assistant_model="assistant-y",
            turns=1,
            chat_fn=_fake_chat,
        )


def test_openrouter_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        openrouter_chat("sys", [], "model-x")


def test_openrouter_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class _Resp:
        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {"message": {"content": "hello"}, "finish_reason": "stop"},
                    ],
                    "usage": {"total_tokens": 3},
                }
            ).encode()

    monkeypatch.setattr("astral.runtime.model.urllib.request.urlopen", lambda *a, **k: _Resp())
    text, meta = openrouter_chat("sys", [{"role": "user", "content": "hi"}], "model-x")
    assert text == "hello"
    assert meta["finish_reason"] == "stop"
    assert meta["usage"]["total_tokens"] == 3


def test_openrouter_provider_filtered_uses_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    calls: list[str] = []

    class _Resp:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self._payload).encode()

    def _urlopen(request: object, timeout: int = 0) -> _Resp:
        body = json.loads(request.data.decode())  # type: ignore[attr-defined]
        model = body["model"]
        calls.append(model)
        if model == "primary":
            return _Resp({"error": "Gemini blocked the response: OTHER"})
        return _Resp(
            {
                "choices": [{"message": {"content": "recovered"}, "finish_reason": "stop"}],
                "usage": {},
            }
        )

    monkeypatch.setattr("astral.runtime.model.urllib.request.urlopen", _urlopen)
    text, _meta = openrouter_chat("sys", [], "primary", fallback_model="fallback")
    assert text == "recovered"
    assert calls == ["primary", "fallback"]


def test_openrouter_http_error_retries_then_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import urllib.error

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("astral.runtime.model.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def _urlopen(*args: object, **kwargs: object) -> None:
        calls["n"] += 1
        raise urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=503,
            msg="busy",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("astral.runtime.model.urllib.request.urlopen", _urlopen)
    with pytest.raises(ProviderError, match="openrouter HTTP 503"):
        openrouter_chat("sys", [], "model-x")
    assert calls["n"] == 2
