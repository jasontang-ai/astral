# ruff: noqa: T201,PLC0415,S603  # CLI surface: print is the interface; deferred
# imports lazy-load heavy domain modules so --help is fast; subprocess delegates
# to the canonical script runners.
"""ASTRAL command-line interface.

Subcommands:
    campaign: Run scheduled cycles with bounded concurrency.
    batch: Run one Bloom batch manifest.
    regen: Regenerate failed units.
    stats: Dataset representation and realization stats.
    review: Build the corpus review bundle.

Examples:
    Run the campaign schedule::

        python -m astral.cli campaign --cycles 1-100

    Regenerate failures::

        python -m astral.cli regen --attempt 2
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _cmd_campaign(args: argparse.Namespace) -> int:
    """Run the campaign schedule."""
    import os

    from astral.bridge.campaign import run_campaign

    if args.total:
        os.environ["ASTRAL_CAMPAIGN_TOTAL"] = str(args.total)
    cycles = _parse_cycles(args.cycles)
    run_campaign(cycles, runs_root=Path(args.runs_root), data_root=Path(args.data_root))
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    """Run one Bloom batch manifest."""
    from astral.bridge.batch import run_bloom_batch

    report = run_bloom_batch(args.manifest, out_dir=args.out_dir or None)
    pairs = report.get("pairs") or []
    promotable = sum(int(p.get("promotable_transcripts", 0)) for p in pairs)
    print(f"batch: {len(pairs)} pairs, {promotable} promotable transcripts")
    return 0


def _cmd_regen(args: argparse.Namespace) -> int:
    """Regenerate failed units via the regen runner."""
    import subprocess
    import sys

    cmd = [sys.executable, "scripts/regen_run.py", "--attempt", str(args.attempt)]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    return subprocess.call(cmd)


def _cmd_stats(args: argparse.Namespace) -> int:
    """Print dataset stats via the stats runner."""
    import subprocess
    import sys

    return subprocess.call([sys.executable, "scripts/dataset_stats.py"])


def _cmd_bench(args: argparse.Namespace) -> int:
    """Benchmark a detection model (scanner) or target refusal behavior."""
    import json

    if args.refusal:
        from astral.scanner.refusal import bench_refusal

        result = bench_refusal(args.model, max_turns=args.turns)
    else:
        from astral.scanner.bench import bench_model

        result = bench_model(
            args.eval,
            model=args.model,
            limit=args.limit or None,
        )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"metrics", "trajectory"}},
            indent=1,
            default=str,
        )
    )
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    """Build the corpus review bundle via the review runner."""
    import subprocess
    import sys

    cmd = [sys.executable, "scripts/build_corpus_review.py"]
    if args.downloads:
        cmd.extend(["--downloads", args.downloads])
    return subprocess.call(cmd)


def _parse_cycles(spec: str) -> range:
    """Parse a cycle range like ``1-100`` or ``83`` into a range."""
    if "-" in spec:
        start, end = spec.split("-", 1)
        return range(int(start), int(end) + 1)
    value = int(spec)
    return range(value, value + 1)


def build_parser() -> argparse.ArgumentParser:
    """Build the unified CLI argument parser.

    Returns:
        The configured ArgumentParser with all subcommands.
    """
    parser = argparse.ArgumentParser(prog="astral", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    campaign = sub.add_parser("campaign", help="run scheduled cycles")
    campaign.add_argument("--cycles", default="1-100", help="cycle range (e.g. 1-100)")
    campaign.add_argument(
        "--total", type=int, default=0, help="campaign size in cycles (default 100)"
    )
    campaign.add_argument("--runs-root", default="_runs")
    campaign.add_argument("--data-root", default="data/cycles")
    campaign.set_defaults(func=_cmd_campaign)

    batch = sub.add_parser("batch", help="run one Bloom batch manifest")
    batch.add_argument("manifest", help="path to the batch manifest YAML")
    batch.add_argument("--out-dir", default=None)
    batch.set_defaults(func=_cmd_batch)

    regen = sub.add_parser("regen", help="regenerate failed units")
    regen.add_argument("--attempt", type=int, default=1)
    regen.add_argument("--dry-run", action="store_true")
    regen.add_argument("--limit", type=int, default=0)
    regen.set_defaults(func=_cmd_regen)

    stats = sub.add_parser("stats", help="dataset representation and realization stats")
    stats.set_defaults(func=_cmd_stats)

    bench = sub.add_parser("bench", help="benchmark a detection model against the dataset")
    bench.add_argument("--eval", default="data/cycles/dataset/dataset-test.eval")
    bench.add_argument("--model", required=True, help="detection model id")
    bench.add_argument("--limit", type=int, default=0)
    bench.add_argument(
        "--refusal", action="store_true", help="benchmark target refusal instead of scanner"
    )
    bench.add_argument("--turns", type=int, default=4)
    bench.set_defaults(func=_cmd_bench)

    review = sub.add_parser("review", help="build the corpus review bundle")
    review.add_argument("--downloads", default=None, help="copy artifacts to this dir")
    review.set_defaults(func=_cmd_review)

    return parser


def main() -> int:
    """Dispatch the unified CLI.

    Returns:
        The subcommand's exit code.
    """
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
