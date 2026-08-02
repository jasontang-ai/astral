# Architecture

ASTRAL is a small deterministic core with optional model/Bloom arms. The live
package keeps explainability high and surface area low: cards compile from pinned
ground truth, a deterministic runtime is the admitted control, and heavier arms
enter only through the earnings process.

```text
src/astral/
├── __init__.py        public SDK exports
├── py.typed           typed-package marker
├── assets/
│   └── grounding/     pinned BioTIER routing, roleplay lookup,
│                      pathogen directory, jailbreak technique lookup
├── cards/             deterministic actor-card compilation
│   ├── contracts.py
│   ├── grounding.py
│   ├── draw.py
│   ├── select.py
│   └── compile.py
├── runtime/           admitted control + thin model arm
│   ├── contracts.py
│   ├── engines.py
│   ├── run.py
│   └── model.py
├── bridge/            Bloom candidate adapter
│   ├── bloom.py
│   └── run.py
└── metrics/           complexity and maintainability gates
```

```text
archive/
└── 0.6.0-full-pipeline/   pre-restart implementation kept for inspection;
                           read-only, never imported, excluded from package and gates
```

## Rules

- The package root contains only [`__init__.py`](../src/astral/__init__.py) and
  [`py.typed`](../src/astral/py.typed).
- [`cards/`](../src/astral/cards/) depends only on the standard library, pydantic, and PyYAML.
- Ground truth is loaded byte-complete from
  [`src/astral/assets/grounding/`](../src/astral/assets/grounding/) and verified
  against pinned hashes; no derivations, no flattening.
- The deterministic runtime is the admitted stage-2 control. Bloom remains a
  candidate until Spec 333 gates pass.
- Components from the archive return only by re-earning their place through the
  ablation process, one variable at a time.
- Style, type, test, and complexity gates are configured in
  [`pyproject.toml`](../pyproject.toml), listed in
  [`skills/astral/gates.yaml`](../skills/astral/gates.yaml), and enforced by hooks
  and CI. mypy blocks; ty is an advisory second opinion.

## Public interface

```python
from astral import VariableAssignment, load_grounding, make_actor_cards
```

See [`docs/design.md`](design.md) for the requirement matrix and component registry.
