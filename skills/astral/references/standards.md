# ASTRAL standards reference

Load when you need the full rules; the SKILL.md summary governs otherwise.

## Style

- Google Python Style Guide with project choices: 100-character lines, full
  package imports, no import-time side effects, no mutable default arguments.
- Docstrings give enough information to call without reading the source:
  summary line, blank line, `Args:`/`Returns:`/`Raises:` sections, `Examples:`
  blocks that run as doctests, `Attributes:` on contract classes.
- Comments explain why; docstrings explain how to use. Neither narrates code.
- Naming: `lower_snake_case`, `CapWords`, `UPPER_SNAKE_CASE`, single leading
  underscore for private helpers.
- Errors are specific and say what was wrong and what was expected.

## Structure

- One owner per concern; fixed dependency direction (`cards`, `runtime`,
  `bridge` depend only on `cards`/stdlib/third-party as registered).
- Package root contains only `__init__.py` and `py.typed`.
- Modules follow the tiered size rule: fine under 400 nonblank lines,
  `# size-justified:` comment required at 401–600, hard fail above 600.

## Metrics and tests

- Radon cyclomatic complexity ≤ 10 per function; maintainability rank A per
  module; trend ratchet versus the previous report.
- Coverage floor 90 percent; tests offline by default with `live` marks for
  model APIs.
- Registry, architecture, and metrics tests run first; the full suite runs in
  CI on Python 3.12 and 3.13.
- Type checking is dual: strict mypy blocks merges; ty runs the frozen command
  `ty check --python .venv/bin/python src` as an advisory signal in hooks and
  CI until promotion criteria in `AGENTS.md` are met.
