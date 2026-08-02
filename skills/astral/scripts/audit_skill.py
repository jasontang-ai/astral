#!/usr/bin/env python3
"""Self-verification for the ASTRAL skill.

Verifies that the skill's machinery is real: the gate manifest parses, every
learning has a live enforcement marker (a string that actually appears in the
referenced file), and every learning maps to gates that exist in the manifest.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SKILL = Path(__file__).resolve().parents[1]
MANIFEST = SKILL / "gates.yaml"
LEARNINGS = SKILL / "references" / "learnings.yaml"


def main() -> int:
    """Verify the skill's claims against the files they reference."""
    problems = []
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    gate_names = {g["name"] for g in manifest["gates"]}
    for gate in manifest["gates"]:
        for field in ("command", "blocking", "tiers"):
            if field not in gate:
                problems.append(f"gate {gate.get('name')}: missing {field}")

    entries = yaml.safe_load(LEARNINGS.read_text(encoding="utf-8")) or []
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)):
        problems.append("duplicate learning ids")
    for entry in entries:
        for gate in entry.get("gates") or []:
            if gate not in gate_names:
                problems.append(f"{entry['id']}: maps to unknown gate '{gate}'")
        enforced = str(entry.get("enforced") or "")
        if "::" not in enforced:
            problems.append(f"{entry['id']}: enforced must be 'path :: marker'")
            continue
        path_text, marker = (part.strip() for part in enforced.split("::", 1))
        target = ROOT / path_text
        if not target.is_file():
            problems.append(f"{entry['id']}: file missing: {path_text}")
        elif marker not in target.read_text(encoding="utf-8", errors="ignore"):
            problems.append(f"{entry['id']}: marker '{marker}' not found in {path_text}")
        for field in ("date", "mistake", "rule"):
            if not entry.get(field):
                problems.append(f"{entry['id']}: missing field {field}")

    for problem in problems:
        print(f"[FAIL] {problem}")
    if problems:
        return 1
    print(
        f"[PASS] {len(gate_names)} gates and {len(entries)} learnings verified against live mechanisms"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
