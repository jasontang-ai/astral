"""Tests for the ASTRAL CLI adapter."""

from __future__ import annotations

from astral._cli import _parse_cycles, build_parser


def test_parser_parses_each_subcommand() -> None:
    parser = build_parser()
    assert parser.parse_args(["stats"]).command == "stats"
    assert parser.parse_args(["review"]).command == "review"
    assert parser.parse_args(["regen"]).command == "regen"
    assert parser.parse_args(["batch", "m.yaml"]).command == "batch"
    assert parser.parse_args(["campaign", "--cycles", "1-3"]).command == "campaign"


def test_fleet_cycle_range_parse() -> None:
    assert list(_parse_cycles("1-3")) == [1, 2, 3]
    assert list(_parse_cycles("5")) == [5]
