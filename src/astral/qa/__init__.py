"""QA domain: deterministic alignment checks between cards and transcripts."""

from astral.qa.acceptance import AcceptanceReport, evaluate_side
from astral.qa.coverage import CoverageReport, check_coverage
from astral.qa.judge import Judgment, judge_sample
from astral.qa.realization import RealizationResult, technique_realization
from astral.qa.repetition import RepetitionResult, detect_repetition

__all__ = [
    "AcceptanceReport",
    "CoverageReport",
    "Judgment",
    "RealizationResult",
    "RepetitionResult",
    "check_coverage",
    "detect_repetition",
    "evaluate_side",
    "judge_sample",
    "technique_realization",
]
