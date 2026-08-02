"""Registry adherence for docs/design.md (R04).

The component registry is the module-level contract for the rebuild. These tests
make drift impossible: every source file must be registered exactly once, every
registry row must point to a real file with the recorded nonblank line count, every
referenced test file must exist, and every requirement referenced in the
traceability matrix must be defined in the requirements section.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "design.md"
SRC = ROOT / "src" / "astral"

# Accept plain `` `path` `` or linked `` [`path`](url) `` registry labels.
ROW = re.compile(
    r"^\| (?:\[`(src/astral/[^`\]]+\.py)`\]\([^)]+\)|`(src/astral/[^`]+\.py)`) \| (\d+) \|",
    re.M,
)
REQ_DEF = re.compile(r"^\| (R\d{2}) \|", re.M)
REQ_ANY = re.compile(r"R\d{2}")
TEST_REF = re.compile(r"test_[a-z_]+(?=,| \|)")


def _rows() -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for match in ROW.finditer(DOC.read_text()):
        path = match.group(1) or match.group(2)
        rows.append((path, int(match.group(3))))
    return rows


def _nonblank(path: Path) -> int:
    return sum(1 for line in path.read_text().splitlines() if line.strip())


def test_every_source_file_is_registered_exactly_once() -> None:
    registered = [path for path, _ in _rows()]
    actual = sorted(str(p.relative_to(ROOT)) for p in SRC.rglob("*.py"))
    assert sorted(registered) == actual, (
        f"registry drift — missing: {sorted(set(actual) - set(registered))}, "
        f"stale: {sorted(set(registered) - set(actual))}, "
        f"duplicates: {sorted({p for p in registered if registered.count(p) > 1})}"
    )


def test_registry_line_counts_match_reality() -> None:
    drift = {
        path: (recorded, _nonblank(ROOT / path))
        for path, recorded in _rows()
        if recorded != _nonblank(ROOT / path)
    }
    assert not drift, f"update docs/design.md line counts: {drift}"


def test_referenced_tests_exist() -> None:
    referenced = set(TEST_REF.findall(DOC.read_text()))
    existing = {p.stem for p in (ROOT / "tests").glob("test_*.py")}
    assert referenced <= existing, f"unknown tests referenced: {sorted(referenced - existing)}"


def test_traceability_requirements_are_defined() -> None:
    text = DOC.read_text()
    defined = set(REQ_DEF.findall(text))
    matrix = text.split("## Traceability matrix", 1)[1]
    referenced = set(REQ_ANY.findall(matrix))
    assert referenced <= defined, (
        f"matrix references undefined requirements: {sorted(referenced - defined)}"
    )
