"""Rubric scanner contract: variables, choices, and card-key mapping.

Ported against current contracts. Only the rubric-assessment surface is ported; the optimization
stack (DSPy/GEPA, layer-1 retrieval, envelopes) stays in the source branch.
"""

from __future__ import annotations

SCANNER_VERSION = "astral_rubric_assessment_v4"
DEFAULT_SCANNER_MODEL = "google/gemini-3.5-flash"

# Ordered rubric variables from scanner_rubric_v4.txt.
RUBRIC_VARIABLES = ("SC", "JB", "KC", "AT", "AV", "SP")
RUBRIC_REQUIRED_VARIABLES = ("SC", "JB", "KC", "SP")
RUBRIC_OPTIONAL_AGENT_VARIABLES = ("AT", "AV")
RUBRIC_SINGLE_CHOICE = ("SC", "JB", "AT", "AV", "SP")
RUBRIC_MULTI_SELECT = ("KC",)

RUBRIC_CHOICES = {
    "SC": ("1", "2", "3", "4", "5", "U"),
    "JB": ("0", "1", "2", "3", "U"),
    "KC": ("0", "1", "2", "3", "4", "5", "6", "7", "U"),
    "AT": ("T0", "T1", "T2", "T3", "T4", "U"),
    "AV": ("V0", "V1", "V2", "V3", "U"),
    "SP": ("0", "1", "2", "3", "U"),
}

RUBRIC_VARIABLE_NAMES = {
    "SC": "scientific_capability",
    "JB": "jail_breaking",
    "KC": "kill_chain_position",
    "AT": "agent_transmissibility",
    "AV": "agent_virulence",
    "SP": "scope",
}

BIOLOGICAL_AGENT_FIELD = "biological_agent"

# Keys inside card.variables for ground-truth joins.
CARD_VARIABLE_KEYS = {
    "SC": "scientific_capability",
    "JB": "jailbreak",
    "KC": "kill_chain",
    "SP": "intended_scope",
}
