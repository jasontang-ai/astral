"""The Bloom arm runner, tested offline with an injected eval function."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from astral import VariableAssignment, make_actor_cards
from astral.bridge.run import BloomHarness, run_bloom_arm

ROUTE = "ca.immune_escape.01"
VARIABLES = VariableAssignment(scientific_capability=3, jailbreak=1, kill_chain=1, intended_scope=1)


def _pair():
    return make_actor_cards(route_id=ROUTE, variables=VARIABLES, seed=7)


def _fake_eval(task, model_roles=None, log_dir=None):
    samples = [
        SimpleNamespace(
            id="ca_immune_escape_01_malicious",
            messages=[
                SimpleNamespace(role="user", content="Opening ask."),
                SimpleNamespace(role="assistant", content="First answer."),
            ],
        ),
        SimpleNamespace(
            id="ca_immune_escape_01_benign",
            messages=[
                SimpleNamespace(role="user", content="Opening ask."),
                SimpleNamespace(role="assistant", content="First answer."),
            ],
        ),
    ]
    return SimpleNamespace(samples=samples)


def test_bloom_arm_normalizes_transcripts(tmp_path: Path) -> None:
    seen = {}

    def _eval(task, model_roles=None, log_dir=None):
        seen["model_roles"] = model_roles
        return _fake_eval(task, model_roles=model_roles, log_dir=log_dir)

    result = run_bloom_arm(
        _pair(),
        harness=BloomHarness(auditor="auditor-x", target="target-y"),
        out_dir=tmp_path,
        eval_fn=_eval,
    )
    assert seen["model_roles"] == {
        "auditor": "auditor-x",
        "target": "target-y",
        "judge": "target-y",
    }
    assert result["engine"] == "petri-bloom-audit-v1:auditor-x/target-y"
    assert len(result["scenarios"]) == 2
    for side, count in (("malicious", 2), ("benign", 2)):
        rows = [
            json.loads(line)
            for line in (tmp_path / side / "visible.jsonl").read_text().splitlines()
        ]
        assert len(rows) == count
        assert rows[0]["role"] == "user"
        record = json.loads((tmp_path / side / "run.json").read_text())
        assert record["side"] == side
        assert record["status"] == "complete"
        assert record["firewall"] == {"status": "pass", "findings": []}
        assert (tmp_path / side / "receipts.jsonl").is_file()
        assert "auditor-x" in record["engine"]


def test_bloom_arm_accepts_list_shaped_eval_logs(tmp_path: Path) -> None:
    def _list_eval(task, model_roles=None, log_dir=None):
        single = _fake_eval(task, model_roles=model_roles, log_dir=log_dir)
        return [single]

    result = run_bloom_arm(
        _pair(),
        harness=BloomHarness(auditor="auditor-x", target="target-y"),
        out_dir=tmp_path,
        eval_fn=_list_eval,
    )
    assert len(result["scenarios"]) == 2


def test_bloom_arm_records_role_mapping_and_usage(tmp_path: Path) -> None:
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15)

    def _eval(task, model_roles=None, log_dir=None):
        sample = SimpleNamespace(
            id="ca_immune_escape_01_malicious",
            messages=[SimpleNamespace(role="user", content="ask")],
            model_usage={"auditor-x": usage, "target-y": usage},
        )
        return SimpleNamespace(samples=[sample])

    result = run_bloom_arm(
        _pair(),
        harness=BloomHarness(auditor="auditor-x", target="target-y"),
        out_dir=tmp_path,
        eval_fn=_eval,
    )
    telemetry = result["telemetry"]
    assert telemetry["roles"] == {
        "auditor": "auditor-x",
        "target": "target-y",
        "judge": "target-y",
    }
    assert telemetry["attribution"] == "model-level (roles share models)"
    assert telemetry["models"]["auditor-x"]["total_tokens"] == 15
    record = json.loads((tmp_path / "malicious" / "run.json").read_text())
    assert record["telemetry"]["roles"]["auditor"] == "auditor-x"


def test_bloom_arm_attaches_fallback_models_to_task(tmp_path: Path) -> None:
    seen = {}

    def _eval(task, model_roles=None, log_dir=None):
        seen["config"] = getattr(task, "config", None)
        return SimpleNamespace(samples=[])

    run_bloom_arm(
        _pair(),
        harness=BloomHarness(
            auditor="auditor-x", target="target-y", fallback_models=["z-ai/glm-5.2"]
        ),
        out_dir=tmp_path,
        eval_fn=_eval,
    )
    assert seen["config"] is not None
    assert seen["config"].fallback_models == ["z-ai/glm-5.2"]


def test_bloom_arm_with_fallback_retries_incomplete(tmp_path: Path) -> None:
    from astral.bridge.run import run_bloom_arm_with_fallback

    calls = {"n": 0}

    def _eval(task, model_roles=None, log_dir=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(samples=[])  # no samples: not clean
        return _fake_eval(task, model_roles=model_roles, log_dir=log_dir)

    result = run_bloom_arm_with_fallback(
        _pair(),
        harness=BloomHarness(auditor="auditor-x", target="target-y"),
        fallback_harness=BloomHarness(auditor="z-ai/glm-5.2", target="z-ai/glm-5.2"),
        out_dir=tmp_path,
        eval_fn=_eval,
    )
    assert calls["n"] == 2
    assert result["retry"] is not None
    assert result["retry"]["to"] == {"auditor": "z-ai/glm-5.2", "target": "z-ai/glm-5.2"}
    assert "glm-5.2" in result["engine"]


def test_bloom_arm_with_fallback_skips_retry_when_clean(tmp_path: Path) -> None:
    from astral.bridge.run import run_bloom_arm_with_fallback

    result = run_bloom_arm_with_fallback(
        _pair(),
        harness=BloomHarness(auditor="auditor-x", target="target-y"),
        fallback_harness=BloomHarness(auditor="z-ai/glm-5.2", target="z-ai/glm-5.2"),
        out_dir=tmp_path,
        eval_fn=_fake_eval,
    )
    assert result["retry"] is None
    assert "auditor-x" in result["engine"]


def test_bloom_arm_passes_harness_policy(tmp_path: Path) -> None:
    seen = {}

    def _task(behavior, max_turns=15, compaction=True, system_message=None, **kwargs):
        seen["max_turns"] = max_turns
        seen["compaction"] = compaction
        seen["system_message"] = system_message
        return object()

    import astral.bridge.run as bridge_run

    original = bridge_run.bloom_audit
    bridge_run.bloom_audit = _task
    try:
        run_bloom_arm(
            _pair(),
            harness=BloomHarness(
                auditor="auditor-x",
                target="target-y",
                judge="judge-z",
                max_turns=4,
                compaction=False,
                system_message="custom system",
            ),
            out_dir=tmp_path,
            eval_fn=_fake_eval,
        )
    finally:
        bridge_run.bloom_audit = original
    assert seen["compaction"] is False
    assert seen["system_message"] == "custom system"
    assert seen["max_turns"] == 24  # agentic ceiling floors tool-bearing pairs


def test_judge_agreement_computes_match_rates() -> None:
    from astral.bridge.run import _judge_agreement
    from astral.qa.judge import Judgment, VariableJudgment

    def vj(choice: int) -> VariableJudgment:
        return VariableJudgment(
            choice=choice,
            confidence=0.9,
            evidence_turns=[1],
            rationale="r",
            counter_explanation="",
            abstain=False,
            reason="",
        )

    a = Judgment(
        variables={"jailbreak": vj(1), "kill_chain": vj(2)},
        assistant_outcome="engaged",
        assistant_outcome_rationale="",
        notes="",
    )
    b = Judgment(
        variables={"jailbreak": vj(1), "kill_chain": vj(3)},
        assistant_outcome="engaged",
        assistant_outcome_rationale="",
        notes="",
    )
    agreement = _judge_agreement(a, b)
    assert agreement is not None
    assert agreement["outcome_match"] is True
    assert agreement["variable_match_rate"] == 0.5
    assert _judge_agreement(a, None) is None


def test_audit_subset_is_seeded_and_bounded() -> None:
    from astral.bridge.run import _audit_subset

    assert _audit_subset("scenario_x") == _audit_subset("scenario_x")
    hits = sum(1 for i in range(200) if _audit_subset(f"scenario_{i}", rate=0.25))
    assert 20 < hits < 80  # ~25% rate with slack
    assert all(_audit_subset(f"scenario_{i}") for i in range(50))  # default is full
