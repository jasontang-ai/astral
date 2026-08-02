#!/usr/bin/env python3
"""One-pass ASTRAL conformance check, driven by the gate manifest.

Reads skills/astral/gates.yaml — the single definition of every gate — and
runs the requested tier. On failure, surfaces the learnings entry mapped to
that gate, so institutional memory arrives at the moment it is needed.

Usage:
    check_submission.py            # fast tier
    check_submission.py --full     # every gate
    check_submission.py --gate NAME  # one gate only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SKILL = Path(__file__).resolve().parents[1]
MANIFEST = SKILL / "gates.yaml"
LEARNINGS = SKILL / "references" / "learnings.yaml"


def _load_gates(tier: str, only: str | None) -> list[dict]:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    gates = manifest["gates"]
    if only:
        gates = [g for g in gates if g["name"] == only]
        if not gates:
            raise SystemExit(f"unknown gate: {only}")
        return gates
    return [g for g in gates if tier in g["tiers"]]


def _learnings_for(gate: str) -> list[dict]:
    if not LEARNINGS.is_file():
        return []
    entries = yaml.safe_load(LEARNINGS.read_text(encoding="utf-8")) or []
    return [e for e in entries if gate in (e.get("gates") or [])]


def _run(command: str) -> tuple[bool, str]:
    result = subprocess.run(command, cwd=ROOT, shell=True, capture_output=True, text=True)
    return result.returncode == 0, (result.stdout + result.stderr)[-400:]


def main() -> int:
    """Run the manifest gates and report, attaching mapped learnings to failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full", action="store_true", help="run every gate, not just the fast tier"
    )
    parser.add_argument("--gate", help="run one gate by name")
    args = parser.parse_args()
    tier = "full" if args.full else "fast"
    failures = []
    advisories = []
    for gate in _load_gates(tier, args.gate):
        ok, output = _run(gate["command"])
        if ok:
            print(f"[PASS] {gate['name']}")
            continue
        if gate["blocking"]:
            failures.append(gate["name"])
            print(f"[FAIL] {gate['name']}")
        else:
            advisories.append(gate["name"])
            print(f"[FAIL] {gate['name']} (advisory)")
        learnings = _learnings_for(gate["name"])
        if learnings:
            for entry in learnings:
                print(f"  learning ({entry['id']}, {entry['date']}): {entry['rule']}")
        elif output.strip():
            print("  " + output.strip().splitlines()[-1][:200])
    if advisories:
        print(f"\nAdvisory failures: {', '.join(advisories)}")
    if failures:
        print(f"\nBlocking failures: {', '.join(failures)}")
        return 1
    print("\nAll blocking gates pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
