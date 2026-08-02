"""Rubric scanner for transcript classification against the v4 rubric.

Only the rubric-assessment surface is ported: the v4 rubric classifier that
scores transcripts on SC/JB/KC/AT/AV/SP plus biological_agent, joined to
ground truth from sample metadata. The optimization stack (DSPy/GEPA,
layer-1 retrieval, envelopes) stays in the source branch.
"""

from astral.scanner.contract import (
    BIOLOGICAL_AGENT_FIELD,
    RUBRIC_CHOICES,
    RUBRIC_VARIABLE_NAMES,
    RUBRIC_VARIABLES,
    SCANNER_VERSION,
)
from astral.scanner.rubric import (
    ground_truth_for,
    pair_side_from,
    rubric_assessment,
    turns_from_transcript,
)
from astral.scanner.run import metric_suite, scan_eval, scan_sample

__all__ = [
    "BIOLOGICAL_AGENT_FIELD",
    "RUBRIC_CHOICES",
    "RUBRIC_VARIABLES",
    "RUBRIC_VARIABLE_NAMES",
    "SCANNER_VERSION",
    "ground_truth_for",
    "metric_suite",
    "pair_side_from",
    "rubric_assessment",
    "scan_eval",
    "scan_sample",
    "turns_from_transcript",
]
