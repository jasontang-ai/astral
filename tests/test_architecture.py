"""Structural rules for the stage-1 layout.

The live package is small on purpose: a public root, one domain package (cards),
and vendored ground-truth assets. The pre-restart implementation is quarantined
under archive/ for inspection; nothing in the live tree may import from it.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "astral"


def test_package_root_is_public_surface_only() -> None:
    root_files = {path.name for path in SOURCE.iterdir() if path.is_file()}
    assert root_files == {"__init__.py", "py.typed"}
    package_dirs = {
        path.name for path in SOURCE.iterdir() if path.is_dir() and path.name != "__pycache__"
    }
    assert package_dirs == {"assets", "bridge", "cards", "_cli", "qa", "runtime", "scanner"}


def test_modules_stay_small() -> None:
    for path in SOURCE.rglob("*.py"):
        nonblank = sum(1 for line in path.read_text().splitlines() if line.strip())
        if nonblank > 600:
            raise AssertionError(
                f"{path.relative_to(ROOT)} has {nonblank} nonblank lines (hard cap 600)"
            )
        if nonblank > 400:
            head = "".join(path.read_text().splitlines(keepends=True)[:5])
            assert "# size-justified:" in head, (
                f"{path.relative_to(ROOT)} has {nonblank} nonblank lines; "
                "modules over 400 need a '# size-justified: <reason>' comment at the top"
            )


def test_live_tree_never_imports_archive() -> None:
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                text = ast.dump(node)
                assert "archive" not in text, f"{path.relative_to(ROOT)} imports archive"


def test_archive_stays_outside_the_package() -> None:
    forbidden = {"archive", "archived", "_archive", "compat"}
    offenders = [path for path in SOURCE.rglob("*") if path.is_dir() and path.name in forbidden]
    assert not offenders


def test_grounding_assets_are_complete() -> None:
    expected = {
        "biotier_routing.yaml",
        "variable_roleplay_guide.yaml",
        "jailbreak_list.yaml",
        "biological_agent_list.yaml",
        "biotool_and_database_list.yaml",
    }
    actual = {path.name for path in (SOURCE / "assets" / "grounding").iterdir() if path.is_file()}
    assert actual == expected
