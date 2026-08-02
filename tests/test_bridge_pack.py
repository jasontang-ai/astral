"""Cycle package writer: eval + transcripts.json best-practice contract."""

from __future__ import annotations

import json
from pathlib import Path

from inspect_ai.log import read_eval_log

from astral.bridge.pack import pack_cycle

VARIABLES = {
    "scientific_capability": 3,
    "jailbreak": 1,
    "kill_chain": 1,
    "intended_scope": 1,
}


def _write_side(unit: Path, side: str, *, with_note: bool = True) -> None:
    side_dir = unit / side
    side_dir.mkdir(parents=True)
    rows = [{"role": "user", "content": "hello from the actor"}]
    if with_note:
        rows.append({"role": "note", "content": '[tool call: hpidb_3_0({"query": "x"})]'})
    rows.append({"role": "assistant", "content": "response from the target"})
    (side_dir / "visible.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    (side_dir / "run.json").write_text(
        json.dumps(
            {
                "engine": "petri-bloom-audit-v1:auditor/target",
                "status": "complete",
                "turns": len(rows),
                "firewall": {"status": "pass", "findings": []},
                "telemetry": {
                    "models": {
                        "auditor": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _cycle_tree(tmp_path: Path) -> Path:
    root = tmp_path / "cycle-1"
    root.mkdir()
    unit = root / "ca.immune_escape.03-s1001"
    _write_side(unit, "benign")
    _write_side(unit, "malicious")
    manifest = {
        "cycle": 1,
        "ratio": "2:2:2",
        "harness": {
            "auditor_model": "openrouter/google/gemini-3.5-flash-lite",
            "target_model": "openrouter/google/gemini-3.5-flash",
            "judge_model": "openrouter/google/gemini-3.5-flash",
        },
        "pairs": [
            {
                "route_id": "ca.immune_escape.03",
                "seed": 1001,
                "variables": VARIABLES,
            }
        ],
    }
    (root / "manifest.yaml").write_text(__import__("yaml").safe_dump(manifest), encoding="utf-8")
    (root / "batch_report.json").write_text(
        json.dumps(
            {
                "manifest": str(root / "manifest.yaml"),
                "pairs": [
                    {
                        "pair_id": "ca.immune_escape.03-s1001",
                        "status": "ok",
                        "complete_transcripts": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return root


def test_pack_cycle_writes_eval_and_transcripts_with_contract(tmp_path: Path) -> None:
    root = _cycle_tree(tmp_path)
    result = pack_cycle(root)
    assert result["samples"] == 2
    eval_path = Path(result["eval_path"])
    json_path = Path(result["transcripts_path"])
    assert eval_path.is_file()
    assert json_path.is_file()

    log = read_eval_log(str(eval_path))
    assert (log.eval.metadata or {}).get("legend")
    assert log.stats is not None
    assert log.stats.model_usage
    sample = log.samples[0]
    assert sample.uuid
    assert sample.turn_count == 3
    assert sample.model_usage
    assert sample.output is not None
    assert sample.output.completion
    assert any(m.role == "system" and "tool call" in str(m.content) for m in sample.messages)
    assert sample.setup  # user_prompt for Inspect native setup visibility
    assert "user_prompt" in (sample.metadata or {}).get("card", {})

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "astral.transcripts.v1"
    assert payload["legend"]
    assert payload["count"] == 2
    row = payload["transcripts"][0]
    assert row["user_prompt"]
    assert row["engine"]
    assert any(m["role"] == "system" for m in row["messages"])


def test_pack_cycle_writes_review_html(tmp_path: Path) -> None:
    """pack_cycle emits the interactive review HTML alongside eval + transcripts."""
    import re

    root = _cycle_tree(tmp_path)
    result = pack_cycle(root)
    review = Path(result["review_path"])
    assert review.is_file()
    html = review.read_text(encoding="utf-8")
    assert "sampleSelect" in html
    match = re.search(
        r'<script id="evaluation-data" type="application/json">\s*(\{.*?\})\s*</script>',
        html,
        re.S,
    )
    assert match is not None
    data = json.loads(match.group(1))
    assert data["schema"] == "astral.review-bundle.v1"
    assert data["count"] == len(data["samples"]) == 2
    sample = data["samples"][0]
    assert sample["metadata"]["route_id"] == "ca.immune_escape.03"
    assert sample["metadata"]["user_prompt"]
