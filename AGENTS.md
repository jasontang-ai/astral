# AGENTS.md

Operational contract for coding agents in this repository. Complementary to
human docs. Prefer exact commands, checklists, and done criteria over prose
inventories. Keep long-lived detail in canonical files and link to them.

## Mission

Keep ASTRAL small, explicit, reproducible, and easy to review. Produce
decision-relevant evidence about AI-enabled biological capability and
safeguards without conflating model capability, user behavior, scanner output,
or real-world risk.

Prefer a minimal deterministic core. Add stochastic or model-backed components
only when they beat that core on a declared metric under a predeclared gate.

## Read first

1. This file — how to act, verify, and stop.
2. [`docs/design.md`](docs/design.md) — requirements and per-file registry.
3. [`docs/architecture.md`](docs/architecture.md) — layout and dependency direction.
4. [`docs/progress/README.md`](docs/progress/README.md) — after-push catch-up notes.

If these disagree, surface the conflict. Do not silently collapse it.

Local working memory is gitignored:

- [`docs/specs/`](docs/specs/)
- [`docs/research/`](docs/research/)
- dated files under [`docs/progress/`](docs/progress/)

Do not promote plans, spec IDs, or catch-up notes into code or public docs.
Specifications are decision contracts, not findings. Existing behavior is not
proof of validity. Proposals are not implementation truth.

## Non-negotiables

- Build the smallest thing that produces evidence. If a simpler existing
  mechanism works, the new one is a defect.
- Every addition earns its place or is removed. Name the decision and evidence.
- One tool per job. Deprecate before adding a second tool for the same job.
- Prefer deletion over addition, configuration over code, composition over new
  abstraction.
- Keep the process layer strategic and beneficial. Process exists to protect the
  minimal core, prevent silent drift, and improve decision quality. If a process
  artifact costs more than the risk it prevents, delete or demote it.
- Deterministic control first. Change one variable at a time.
- Requirements are atomic and individually enforced. No combined quality score
  substitutes for per-requirement checks.
- No model is the sole validator of its own output.
- Never import archived code. Port constructs against current contracts.
- Offline tests by default. Mark live network or model work explicitly.
- No secrets in files or commits.
- Verify, do not assert. Measure claims against the real artifact.
- Do not present candidates as shipped behavior.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e '.[dev]'
```

Python floor: 3.12. Lockfile: [`uv.lock`](uv.lock).

Optional hooks:

```bash
git config core.hooksPath .githooks
```

## Do this for every change

### Before coding

1. Orient on recent commits, failing tests, artifacts, and the owning module in
   [`docs/design.md`](docs/design.md).
2. State the decision, threat or failure pathway if relevant, construct, one
   changed variable, and falsifier.
3. Prefer an existing mechanism. If ownership overlap is possible, stop and
   surface it.

### While coding

1. Keep one owner per file and one job per tool.
2. Match neighboring code. Do not invent parallel abstractions.
3. Write Google-style docstrings on public functions: summary; then `Args:`,
   `Returns:`, and `Raises:` when needed; plus executable `Examples:` on public
   SDK surfaces.
4. Use plain objective English. No hedging, metaphors, or decision history in
   normative text.
5. In Markdown docs, hyperlink real repository paths. Bare `` `path` `` is for
   commands, code samples, or tables only.
6. Validate at user, network, persistence, and untrusted-I/O boundaries.
7. Fail closed with specific errors. Do not swallow failures in broad `except`.

### File lifecycle

**Add a source file**

1. Confirm one owner and no duplicated operation.
2. Add Google-style docs and neighboring test coverage.
3. Register it in [`docs/design.md`](docs/design.md) in the same commit:
   function, public surface, dependencies, verifying tests, nonblank line count.
4. Run:
   `pytest tests/test_design_registry.py tests/test_architecture.py`

**Change a source file**

1. Update the registry line count when nonblank lines change.
2. Update the registry row and public exports when the public surface changes.
3. Respect module size: under 400 nonblank lines preferred; 401–600 needs
   `# size-justified:`; over 600 fails.

**Delete a source file**

1. Delete its registry rows in the same commit.
2. Remove or reassign every requirement it owned in the traceability matrix.
3. Update any stage or dependency table that referenced it.

**Add or change a requirement**

1. One atomic requirement per change.
2. Assign class A, B, or C:
   - **A** — deterministic, CI-enforced
   - **B** — format or schema, boundary-enforced
   - **C** — subjective; ablation plus human review only
3. Add or update the traceability row in the same commit.

**Add a pipeline component**

1. Enter it as a candidate, never as default.
2. Ship or reuse the deterministic control first.
3. Predeclare decision, hypothesis, dependent variable, falsifier, gate, and
   cost budget.
