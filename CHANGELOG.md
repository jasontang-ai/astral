# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Agentless objectives name the theme once; public draw helpers keep doctest
  examples; firewall markers match the revised prompt contract.
- Grounding integration uses the final BioTIER ASTRAL v0.5.1 selection contract:
  selection-enabled routes now use `agent_category_ref`, fixed menus enforce agent id constraints exactly, required/excluded tags and active status apply properly, and agentless routes now produce `agent = null`.
- Jailbreak level configuration is moved to the routing asset allowing route-specific restrictions, enforcing level 0 strictly for RB routes.
- Actor prompts now omit internal route identifiers, applicability labels, agent classes, and T/V scores while retaining the resolved agent name and route category text.

- Intended-scope guidance for levels 1–3 explicitly names harm.
- Jailbreak runtime grounding is the technique lookup only
  (`jailbreak_list.yaml`). Selected techniques supply actor instructions; no
  separate doctrine asset is loaded into cards or prompts.
- Type checking is dual and explicit: strict mypy remains blocking; ty runs the
  frozen advisory command `ty check --python .venv/bin/python src` in hooks and
  CI. Bloom eval-log unwrapping accepts one log or a list of logs.

## [0.7.0] - 2026-07-24

### Changed

- Restarted from first principles at stage 1: `make_actor_cards` compiles matched
  benign and malicious actor cards from the same inputs; the benign side follows
  the same pathway with intended scope and jailbreak disabled.
- Ground truth is vendored byte-complete under `assets/grounding/` (BioTIER routing
  registry, variable roleplay lookup, unified pathogen list, jailbreak technique
  lookup) and verified against pinned hashes on every load.
- The variable table is reduced: scientific capability, jailbreak (capped at 2),
  one kill-chain position, intended scope; persistence removed; tool categories
  replaced by a tool-call paragraph instruction.
- The pre-restart pipeline (generation, scanning, evaluation, workflow, adapters,
  CLI) is quarantined in `archive/0.6.0-full-pipeline/` for inspection and tagged
  `archive/0.6.0-full-pipeline` in git. It is never imported and excluded from the
  package, tests, and gates.

## [0.6.0] - 2026-07-23

### Changed

- Reorganized the SDK into explicit domain packages: `authoring`, `core`, `generation`,
  `scanning`, `evaluation`, `workflow`, `adapters`, and `cli`.
- Reduced the package root to the public `__init__.py` and `py.typed` marker.
- Moved Inspect registration under `adapters` and made CLI entry points target
  `cli.main` directly.
- Added architecture tests for the root layout and domain dependency direction.
- Removed old flat deep-import paths instead of retaining compatibility shims. The
  documented top-level SDK API is unchanged.

### Fixed

- Removed duplicated workspace read/list limit constants.

## [0.5.0] - 2026-07-23

### Added

- `astral baseline`: compiles three matched pairs, runs six fixture cases twice, and
  byte-compares every log, QA result, prediction, manifest, and report without model or
  network calls.
- `astral case compile-pair`: shared scenario, seed, obstacles, delivery, flags, and
  horizon with side-specific intent layers and deterministic source hashes.
- Structured objective steps with private surface ask, cover, and fallback fields.
- `astral diff`: descriptive report deltas for controlled component ablations.
- A generation authorization gate for concerning-route cases.

### Changed

- The metadata firewall now treats authorization, pair IDs, and source hashes as private
  provenance.
- The roadmap now requires deterministic and one-component ablations before adding
  model-backed pipeline components.

## [0.4.0] - 2026-07-23

### Added

- Per-log review packet: `astral review` renders JSON, text, and HTML with
  deterministically verified citations, measurements, provenance, and the source
  transcript. No model calls.
- Workspace file tools: sandboxed `list_files`/`read_file` via `--workspace`, with
  the QA tool gate via `--require-tool`.
- Role-based model allocation for provider-backed runs in
  `src/astral/assets/models.yaml`, overridable by CLI flags or
  `ASTRAL_*_MODEL` environment variables.
- Turn-level QA regeneration: deterministic defect detectors (incapacity, tool
  theatre, truncation, repetition) re-ask a defective turn with a corrective note
  inside a bounded budget, recorded as `qa_retries` in the run record.

### Changed

- Research governance (specs, maps, run records) moved out of the repository; the
  forward plan lives in `ROADMAP.md`.

## [0.3.0] - 2026-07-23

### Added

- Provider resilience: retries with exponential backoff and jitter for remote
  providers; `latency_ms`, `total_tokens`, and `last_error` in provenance.
- Evaluation economics: total tokens/latency and route×rubric co-occurrence slices
  in reports.
- Case compiler: `astral case compile` derives a validated case deterministically
  from a compact assignment.
- Acceptance-lite QA: deterministic promote/repair/reject gate with
  `astral generate --qa` and the `qa.accept()` API.
- Batch runner: `astral batch` orchestrates a directory of cases with a manifest.

## [0.2.0] - 2026-07-23

### Added

- Assignment-grounded user simulation: the V4.1 log-generation guide ships as a
  structured asset, and generation composes the simulated user's behavioral register
  from the case's hidden assignment.
- `HiddenLabel.delivery` and `HiddenLabel.flags` for delivery scenery and conditional
  flag modules, strictly validated.
- `examples/` with offline, tested walkthroughs.
- `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`, `Makefile`, issue and pull
  request templates, and a documentation index.

## [0.1.0] - 2026-07-23

### Added

- Public core: case validation, bounded multi-turn generation with explicit tools,
  independent route and V4.1 rubric scanner heads, post-inference evaluation with
  uncertainty and matched-pair recovery, and self-contained HTML reports.
- First-class Inspect AI tasks and Inspect Scout scanners over the same contracts.
- Structural metadata firewall separating visible logs from hidden labels.
- Offline `astral demo` exercising the complete workflow without credentials.
