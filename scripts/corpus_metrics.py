#!/usr/bin/env python3
"""Corpus quality metrics per cycle: tool loops, naming, promotable, failures.

The regression tripwire for the campaign: run after each segment to verify the
tool-loop ratio, the name-the-tool cadence, and promotable rates stay on
target. Prints a table and writes a JSON report.

Usage:
    python scripts/corpus_metrics.py [--cycles-root data/cycles] [--json report.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_GENERIC_MARKERS = (
    "run a quick",
    "run the",
    "use the tool",
    "our tool",
    "modeling tool",
    "a calculation",
    "compute this",
    "simulate this",
)


def _tool_names(biotool: Any) -> set[str]:
    """Name aliases for one biotool entry (canonical + aliases + head token)."""
    if not isinstance(biotool, dict):
        return set()
    names = {str(biotool.get("canonical_name") or "").lower()}
    for alias in biotool.get("aliases") or []:
        names.add(str(alias).lower())
    for name in list(names):
        names.add(name.split()[0])
    return {name for name in names if len(name) >= 4}


def _classify_no_loop(user_text: str, names: set[str]) -> str:
    """Failure class for a tool-bearing transcript without a loop."""
    if names and any(name in user_text for name in names):
        return "target_no_call"
    if any(marker in user_text for marker in _GENERIC_MARKERS):
        return "generic_ask"
    return "no_ask"


def cycle_metrics(cycle_dir: Path) -> dict[str, Any]:
    """Compute quality metrics for one cycle directory."""
    transcripts_path = cycle_dir / "transcripts.json"
    if not transcripts_path.is_file():
        return {}
    entries = json.loads(transcripts_path.read_text(encoding="utf-8")).get("transcripts") or []
    report_path = cycle_dir / "batch_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    promotable = sum(int(p.get("promotable_transcripts", 0)) for p in report.get("pairs") or [])
    counts: Counter[str] = Counter()
    named = 0
    for entry in entries:
        calls = [m for m in entry["messages"] if "tool call" in str(m.get("content", ""))]
        results = [m for m in entry["messages"] if "tool result" in str(m.get("content", ""))]
        biotool = entry.get("biotool")
        user_text = " ".join(
            str(m.get("content", "")).lower() for m in entry["messages"] if m.get("role") == "user"
        )
        if calls or results:
            counts["loop"] += 1
            names = _tool_names(biotool)
            if names and any(name in user_text for name in names):
                named += 1
        elif biotool:
            counts[_classify_no_loop(user_text, _tool_names(biotool))] += 1
        else:
            counts["conversation_only"] += 1
    total = len(entries)
    loop = counts["loop"]
    return {
        "cycle": cycle_dir.name,
        "logs": total,
        "loop": loop,
        "loop_rate": round(loop / total, 3) if total else None,
        "named_request_rate": round(named / loop, 3) if loop else None,
        "generic_ask": counts["generic_ask"],
        "target_no_call": counts["target_no_call"],
        "no_ask": counts["no_ask"],
        "conversation_only": counts["conversation_only"],
        "promotable": promotable,
        "promotable_rate": round(promotable / total, 3) if total else None,
    }


def main() -> int:
    """Print the metrics table and optionally write JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles-root", type=Path, default=Path("data/cycles"))
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    rows = []
    for cycle_dir in sorted(
        args.cycles_root.iterdir(), key=lambda p: int(p.name[6:]) if p.name[6:].isdigit() else 0
    ):
        if cycle_dir.name.startswith("cycle-") and cycle_dir.name[6:].isdigit():
            metrics = cycle_metrics(cycle_dir)
            if metrics:
                rows.append(metrics)
    if not rows:
        print("no cycle metrics found", file=sys.stderr)
        return 1

    header = f"{'cycle':9} {'logs':>4} {'loop%':>6} {'named%':>7} {'genQ':>5} {'noCall':>6} {'noAsk':>6} {'conv':>5} {'prom%':>6}"
    print(header)
    print("-" * len(header))
    total_loop = total_logs = total_prom = 0
    for row in rows:
        total_logs += row["logs"]
        total_loop += row["loop"]
        total_prom += row["promotable"]
        print(
            f"{row['cycle']:9} {row['logs']:>4} {row['loop_rate'] or 0:>6.0%} "
            f"{row['named_request_rate'] or 0:>7.0%} {row['generic_ask']:>5} "
            f"{row['target_no_call']:>6} {row['no_ask']:>6} "
            f"{row['conversation_only']:>5} {row['promotable_rate'] or 0:>6.0%}"
        )
    print("-" * len(header))
    print(
        f"TOTAL     {total_logs:>4} {total_loop / total_logs:>6.0%} {'':>7} {'':>5} {'':>6} {'':>6} {'':>5} {total_prom / total_logs:>6.0%}"
    )
    if args.json:
        args.json.write_text(json.dumps({"cycles": rows}, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
