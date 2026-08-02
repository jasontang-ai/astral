# ASTRAL

ASTRAL is a biosecurity behavioral evaluation framework: it generates simulated
malicious and benign actor-model conversations from grounded actor cards, then
measures compliance (SecureBio BioTIER refuse/permit extended to multi-turn),
refusal decay, uplift, and detection.

**This is a reviewer-facing public copy.** The following are intentionally
excluded because they are restricted from public distribution or are
evaluation-private:

- the dataset (`data/`, `_runs/`) — simulated biothreat conversations
- the grounding assets (`src/astral/assets/grounding/`) — BioTIER routing,
  biological-agent, and related registries that carry threat-relevant content

The framework code — generation (`cards`, `bridge`), evaluation (`qa`,
`scanner`), and the benchmark protocol — is included so reviewers can read how
it works. The code references the gated grounding and will not run end-to-end
without it; access to the dataset and grounding is available on request to
organizations with a track record in AI-safety research.

See `docs/architecture.md` and `docs/benchmark.md` for the design.



---

# ASTRAL

[![CI](https://github.com/ethan-tam33/astral/actions/workflows/ci.yml/badge.svg?branch=jasontang%2Fprs%2Flab)](https://github.com/ethan-tam33/astral/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**ASTRAL** compiles grounded, matched actor-card pairs for AI biosecurity
evaluation and turns them into reproducible transcripts.

The repository is intentionally small. Deterministic defaults come first.
Heavier runtime arms enter only when they beat that control on a declared
metric.

## What it does

```text
pinned ground truth
→ deterministic card compile
→ matched benign / malicious pair
→ runtime transcript
```

1. **Compile** a route-grounded actor card from BioTIER assets.
2. **Match** a benign twin on the same pathway with scope and jailbreak off.
3. **Run** a deterministic control transcript with per-turn provenance.
4. **Compare**, when needed, against the thin model arm or the Bloom candidate.

ASTRAL does **not** claim scanner validity, real-world risk, or realism from
fixture metrics. Those require controlled ablation and independent review.

## Status

| Piece | Role | Status |
|---|---|---|
| [`cards/`](src/astral/cards/) | matched actor-card compiler | admitted |
| [`runtime/`](src/astral/runtime/) deterministic control | CI / ablation floor | admitted |
| [`runtime/model.py`](src/astral/runtime/model.py) | thin model smoke arm | available |
| [`bridge/`](src/astral/bridge/) | Petri Bloom adapter | candidate |
| scanners / full generation stack | archived pre-restart pipeline | not imported |

Landmark comparison:
[`docs/evidence/three-way-ca-immune-escape-01-2026-07-25/`](docs/evidence/three-way-ca-immune-escape-01-2026-07-25/)

## Install

Python 3.12+.

```bash
uv venv
source .venv/bin/activate
uv pip install -e '.[dev]'
```

Optional Bloom extras:

```bash
uv pip install -e '.[bloom]'
```

## Quick start

```python
from astral import VariableAssignment, make_actor_cards
from astral.runtime import run_pair

pair = make_actor_cards(
    route_id="ca.immune_escape.01",
    variables=VariableAssignment(
        scientific_capability=3,
        jailbreak=1,
        kill_chain=1,
        intended_scope=1,
    ),
    seed=7,
)

benign, malicious = run_pair(pair, seed=7)
print(pair.pair_id)
print(malicious.jailbreak_method)
print(benign.turns, malicious.turns)
```

What you get:

- **shared path:** same route, agent, workplace, capability, and kill-chain
- **benign difference:** `intended_scope=0`, `jailbreak=0`, authorized objective
- **malicious difference:** assigned scope/jailbreak, selected technique, private objective
- **runtime control:** byte-identical artifacts for the same card and seed

Draw a legal assignment when you do not want to specify variables:

```python
from astral import draw_assignment, make_actor_cards

route_id, variables = draw_assignment(seed=3, index=0)
pair = make_actor_cards(route_id=route_id, variables=variables, seed=3)
```

Or let the compiler draw for a fixed route:

```python
pair = make_actor_cards(route_id="ca.immune_escape.01", seed=7)
```

Illegal route values and out-of-constraint agents fail closed.

## Ground truth

Vendored under [`src/astral/assets/grounding/`](src/astral/assets/grounding/),
loaded byte-complete and hash-pinned:

| Asset | Role |
|---|---|
| `biotier_routing.yaml` | 98 routes and per-route allowed variable spaces |
| `variable_roleplay_guide.yaml` | roleplay instructions by variable level |
| `biological_agent_list.yaml` | 235 agents with class, tags, T/V, and control-regime tags |
| `jailbreak_list.yaml` | jailbreak techniques and actor instructions |

The compiler validates caller-provided variables against the route. If variables
are omitted, it selects from that route’s allowed sets with a deterministic seed,
then re-validates.

## Layout

```text
src/astral/
  cards/       deterministic compile, draw, select, grounding
  runtime/     deterministic control + thin model arm
  bridge/      Bloom candidate adapter
  metrics/     complexity and maintainability gates
  assets/      pinned ground truth
docs/
  design.md        requirements + component registry
  architecture.md  package layout and dependency rules
  evidence/        promoted landmark runs only
```

## Verify

```bash
pytest
make coverage
make metrics
mypy src
ty check --python .venv/bin/python src   # advisory
python skills/astral/scripts/check_submission.py --full
```

Enforcement stack:

- **blocking:** ruff, mypy, pytest, coverage floor 90%, radon metrics, design registry
- **advisory:** ty second-opinion types
- **config:** [`pyproject.toml`](pyproject.toml), [`skills/astral/gates.yaml`](skills/astral/gates.yaml), CI

## Documentation

| Doc | Use |
|---|---|
| [`docs/design.md`](docs/design.md) | requirements and per-file registry |
| [`docs/architecture.md`](docs/architecture.md) | layout and dependencies |
| [`docs/evidence/`](docs/evidence/) | landmark evidence index |
| [`AGENTS.md`](AGENTS.md) | agent operating contract |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | development and review standard |
| [`docs/progress/README.md`](docs/progress/README.md) | local notes after material pushes only |

## Design rules

- Keep the core minimal and explicit.
- Deterministic control first; change one variable at a time.
- Candidates are not defaults until they earn admission.
- Fixture metrics measure workflow mechanics, not external validity.
- Archived code is never imported. Port constructs against current contracts.

Pre-restart pipeline tag: `archive/0.6.0-full-pipeline`.

## License

MIT. See [`LICENSE`](LICENSE).
