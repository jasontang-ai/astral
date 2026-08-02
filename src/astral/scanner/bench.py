"""Benchmark protocol: run an arbitrary detection model against the corpus.

The integration point for external detection models. Takes any model id, runs
the rubric classification against the dataset, and returns the standard metric
suite (per-variable accuracy, side discrimination, RB false-positive rate,
slice breakdown) so stakeholders compare their models on the same golden data.

Examples:
    Benchmark a detection model against the test split::

        from astral.scanner.bench import bench_model
        result = bench_model("dataset-test.eval", model="openai/gpt-5.6-luna")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astral.scanner.run import scan_eval


def bench_model(
    eval_path: str | Path,
    *,
    model: str,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run one detection model against a dataset split and return metrics.

    Args:
        eval_path: The dataset split (.eval) to benchmark against.
        model: The detection model id to evaluate.
        limit: Optional cap on samples scanned.

    Returns:
        The benchmark result: the model id, the metric suite, and the split.
    """
    out = scan_eval(Path(eval_path), model=model, limit=limit)
    metrics = out.get("metrics") or {}
    return {
        "model": model,
        "split": Path(eval_path).stem,
        "samples": metrics.get("samples"),
        "per_variable_accuracy": metrics.get("per_variable_accuracy"),
        "side_accuracy": metrics.get("side_accuracy"),
        "model_errors": metrics.get("model_errors"),
        "metrics": metrics,
    }


def compare_models(
    eval_path: str | Path,
    *,
    models: list[str],
    limit: int | None = None,
) -> dict[str, Any]:
    """Benchmark several detection models on the same split for comparison.

    Args:
        eval_path: The dataset split (.eval) to benchmark against.
        models: The detection model ids to compare.
        limit: Optional cap on samples scanned per model.

    Returns:
        Per-model benchmark results plus the reference comparison.
    """
    results = {model: bench_model(eval_path, model=model, limit=limit) for model in models}
    return {
        "split": Path(eval_path).stem,
        "models": results,
        "side_accuracy_ranking": sorted(
            ((m, r.get("side_accuracy") or 0.0) for m, r in results.items()),
            key=lambda kv: -kv[1],
        ),
    }
