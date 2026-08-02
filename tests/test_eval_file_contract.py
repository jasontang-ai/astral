"""The eval-file best-practice field contract."""

from __future__ import annotations

from inspect_ai.log import EvalDataset, EvalLog, EvalSample, EvalSpec, read_eval_log, write_eval_log
from inspect_ai.log._log import EvalConfig


def test_eval_metadata_legend_survives_the_recorder(tmp_path) -> None:
    """Legends must live on eval.metadata; top-level log.metadata is dropped."""
    path = tmp_path / "sample.eval"
    log = EvalLog(
        status="success",
        eval=EvalSpec(
            created="2026-07-29",
            task="contract",
            dataset=EvalDataset(name="contract", location="contract.eval", samples=1),
            model="test",
            config=EvalConfig(),
            metadata={"legend": {"how_to_read": "cells read judge/scanner/assigned"}},
        ),
        samples=[EvalSample(id="s1", epoch=1, input="q", target="benign", messages=[])],
    )
    log.metadata = {"dropped": True}
    write_eval_log(log, str(path))
    loaded = read_eval_log(str(path))
    assert (loaded.eval.metadata or {}).get("legend", {}).get("how_to_read") == (
        "cells read judge/scanner/assigned"
    )
    assert "dropped" not in (loaded.metadata or {})
