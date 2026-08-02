# ASTRAL workflow reference

## The spec loop

orient -> map -> select -> specify -> challenge -> execute -> validate -> learn

- Orient: read AGENTS.md, docs/design.md, recent commits, and the tests first.
- Map: state the decision, the construct, current evidence, and unknowns.
- Select: rank by decision value, information gain, and cost.
- Specify: one atomic requirement per change, with its enforcement mechanism.
- Challenge: check for leakage, weak controls, circular scoring, and drift.
- Execute: smallest coherent slice; registry rows in the same commit.
- Validate: gates plus the real user-facing surface; never unit tests alone.
- Learn: add a dated learnings entry with the rule the mistake created.

## Admission for new components

1. Candidate status in the stage table; never presented as shipped behavior.
2. Deterministic default first.
3. One-variable ablation against the frozen control with persisted outputs.
4. Promotion only on a predeclared gate with repetitions and holdouts.
5. Otherwise repair or delete, with the decision recorded.

## Commits and hooks

- Short imperative subject under 60 characters; conventional prefix.
- Hooks and reviews are driven by `skills/astral/gates.yaml`.
- `post-commit` / local checks: fast tier, including advisory ty.
- `pre-push`: fast blocking subset (registry, format, lint, mypy, skill-audit).
- CI runs the blocking suite plus advisory ty with the frozen command
  `ty check --python .venv/bin/python src`.
- After material successful pushes only, append one objective entry to
  `docs/progress/YYYY-MM-DD.md` using `docs/progress/README.md`. Skip small
  routine pushes. Dated progress files are gitignored; only the progress README
  is tracked. Keep the process layer strategic: protect the minimal core, do not
  accumulate ritual.