4. Change exactly one variable against the frozen control. Persist raw failures.
5. Promote only on the predeclared gate with repetitions and holdouts.
6. Otherwise repair or delete it, including registry rows. Record the decision.
   Dropped means deleted, not commented out.

**Make a claim**

1. Class A evidence may be described as verified behavior.
2. Class B evidence may be described as schema or conformance behavior.
3. Class C qualities — realism, realization quality, scanner accuracy, external
   validity — need controlled ablation and human review. Never claim them from
   CI, fixtures, one run, or the model that produced the artifact.
4. Fixture metrics are workflow-mechanics evidence only. Say exactly that.

**Restore from archive or external research code**

1. Treat archive tags and old branches as external evidence, not importable code.
2. Port the construct or behavior, not the module tree.
3. Re-enter through the candidate admission path.
4. Require a current use case or material expected information gain.
5. Do not add compatibility shims for unreleased internal shapes.

### Before commit

```bash
pytest tests/test_design_registry.py tests/test_architecture.py
ruff format --check src tests
ruff check src tests
mypy src
```

If a change grows complexity, slows gates, or stretches the feedback loop,
justify it in the commit message.

### Before push

```bash
ty check --python .venv/bin/python src   # advisory
pytest
python scripts/metrics_report.py --check
python skills/astral/scripts/check_submission.py --full
```

Release-facing changes also need:

```bash
python -m build
```

Done means the artifact works through its real user-facing surface, not only
that unit tests pass. Preserve failures. Report anything unverified.

### After material successful pushes

When a push is material, append one compact objective entry to
`docs/progress/YYYY-MM-DD.md` using
[`docs/progress/README.md`](docs/progress/README.md).

Material means a contract change, admission or rejection, landmark evidence,
grounding source-of-truth change, gate-policy change, major unlock or blocker,
or release-facing change. Skip routine formatting, registry-count syncs, tiny
fixups, docs polish with no decision change, and process-about-process notes
unless policy itself changed.

Hard caps: max 5 entries and about 40 lines per day file; max 3 `changed`
bullets; one entry per decision theme. Merge or delete low-value notes. Dated
progress files are disposable and gitignored; only the progress README is
tracked.

## How work is admitted

Use this loop for substantive work:

1. Orient
2. Map the decision, construct, current evidence, alternatives, and unknowns
3. Select the highest-information next slice under safety and cost constraints
4. Specify locally under gitignored working memory
5. Challenge leakage, circular scoring, weak controls, label contamination,
   under-elicitation, unavailable dependencies, and unsafe detail
6. Implement the smallest coherent slice
7. Verify with gates and the real user-facing surface
8. Record result, limitation, decision, and highest-value successor

Research defaults:

- Start from the deterministic control and matched pairs.
- Keep shared route context fixed within a pair; change only the declared intent
  layer.
- Preserve hard benign near-neighbors.
- Do not infer intent from vocabulary alone.
- Record failures, coverage, calibration, cost, latency, and uncertainty
  separately.
- Use repetitions and holdouts before promoting stochastic improvements.

## Evidence boundaries

Keep these surfaces separate:

| Surface | Meaning |
|---|---|
| Ground truth | pinned vendored assets; load byte-complete; never edit in place |
| Design intent | private objectives, variables, pair metadata, hashes |
| Realized behavior | visible conversation and public tool receipts |
| Scanner judgment | predictions over visible material only |
| Evaluation | labels joined after inference |
| External validity | repeated held-out evidence and independent review |

## Biological and behavioral evaluation

- Separate capability, safeguards, human uplift, accessibility, intent,
  concealment, potential harm, and routing priority.
- Prefer matched controls, hard benign cases, paired comparisons, ablations,
  holdouts, repetitions, and cross-context replication.
- Report raw task performance, refusals, conditional performance, coverage,
  errors, calibration, false-positive burden, reviewer workload, cost, and
  latency separately.
- For interaction logs, judge cumulative behavior and cite supporting turns.
  Avoid keyword-only or isolated-turn conclusions.
- Treat synthetic personas and model judgments as evaluation constructs, not
  facts about real people.
- Require biological, statistical, operational, legal, or regulatory expert
  review for claims outside the software contract.
- Use synthetic tasks, abstract interfaces, redacted fixtures, and controlled
  review when detail could materially enable high-consequence biological harm.

## Code and docs standards

Normative layout and requirements live in [`docs/design.md`](docs/design.md).
Style reference:
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html),
enforced through Ruff's Google pydocstyle convention plus project gates.

Operational rules:

