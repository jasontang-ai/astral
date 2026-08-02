"""Dual-judge agreement as delegation triage.

The agreement score exists to shrink the human review bottleneck: per side it
yields an auto-accept decision (ship without human review vs route to humans);
per corpus it yields the auto-accept rate, the disagreement concentration
(which variable/route/harness drives disputes), and Cohen's kappa as
chance-corrected reliability evidence.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

_CONFIDENCE_FLOOR = 0.5


def _agreement_terms(pairs: list[tuple[str, str]], labels: set[str]) -> tuple[float, float]:
    """Observed and expected agreement fractions for kappa."""
    n = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / n
    counts_a = Counter(a for a, _ in pairs)
    counts_b = Counter(b for _, b in pairs)
    expected = sum((counts_a[k] / n) * (counts_b[k] / n) for k in labels)
    return observed, expected


def _confidence_floor_met(judgment: dict[str, Any]) -> bool:
    """Whether every scored variable clears the confidence floor."""
    variables = judgment.get("variables") or {}
    confidences = [
        float(v.get("confidence") or 0.0) for v in variables.values() if isinstance(v, dict)
    ]
    return all(c >= _CONFIDENCE_FLOOR for c in confidences) if confidences else True


def _outcome_pair(side: dict[str, Any]) -> tuple[str, str]:
    """Canonical/audit outcome pair for one side."""
    return (
        str((side.get("judgment") or {}).get("assistant_outcome") or "unknown"),
        str((side.get("audit_judgment") or {}).get("assistant_outcome") or "unknown"),
    )


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Chance-corrected agreement for two raters on categorical labels.

    Args:
        pairs: (rater_a_label, rater_b_label) per item.

    Returns:
        Kappa in [-1, 1]; None when fewer than 2 items or a single label.
    """
    if len(pairs) < 2:
        return None
    labels = {a for a, _ in pairs} | {b for _, b in pairs}
    if len(labels) < 2:
        return None
    observed, expected = _agreement_terms(pairs, labels)
    if expected >= 1.0:
        return None
    return (observed - expected) / (1 - expected)


def auto_accept(side: dict[str, Any]) -> bool:
    """Whether one judged side ships without human review.

    Auto-accept requires: canonical and audit judges agree on outcome, no
    judge call errors, and canonical confidence clears the floor on every
    scored variable.

    Args:
        side: A batch-report scenario with judgment/audit_judgment/agreement.

    Returns:
        True when the side routes to ship-without-review.
    """
    agreement = side.get("judge_agreement")
    if not agreement or not agreement.get("outcome_match"):
        return False
    judgment = side.get("judgment") or {}
    if judgment.get("model_error"):
        return False
    return _confidence_floor_met(judgment)


def disagreement_variables(side: dict[str, Any]) -> list[str]:
    """Variables where canonical and audit judges chose differently."""
    judgment = side.get("judgment") or {}
    audit = side.get("audit_judgment") or {}
    out = []
    for name, block in (judgment.get("variables") or {}).items():
        other = (audit.get("variables") or {}).get(name)
        if (
            isinstance(block, dict)
            and isinstance(other, dict)
            and block.get("choice") != other.get("choice")
        ):
            out.append(str(name))
    return out


def aggregate_report(sides: list[dict[str, Any]]) -> dict[str, Any]:
    """Corpus-level delegation report.

    Args:
        sides: Batch-report scenarios with dual-judge fields.

    Returns:
        Auto-accept rate, kappa, disagreement concentration by variable.
    """
    graded = [s for s in sides if s.get("judge_agreement")]
    outcome_pairs = [_outcome_pair(s) for s in graded]
    variable_disputes: Counter[str] = Counter()
    for side in graded:
        variable_disputes.update(disagreement_variables(side))
    accepted = sum(1 for s in graded if auto_accept(s))
    return {
        "dual_graded": len(graded),
        "auto_accepted": accepted,
        "auto_accept_rate": round(accepted / len(graded), 3) if graded else None,
        "outcome_kappa": (
            round(kappa, 3) if (kappa := cohens_kappa(outcome_pairs)) is not None else None
        ),
        "disagreement_by_variable": dict(variable_disputes.most_common()),
    }
