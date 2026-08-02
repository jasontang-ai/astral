"""Two-sided calibration for judge/router error rates.

Dual-judge agreement cannot see correlated judge error; the only defense is
empirical measurement. Ship-routed sides get a seeded audit sample (measures
false-negative rate: bad content shipping). Regen-routed sides get a verify
sample, and human-routed sides are reviewed by definition (both measure
false-alarm rate: good content burned on regen or reviewer time). Every
human verdict is logged against the router decision so both error classes
are tracked per slice (route, model, variable) and the router recalibrates
from evidence instead of priors.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SHIP_AUDIT_RATE = 0.05
REGEN_VERIFY_RATE = 0.05


def audit_flag(kind: str, seed: str, side: str, rate: float) -> bool:
    """Seeded audit/verify selection for one side."""
    digest = hashlib.sha256(f"calib|{kind}|{seed}|{side}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF < rate


def stratified_review_sample(
    sides: list[dict[str, Any]], rate: float = 0.05, *, seed: int = 0
) -> list[dict[str, Any]]:
    """Stratified review sample covering every variable level and category.

    Random 5% sampling clusters on common cells and misses rare ones
    (Dev's point). Stratification takes the rate of each (family, side,
    variable-level) stratum so review coverage spans the full space
    instead of concentrating on the dominant cells.
    """
    strata: dict[tuple[str, str, Any, Any], list[dict[str, Any]]] = {}
    for side in sides:
        variables = side.get("variables") or {}
        key = (
            str(side.get("route_id") or "").split(".")[0],
            str(side.get("side") or ""),
            variables.get("sc"),
            variables.get("jb"),
        )
        strata.setdefault(key, []).append(side)
    rng = random.Random(seed)  # noqa: S311  # reproducible sampling
    out: list[dict[str, Any]] = []
    for members in strata.values():
        take = max(1, round(len(members) * rate))
        out.extend(rng.sample(members, min(take, len(members))))
    return out


def ship_audit_flag(seed: str, side: str) -> bool:
    """Whether a ship-routed side goes to human calibration review."""
    return audit_flag("ship", seed, side, SHIP_AUDIT_RATE)


def regen_verify_flag(seed: str, side: str) -> bool:
    """Whether a regen-routed side gets human verification of the decision."""
    return audit_flag("regen", seed, side, REGEN_VERIFY_RATE)


@dataclass(frozen=True)
class CalibrationVerdict:
    """One human verdict against a router decision."""

    side_id: str
    cycle: str
    route_decision: str
    router_p_wrong: float
    human_verdict: str  # good | bad | borderline
    slice_route: str = ""
    slice_target: str = ""


def _partition(
    verdicts: list[CalibrationVerdict],
) -> tuple[list[CalibrationVerdict], list[CalibrationVerdict]]:
    """Split verdicts into shipped and rejected decision groups."""
    shipped = [v for v in verdicts if v.route_decision == "ship"]
    rejected = [v for v in verdicts if v.route_decision in {"regen", "human_review"}]
    return shipped, rejected


def _slice_breakdown(verdicts: list[CalibrationVerdict]) -> dict[str, Counter[str]]:
    """Per-slice miss and false-alarm counts."""
    slices: dict[str, Counter[str]] = {}
    for verdict in verdicts:
        key = verdict.slice_route or verdict.slice_target or "unknown"
        bucket = slices.setdefault(key, Counter())
        if verdict.route_decision == "ship" and verdict.human_verdict == "bad":
            bucket["miss"] += 1
        if verdict.route_decision != "ship" and verdict.human_verdict == "good":
            bucket["false_alarm"] += 1
        bucket["n"] += 1
    return slices


class CalibrationLog:
    """Append-only verdict log with error-rate computation per slice."""

    def __init__(self, path: Path | None = None) -> None:
        """Load prior verdicts."""
        self.path = path
        self.verdicts: list[CalibrationVerdict] = []
        if path and path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self.verdicts.append(CalibrationVerdict(**row))

    def record(self, verdict: CalibrationVerdict) -> None:
        """Append one human verdict and persist."""
        self.verdicts.append(verdict)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(verdict.__dict__) + "\n")

    def error_rates(self) -> dict[str, Any]:
        """Miss and false-alarm rates overall and per slice.

        Miss: router shipped, human says bad. False alarm: router sent to
        regen/human, human says good.
        """
        shipped, rejected = _partition(self.verdicts)
        misses = sum(1 for v in shipped if v.human_verdict == "bad")
        alarms = sum(1 for v in rejected if v.human_verdict == "good")
        slices = _slice_breakdown(self.verdicts)
        return {
            "n_verdicts": len(self.verdicts),
            "miss_rate": round(misses / len(shipped), 3) if shipped else None,
            "false_alarm_rate": round(alarms / len(rejected), 3) if rejected else None,
            "by_slice": {k: dict(v) for k, v in slices.items()},
        }

    def p_wrong_recalibration(self) -> float | None:
        """Empirical ship-side error rate to recalibrate the router intercept."""
        shipped = [v for v in self.verdicts if v.route_decision == "ship"]
        if len(shipped) < 30:
            return None  # not enough evidence to recalibrate
        misses = sum(1 for v in shipped if v.human_verdict == "bad")
        return misses / len(shipped)