- Package root contains only `__init__.py` and `py.typed`.
- Domain modules do not import CLI or adapter layers.
- No import-time network calls or hidden provider fallbacks.
- Public functions use strict types. Prefer `| None` over `Optional`.
- Comments explain why. Docstrings explain how to use. Neither narrates code.
- Raise specific errors that state what was wrong and what was expected.
- Line length 100, enforced by Ruff.
- Function complexity and module maintainability are measured by radon gates.
- A new reader should understand a file from its registry row and first
  docstring line.

## Toolchain

One tool per job. Config lives in [`pyproject.toml`](pyproject.toml).
Gate manifest: [`skills/astral/gates.yaml`](skills/astral/gates.yaml).

| Tool | Role | Gate |
|---|---|---|
| uv | env and lockfile | committed `uv.lock` |
| ruff | format, lint, docstrings, security, imports | blocking |
| mypy | strict types | blocking |
| ty | second-opinion types; always pass `--python .venv/bin/python` | advisory |
| pytest + doctests | offline tests and executable examples | blocking |
| pytest-cov | coverage floor 90 percent | blocking in CI / `make coverage` |
| radon via `python scripts/metrics_report.py` | complexity, maintainability, trend ratchet | blocking |
| pydantic | boundary contracts | runtime validation |

Do not replace mypy with ty. Promote ty to a blocking AND-gate only after it is
pinned, CI-stable, and false-positive quiet on the default branch.

New tools enter only with one owner, one job, and one enforcement path.

## Git and safety

- Commit as `Jason Tang <208424706+jasontang-ai@users.noreply.github.com>`.
- Keep repository-local git identity on that address. Historical alternate
  noreply identities are canonicalized through [`.mailmap`](.mailmap) instead of
  rewriting published history.
- Short imperative subjects with conventional prefixes:
  `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
- Never force-push, rewrite published history, amend published commits, or run
  destructive git operations without explicit human approval.
- Never revert another worker's changes unless asked.
- Human approval is required for sensitive release, production deployment,
  benchmark-label exposure, destructive actions, and high-impact scientific or
  policy claims.
- For blocked web pages, use Exa with `EXA_API_KEY` from the environment. Never
  hardcode keys.

## Review standard

Lead with findings and decisions. Separate:

1. implementation behavior
2. empirical evidence
3. limitations
4. operational implications

A green software test establishes implementation behavior, not scanner validity
or real-world safety.

## Learnings

Durable mistakes live in
[`skills/astral/references/learnings.yaml`](skills/astral/references/learnings.yaml).
Append entries; never edit old ones. Supersede with a new id.
[`skills/astral/scripts/audit_skill.py`](skills/astral/scripts/audit_skill.py)
checks that every entry still has a live enforcement marker.

When a gate fails, read the matching learning before patching around it.

## Memory layers

Three systems, one job each:

| Layer | Location | Job |
|---|---|---|
| Enforced rules | [`skills/astral/references/learnings.yaml`](skills/astral/references/learnings.yaml) | Mistake → rule → live enforcement marker, audited |
| Push decisions | [`docs/progress/`](docs/progress/) | Material push records: SHA, gates, decision, next |
| Working memory | `.agent-memory/` (gitignored, OptMem) | Durable facts, provider behaviors, open questions |

Agents working on this repository use OptMem
([github.com/VictorTaelin/OptMem](https://github.com/VictorTaelin/OptMem)):
run `MEMORY_DIR=.agent-memory ~/.optmem/memo wake` at session start,
`memo note "<one line>"` when something durable is learned, and
`memo recall <regex>` to search. Notes that become rules are promoted into
`learnings.yaml` with an enforcement marker; they do not bypass it.

Getting started on a fresh machine:

```bash
curl -fsSL https://raw.githubusercontent.com/VictorTaelin/OptMem/main/install.sh | sh
mkdir -p .agent-memory
MEMORY_DIR=.agent-memory ~/.optmem/memo wake
```

### Agent identity memory (cognitive model)

An agent's own memory uses three stores, modeled on human memory:

- **Procedural (`PROC/`)** — skills and rules of action: gate discipline,
  patch discipline, verification order. Compact, imperative, tested.
- **Episodic (`EPI/`)** — dated incidents with cost and cause. Episodes are
  the evidence behind rules; they are never deleted, only compressed by
  `memo nap` (the consolidation step, analogous to gist formation).
- **Reflective (`REFL/`)** — metacognition: calibration tags
  (`verified | inferred | open`), cross-episode patterns, working agreements,
  and the self-model (known weak spots, known strengths).

Practices: wake at session start and answer one recall question from memory
before searching (retrieval practice); write compressions in your own words;
every episodic note carries why and cost; a repeated episode pattern becomes
a procedural rule, and a rule enters `learnings.yaml` only when gate
enforcement is warranted.
