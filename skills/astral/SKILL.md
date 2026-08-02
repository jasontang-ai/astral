---
name: astral
description: ASTRAL repository standards and workflow. Use when changing code, docs, tests, or configuration in the ASTRAL repo — covers the component registry, style gates, metrics ratchet, spec loop, and the run-before-push checklist.
---

# ASTRAL Repository Skill

ASTRAL holds one standard: deterministic defaults, enforced style, evidence over
assertion. Follow this skill for every change in this repository.

## Canonical order

1. [`AGENTS.md`](../../AGENTS.md) — conduct contract (rules of action, style standard, learnings).
2. [`docs/design.md`](../../docs/design.md) — module contract: atomic requirements and the per-file
   component registry. Enforced by [`tests/test_design_registry.py`](../../tests/test_design_registry.py).
3. [`docs/architecture.md`](../../docs/architecture.md) — layout and dependency rules.

When these disagree, surface the conflict; do not silently collapse it.

## Non-negotiables

- Every module earns its place or is dropped; new components enter as candidates
  behind a deterministic default with a one-variable ablation.
- Every source file enters the [`docs/design.md`](../../docs/design.md) registry in the same commit,
  with function, public surface, dependencies, tests, and nonblank line count.
- Offline tests by default; `live` marks for anything calling model APIs.
- Plain objective English; no hedging; docstrings in Google format with
  `Args:`/`Returns:`/`Raises:` on public functions and `Examples:` blocks that
  execute as doctests.
- Markdown docs link repository paths instead of bare path text.
- Ground truth files are loaded byte-complete and hash-pinned; never edited in
  place, never paraphrased into code.
- Commit messages: short imperative subject, conventional prefix.
- Type checking is dual: mypy blocks; ty is advisory via
  `ty check --python .venv/bin/python src`.

## Run before push

```bash
pytest tests/test_design_registry.py tests/test_architecture.py
ruff format --check src tests
ruff check src tests
mypy src
ty check --python .venv/bin/python src   # advisory
pytest
make coverage     # 90 percent floor
make metrics      # complexity and maintainability gates
```

For a full conformance check in one pass, run:

```bash
python skills/astral/scripts/check_submission.py          # fast gates
python skills/astral/scripts/check_submission.py --full   # plus tests and metrics
python skills/astral/scripts/audit_skill.py               # verify every rule still has a live mechanism
```

Failures come with the matching entry from the structured learnings log
([`references/learnings.yaml`](references/learnings.yaml)), so institutional memory arrives at the moment
it is needed.

## Reference files (load on demand)

- [`references/standards.md`](references/standards.md) — the style and structure standards in detail.
- [`references/workflow.md`](references/workflow.md) — the spec loop, admission process, and commit rules.
- [`references/learnings.yaml`](references/learnings.yaml) — the canonical structured learnings log: one
  entry per mistake, with the pattern that surfaces it on matching failures.
  Append entries; never edit them.

## Failure modes this skill exists to prevent

- Unregistered or stale registry entries (CI-enforced).
- Model-backed components presented as admitted defaults.
- Docstring rewrites that silently drop required sections (audited).
- Metric regressions shipped without justification (trend ratchet).
