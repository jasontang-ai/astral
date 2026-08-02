# Contributing

ASTRAL holds one standard for every change: deterministic defaults, enforced style,
and evidence over assertion. This document is the contract for keeping it.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e '.[dev]'
pytest
```

## The standard

- **Style:** Google Python Style Guide with project choices, enforced by ruff
  (16 families including pydocstyle-google and pep8-naming), strict mypy, and a
  dual type posture (ty advisory, mypy blocking). Plain, objective English in
  code and docs; no hedging, no decision history in normative text.
- **Structure:** one owner per concern, registered per-file in
  [`docs/design.md`](docs/design.md). Every source file is in the component
  registry in the same commit that creates or changes it;
  [`tests/test_design_registry.py`](tests/test_design_registry.py) fails otherwise.
- **Path links:** Markdown docs link repository files instead of bare path text.
  See [`AGENTS.md`](AGENTS.md).
- **Tests:** offline by default; `live` marks are required for anything calling
  model APIs. Coverage floor 90 percent (`make coverage`).
- **Metrics:** radon complexity ≤ 10 per function, maintainability rank A per
  module, and no trend regression (`make metrics`,
  [`tests/test_metrics.py`](tests/test_metrics.py)).
- **Process:** every module earns its place or is dropped. New components enter
  as candidates behind a deterministic default and pass a one-variable ablation
  before admission.

## The gates

Run before every push:

```bash
pytest tests/test_design_registry.py tests/test_architecture.py
ruff format --check src tests
ruff check src tests
mypy src
ty check --python .venv/bin/python src   # advisory
pytest
make coverage
make metrics
python skills/astral/scripts/check_submission.py --full
```

CI runs the blocking suite on Python 3.12 and 3.13 plus advisory ty and a wheel
smoke. Optional local hooks: `git config core.hooksPath .githooks`. Hooks and
reviews are driven by [`skills/astral/gates.yaml`](skills/astral/gates.yaml).

## Commits

- Short imperative subject (under 60 characters) with a conventional prefix:
  `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`.
- Body only when the why is not obvious from the diff.
- Author identity: `Jason Tang <208424706+jasontang-ai@users.noreply.github.com>`.
  Use the repository-local git config if needed. Historical alternate noreply
  identities are mapped in [`.mailmap`](.mailmap); do not rewrite published
  history to clean attribution.
- Registry rows, `uv.lock`, and learning entries land in the same commit as the
  change they describe.
- After a **material** successful push, append one objective note to the day
  file under [`docs/progress/`](docs/progress/) using
  [`docs/progress/README.md`](docs/progress/README.md). Skip small routine
  pushes. Dated notes are gitignored local catch-up memory. Keep process light:
  notes exist for decisions and future catch-up, not for every commit.

## What gets rejected

- Changes that break a gate without a fix or a recorded justification.
- Unregistered files, stale registry counts, or renamed-but-not-swept symbols.
- Model-backed components presented as admitted defaults.
- Docs or code that describe intention rather than current behavior.

## Learnings

`AGENTS.md` keeps a dated learnings log. When a mistake teaches something
durable, add the entry and the rule it created in the same commit. Entries are
appended, never edited.
