# ASTRAL engineering design doc

This document is the module-level contract for the ASTRAL rebuild. It decomposes the
pipeline into atomic requirements, assigns every requirement an owner and an
enforcement mechanism, and registers every source file with its function, public
surface, dependencies, and verifying tests. The registry is enforced by
[`tests/test_design_registry.py`](../tests/test_design_registry.py): an unregistered file, a stale entry, or a broken
requirement reference fails CI. Conduct rules for acting on this document live in
`AGENTS.md`.

Two rules govern everything below:

1. **Every module earns its place or is dropped.** Admission requires a deterministic
   default plus a one-variable ablation showing the component improves a declared
   dependent variable without breaking an invariant. Retirement is recorded.
2. **Requirements are atomic and individually enforced.** Each requirement is small,
   unambiguous, and self-contained, and is checked by exactly the mechanism that can
   verify it: deterministic checks in CI, schema checks at boundaries, and — for
   subjective qualities — controlled ablation and human review. No model is the sole
   validator of its own output.

## Current stage

**Stage 2 — grounded runtime control with a Bloom candidate.** Stage 1 compiles
matched actor-card pairs from the BioTIER routing registry, roleplay lookup,
pathogen directory, jailbreak lookup, and simulated BioTIER tool/database lookup. The deterministic runtime is the
admitted stage-2 control. The Bloom bridge is a candidate runtime and is not a
default until Spec 333 passes its ablation and operational gates.

The pre-restart implementation (stages 2–8: generation, scanning, evaluation,
workflow, adapters, CLI) is preserved in the git tag `archive/0.6.0-full-pipeline`.
Archived code is never imported by the live tree and returns only through the
change process below. Components return only by re-earning their place
through the ablation process.

## The stages

| Stage | Question | Owning module(s) | Status |
|---|---|---|---|
| 1 · Cards | Who is the actor, and what do they want? | `cards/compile`, `cards/grounding`, `cards/contracts` | admitted (this document) |
| 2 · Run | What does the interaction look like? | `runtime/run`, `runtime/engines`; `bridge/bloom` | control admitted; Bloom bridge emitted for the model-runtime comparison |
| 3 · QA | Did the run realize its design? | archived | candidate |
| 4 · Scan | What does visible behavior show? | archived | candidate |
| 5 · Evaluate & release | What does the evidence mean? | archived | candidate |

## Requirements

Class A — deterministic, CI-enforced. Class B — format/schema, boundary-enforced.
Class C — subjective, enforced only by ablation and human review.

### Class A — deterministic

| ID | Requirement | Enforced by |
|---|---|---|
| R01 | Package root contains only `__init__.py` and `py.typed`. | [`tests/test_architecture.py`](../tests/test_architecture.py) |
| R02 | Every module stays under 400 nonblank lines. | [`tests/test_architecture.py`](../tests/test_architecture.py) |
| R03 | Every source file is registered in this document; the registry matches reality. | [[`tests/test_design_registry.py`](../tests/test_design_registry.py)](../tests/test_design_registry.py) |
| R04 | Ground-truth files load byte-complete and match hashes pinned in the test suite. | [`tests/test_grounding.py`](../tests/test_grounding.py) |
| R05 | Identical inputs compile to identical cards, including hashes. | [`tests/test_cards.py`](../tests/test_cards.py) |
| R06 | Pair sides share route, agent, simulated tool/database selection, workplace, and seed; the benign side is the same run with scope and jailbreak set to zero. | [`tests/test_cards.py`](../tests/test_cards.py) |
| R07 | Variables outside a route's allowed levels are rejected. | [`tests/test_cards.py`](../tests/test_cards.py) |
| R08 | Agents violating normalized route rules (category, tag, active status, fixed menu) are rejected; agentless routes specify no agent and generic scenarios. | [`tests/test_cards.py`](../tests/test_cards.py) |
| R33 | A route with BioTIER tool categories selects one active compatible tool/database by stable ID and seed; category-free routes select none. The card permits simulated conversational reference only and never executes an external tool. | [`tests/test_grounding.py`](../tests/test_grounding.py), [`tests/test_cards.py`](../tests/test_cards.py) |
| R09 | Route category text appears verbatim in card prompts. | [`tests/test_cards.py`](../tests/test_cards.py) |
| R10 | Unknown routes or agents fail closed with explicit errors. | [`tests/test_cards.py`](../tests/test_cards.py) |
| R11 | The live tree never imports the archive. | [`tests/test_architecture.py`](../tests/test_architecture.py) |

| R16 | Identical card and seed produce byte-identical run artifacts. | [`tests/test_runtime.py`](../tests/test_runtime.py) |
| R17 | Every run-record turn lists the ground-truth fields it was assembled from. | [`tests/test_runtime.py`](../tests/test_runtime.py) |
| R18 | Benign runs contain no jailbreak turn; malicious JB≥1 runs contain the technique move. | [`tests/test_runtime.py`](../tests/test_runtime.py) |
| R24 | An emitted Bloom behavior round-trips through Bloom's own loader with seeds, variation, and dimensions intact. | [`tests/test_bridge.py`](../tests/test_bridge.py) |
| R25 | Radon complexity ≤ 10 per function (rank B or better), maintainability rank A per module, and no trend regression versus the previous report. | [`tests/test_metrics.py`](../tests/test_metrics.py), [`scripts/metrics_report.py`](../scripts/metrics_report.py) |
| R26 | bridge/normalize | test_bridge_normalize |
| R27 | bridge/normalize, bridge/run | test_bridge_normalize |
| R28 | bridge/batch | test_bridge_batch |
| R29 | bridge/run, bridge/batch | test_bridge_run, test_bridge_batch |
| R30 | runtime/contracts, runtime/run, runtime/model, bridge/run | test_runtime |
| R31 | qa/realization | test_qa_realization |
| R32 | qa/repetition | test_qa_repetition |
| R33 | qa/judge | test_qa_judge |
| R34 | cards/compile, cards/draw | test_cards |
| R35 | cards/compile | test_cards |
| R36 | qa/coverage, bridge/run | test_qa_coverage, test_bridge_run |
| R37 | bridge/rotation, assets/model_routing.yaml | test_rotation |
| R38 | bridge/sessions | test_sessions |
| R39 | bridge/pack | test_bridge_pack |
| R40 | qa/acceptance, bridge/bloom, bridge/run, bridge/batch | test_qa_acceptance |
| R41 | bridge/normalize | test_bridge_normalize |
| R42 | qa/coverage | test_qa_coverage |
| R43 | bridge/normalize, qa/acceptance | test_qa_acceptance |
| R44 | bridge/run, qa/judge | test_bridge_run |
| R45 | bridge/bloom | test_bridge |
| R46 | qa/acceptance, bridge/normalize | test_qa_acceptance |
| R47 | bridge/pack, assets/review_template.html | test_bridge_pack |
| R48 | bridge/rotation | test_rotation |
| R49 | bridge/bloom, assets/biotool_output_cards.yaml | test_bridge |
| R50 | cards/compile, cards/output_cards, assets/biotool_output_cards.yaml, assets/biotool_output_examples.yaml | test_bridge |
| R51 | bridge/campaign | test_bridge_batch |
| R51 | Fleet runs cycles with bounded concurrency and resume (skip finished/in-flight); schedule materialized at data/cycles/schedule.yaml; harness draws exclude only the Claude refusal frontier. | [`tests/test_bridge_batch.py`](../tests/test_bridge_batch.py) |
| R50 | Tool output cards compile into the actor card prompt (guidance biotool_output); verbatim real documented examples (biotool_output_examples.yaml) win over approximations; all 105 routing tools resolve non-default cards. | [`tests/test_bridge.py`](../tests/test_bridge.py) |
| R49 | Auditor seeds carry per-tool output format cards (biotool_output_cards.yaml): raw tables/logs/records with version strings and realistic noise; repeated results must vary. | [`tests/test_bridge.py`](../tests/test_bridge.py) |
| R44 | QA judge runs per side after acceptance; judgment stored in run.json and batch report alongside acceptance. Judge failure does not block batch. | [`tests/test_bridge_run.py`](../tests/test_bridge_run.py) |

| R45 | Auditor seed instructs user to mention biotool by name when computation is needed; tool schema warns target not to self-initiate on first turn. | [`tests/test_bridge.py`](../tests/test_bridge.py) |
| R46 | Acceptance accepts refusal as a valid tool outcome; missing_tool_call fails only when the user asked and the target engaged without calling. Normalize drops self-initiated pre-mention tool notes. | [`tests/test_qa_acceptance.py`](../tests/test_qa_acceptance.py) |
| R47 | pack_cycle writes astralbench-cycle-N-review.html (interactive chat + card + judge review bundle) alongside the eval and transcripts.json. | [`tests/test_bridge_pack.py`](../tests/test_bridge_pack.py) |
| R48 | Cycles draw harness models via production_cycle_pair: seeded round-robin over the full user/target pools excluding only the BioTIER refusal-frontier (Claude 4.6/4.7/4.8). 75/25 tools split per cycle. | [`tests/test_rotation.py`](../tests/test_rotation.py) |
| R43 | Normalize surfaces tool results as visible notes (closed agentic loop); acceptance requires grounded query + result for tool-bearing cards. | [`tests/test_qa_acceptance.py`](../tests/test_qa_acceptance.py) |
| R42 | Coverage gates only on core keyword aspects (topic/agent/kill_chain); agent matches aliases/tokens, kill_chain matches stage cues; JB technique/tool loop are diagnostic or acceptance-owned, not promotion blockers. | [`tests/test_qa_coverage.py`](../tests/test_qa_coverage.py) |
| R41 | Normalize expands Inspect attachment:// tool-arg ids from sample.attachments so visible tool notes carry real scientific queries; nobody promotion-gates placeholders. | [`tests/test_bridge_normalize.py`](../tests/test_bridge_normalize.py) |
| R40 | Tool-bearing runs use a high max_turns safety ceiling only; auditor seeds carry a soft checklist stop (no turn floor); sides promote on exchange + firewall + grounded tool queries + coverage, not truncation alone. | [`tests/test_qa_acceptance.py`](../tests/test_qa_acceptance.py) |
| R39 | Finished cycles emit inspect-native eval and transcripts.json with eval.metadata legend, sample uuid/usage/completion, note-role tool calls, and full user_prompt. | [`tests/test_bridge_pack.py`](../tests/test_bridge_pack.py) |
| R38 | Multi-session arcs escalate kill chain across sessions with bounded grounded handoffs, note-role boundaries, arc provenance, and an exchange gate; no-exchange sessions block rather than append. | [`tests/test_sessions.py`](../tests/test_sessions.py) |
| R37 | Cycle model pairs rotate deterministically through evidence-grounded pools; fallbacks preserve refusal tiers with seeded rotation, never escalating permissiveness. | [`tests/test_rotation.py`](../tests/test_rotation.py) |
| R36 | Generated runs carry a coverage report per grounded checklist aspect; deterministic aspects are verified with evidence turns, register and scope defer to the judge. | [`tests/test_qa_coverage.py`](../tests/test_qa_coverage.py) |
| R35 | Card prompts state the chat channel ("You are chatting with an AI language model"), chat brevity, and omit the workplace-message genre cue. | [`tests/test_cards.py`](../tests/test_cards.py) |
| R34 | Malicious cards require intended_scope >= 1 at compile; draws never assign scope 0 to malicious-eligible pairs; RB routes are benign-only. | [`tests/test_cards.py`](../tests/test_cards.py) |
| R33 | The QA judge scores actor realization per variable on assigned scales with cited turns, counter-explanations, abstention, and a separate assistant outcome. | [`tests/test_qa_judge.py`](../tests/test_qa_judge.py) |
| R32 | Repetition is detected as substantive normalized assistant loops and split by engine provenance: fixture loops are determinism, model loops are degeneration. | [`tests/test_qa_repetition.py`](../tests/test_qa_repetition.py) |
| R31 | Technique realization is detected deterministically with marker evidence and stop-rule compliance; benign and JB0 cards are never realized. | [`tests/test_qa_realization.py`](../tests/test_qa_realization.py) |
| R30 | Runtime arms default to a ten-visible-message turn cap; Bloom expresses it as half the cap in auditor turns. | [`tests/test_runtime.py`](../tests/test_runtime.py) |
| R29 | Bloom run and batch reports record declared role-to-model mapping and provider-reported per-model token usage; batch reports aggregate actual usage and tokens per complete transcript. | [`tests/test_bridge_run.py`](../tests/test_bridge_run.py), [`tests/test_bridge_batch.py`](../tests/test_bridge_batch.py) |
| R26 | Bloom normalization extracts visible turns from tool-call structure, records engine receipts separately, and marks truncated target turns with a per-sample status. | [`tests/test_bridge_normalize.py`](../tests/test_bridge_normalize.py) |
| R27 | No private card field (objective, hash, or prompt markers) appears in normalized visible output. | [`tests/test_bridge_normalize.py`](../tests/test_bridge_normalize.py) |
| R28 | A Bloom batch records every pair's status; one pair's failure neither aborts the batch nor vanishes from the report. | [`tests/test_bridge_batch.py`](../tests/test_bridge_batch.py) |
| R19 | Every route carries complete legal variable spaces and non-empty category text. | [`tests/test_grounding.py`](../tests/test_grounding.py) |
| R20 | Route and agent ids are unique; the unified biological agent list never silently collapses. | [`tests/test_grounding.py`](../tests/test_grounding.py) |
| R21 | Structured roleplay and jailbreak lookup levels resolve to non-empty instructions; flag modules stay separate from variables. | [`tests/test_grounding.py`](../tests/test_grounding.py) |

### Class B — format and schema

| ID | Requirement | Enforced by |
|---|---|---|
| R12 | Jailbreak values are drawn from each route's allowed space; RB routes explicitly draw from [0] and fail if higher levels are supplied. | [`tests/test_cards.py`](../tests/test_cards.py) |
| R13 | Jailbreak level 2 on a benign side requires a recorded review note. | [`tests/test_cards.py`](../tests/test_cards.py) |
| R14 | Roleplay and jailbreak instructions are quoted verbatim from their pinned lookup entries. | [`tests/test_grounding.py`](../tests/test_grounding.py), [`tests/test_cards.py`](../tests/test_cards.py) |
| R15 | Card provenance includes a stable hash over all resolved inputs. | [`tests/test_cards.py`](../tests/test_cards.py) |

### Class C — subjective (deferred by design)

| ID | Requirement | Enforcement |
|---|---|---|
| R22 | Card realism and downstream conversation quality are measured only through controlled ablation with repetitions and holdouts. | ablation process; human review |
| R23 | Coverage of the route universe (basin KPI) is reported before any validity claim; governance-evasion families stay a small, capped slice. | ablation process; evaluation reports |

## Component registry

Line counts are nonblank lines. Every file in `src/astral/` appears exactly once.

| File | Lines | Function | Public surface | Depends on | Verified by |
|---|---|---|---|---|---|
| [`src/astral/__init__.py`](../src/astral/__init__.py) | 33 | Public SDK surface. | `draw_assignment`, `draw_assignment_for_route`, `make_actor_card`, `make_actor_cards`, `load_grounding`, `VariableAssignment`, `ActorCard`, `ActorCardPair`, `AgentRef`, `BioToolRef`, `RouteRef`, `Grounding`, `__version__` | cards | test_cards |
| [`src/astral/py.typed`](../src/astral/py.typed) | 0 | Typed-package marker. | — | — | test_architecture |
| [`src/astral/cards/__init__.py`](../src/astral/cards/__init__.py) | 27 | Domain exports. | same as root re-exports | cards.compile, cards.contracts, cards.grounding | test_cards |
| [`src/astral/cards/contracts.py`](../src/astral/cards/contracts.py) | 97 | Pair, card, variable, agent, and route shapes. | `StrictModel`, `VariableAssignment`, `AgentRef`, `RouteRef`, `ActorCard`, `ActorCardPair` | — | test_cards |
| [`src/astral/cards/grounding.py`](../src/astral/cards/grounding.py) | 164 | Hash-verified loaders for the four ground-truth files and structured roleplay/jailbreak lookups. | `ASSETS`, `Grounding`, `file_hashes`, `variable_instruction`, `jailbreak_techniques`, `load_grounding` | — | test_grounding |
| [`src/astral/cards/draw.py`](../src/astral/cards/draw.py) | 94 | Seeded route permutation and variable draws from route-allowed spaces. | `route_order`, `draw_assignment`, `draw_assignment_for_route`, `allowed_jailbreak_levels` | cards.contracts, cards.grounding | test_cards |
| [`src/astral/cards/output_cards.py`](../src/astral/cards/output_cards.py) | 58 | Simulated-tool output card resolution: tool -> category -> default, preferring verbatim real documented examples. | `load_output_cards`, `resolve_output_card` | cards.contracts | test_bridge |
| [`src/astral/cards/select.py`](../src/astral/cards/select.py) | 136 | Agent pool resolution and validation against normalized route constraints. | `select_agent` | cards.grounding | test_cards |
| [`src/astral/cards/compile.py`](../src/astral/cards/compile.py) | 503 | Route/level/agent validation, seeded assignment draws, deterministic agent selection, prompt assembly, provenance hashes. | `make_actor_card`, `make_actor_cards` | cards.contracts, cards.draw, cards.grounding, cards.select | test_cards |
| [`src/astral/cards/tool_select.py`](../src/astral/cards/tool_select.py) | 57 | Stable seeded selection and validation of route-compatible simulated BioTIER tools/databases; no execution boundary. | `select_biotool` | cards.grounding | test_cards, test_grounding |
| [`src/astral/runtime/__init__.py`](../src/astral/runtime/__init__.py) | 14 | Domain exports. | `run_card`, `run_pair`, `Message`, `VisibleLog`, `RunRecord`, `TurnProvenance` | runtime.run, runtime.contracts | test_runtime |
| [`src/astral/runtime/contracts.py`](../src/astral/runtime/contracts.py) | 50 | Run shapes: messages, visible logs, per-turn provenance, run records. | `Message`, `VisibleLog`, `TurnProvenance`, `RunRecord`, `StrictModel` | — | test_runtime |
| [`src/astral/runtime/engines.py`](../src/astral/runtime/engines.py) | 106 | Deterministic user/assistant turn engines assembled from grounded card fields. | `user_turn`, `assistant_reply` | cards.contracts | test_runtime |
| [`src/astral/runtime/run.py`](../src/astral/runtime/run.py) | 105 | Bounded card-to-transcript loop with per-turn provenance and deterministic artifacts. | `run_card`, `run_pair` | cards.contracts, runtime.contracts, runtime.engines | test_runtime |
| [`src/astral/runtime/model.py`](../src/astral/runtime/model.py) | 337 | Model-backed card execution with role inversion, provider retry handling, and an injectable chat backend; assistant never sees the card. | `run_card_model`, `run_pair_model`, `openrouter_chat`, `ProviderError`, `classify_failure`, `is_refusal_lead` | cards.contracts, runtime.contracts | test_model_runtime |
| [`src/astral/bridge/__init__.py`](../src/astral/bridge/__init__.py) | 16 | Domain exports. | `card_to_seed`, `firewall_check`, `normalize_sample`, `pair_to_behavior`, `run_bloom_arm`, `run_bloom_batch`, `write_behavior_dir` | bridge.batch, bridge.bloom, bridge.normalize, bridge.run | test_bridge, test_bridge_run, test_bridge_normalize, test_bridge_batch |
| [`src/astral/bridge/bloom.py`](../src/astral/bridge/bloom.py) | 276 | Deterministic actor-card to Petri Bloom behavior emission (seeds, dimensions, understanding). | `card_to_seed`, `pair_to_behavior`, `write_behavior_dir` | cards.contracts, petri_bloom, inspect_petri | test_bridge |
| [`src/astral/bridge/normalize.py`](../src/astral/bridge/normalize.py) | 508 | Bloom sample normalization contract: structured extraction from tool calls, statuses, receipts separation, firewall check. | `normalize_sample`, `firewall_check`, `NormalizedSample`, `EngineReceipt` | cards.contracts, runtime.contracts | test_bridge_normalize |
| [`src/astral/bridge/rotation.py`](../src/astral/bridge/rotation.py) | 168 | Deterministic model rotation and tier-preserving seeded fallbacks from config/model_routing.yaml. | `cycle_pair`, `provider_id`, `resolve_fallback`, `is_hard_cell`, `pool_summary` | assets/model_routing.yaml | test_rotation |
| [`src/astral/bridge/sessions.py`](../src/astral/bridge/sessions.py) | 204 | Multi-session escalation arcs: continuation cards with bounded grounded handoffs, chain runner with exchange gate, arc provenance. | `continuation_card`, `run_session_chain`, `append_session`, `sessions_metadata` | bridge/run | test_sessions |
| [`src/astral/bridge/batch.py`](../src/astral/bridge/batch.py) | 245 | Manifest-driven Bloom batch runner with failure isolation, cost ceiling, atomic progress reports, and resume support. | `run_bloom_batch` | bridge.run, cards | test_bridge_batch |
| [`src/astral/bridge/regen_merge.py`](src/astral/bridge/regen_merge.py) | 74 |
| [`src/astral/bridge/trajectory.py`](../src/astral/bridge/trajectory.py) | 72 | Per-turn trajectories: assistant BioTIER compliance (refuse/permit) and actor pursuit (pursue/retreat), grounded in BioTIER risk-set. | `_per_turn_compliance`, `_actor_trajectory` | qa.acceptance | test_bridge_trajectory |
| [`src/astral/bridge/pack.py`](../src/astral/bridge/pack.py) | 571 | Cycle package writer: combined Inspect eval + transcripts.json with best-practice fields (uuid, usage, legend on eval.metadata, note-role tool calls, user_prompt). | `pack_cycle`, `write_cycle_eval`, `write_transcripts_json` | bridge/batch | test_bridge_pack |
| [`src/astral/bridge/campaign.py`](../src/astral/bridge/campaign.py) | 583 | Cycle campaign: 100-cycle seeded schedule, manifest builder, resume-aware parallel runner with bounded concurrency. | `cycle_spec`, `build_schedule`, `run_campaign` | bridge.batch, bridge.rotation | test_bridge_batch |
| [`src/astral/_cli/__init__.py`](../src/astral/_cli/__init__.py) | 135 | ASTRAL command-line interface: campaign, batch, regen, stats, review subcommands delegating to the canonical runners. | `build_parser`, `main` | bridge.campaign, bridge.batch, scripts | test_cli |
| [`src/astral/_cli/__main__.py`](../src/astral/_cli/__main__.py) | 4 | Module entry point for python -m astral.cli. | `main` | cli | test_cli |
| [`src/astral/bridge/run.py`](../src/astral/bridge/run.py) | 451 | Petri Bloom audit execution with explicit model roles, compaction policy, telemetry, and normalized artifact writing. | `run_bloom_arm`, `run_bloom_arm_with_fallback`, `BloomHarness` | bridge.bloom, bridge.normalize, cards.contracts, inspect_ai, petri_bloom | test_bridge_run |
| [`src/astral/qa/__init__.py`](../src/astral/qa/__init__.py) | 18 | QA domain exports. | `detect_repetition`, `technique_realization`, `RealizationResult`, `RepetitionResult` | qa.realization, qa.repetition | test_qa_realization, test_qa_repetition |
| [`src/astral/qa/realization.py`](../src/astral/qa/realization.py) | 214 | Deterministic technique-realization detection: marker evidence and stop-rule compliance for the card's assigned jailbreak technique. | `technique_realization`, `RealizationResult` | cards.contracts, runtime.contracts | test_qa_realization |
| [`src/astral/qa/repetition.py`](../src/astral/qa/repetition.py) | 256 | Degenerate-repetition detection with the fixture-determinism split by engine provenance; short formulaic turns are never counted. | `detect_repetition`, `RepetitionResult` | runtime.contracts | test_qa_repetition |
| [`src/astral/qa/judge.py`](../src/astral/qa/judge.py) | 190 | QA judge: per-variable realization on assigned BioTIER scales with counter-explanations, abstention, and assistant outcome classes. | `judge_sample`, `build_prompt`, `parse_judgment`, `Judgment` | cards.contracts, qa.realization, runtime.model | test_qa_judge |
| [`src/astral/qa/coverage.py`](../src/astral/qa/coverage.py) | 267 | Deterministic coverage verification: each grounded checklist aspect checked against the visible transcript with evidence turns. | `check_coverage`, `CoverageReport`, `AspectCoverage` | cards.contracts, qa.realization, runtime.contracts | test_qa_coverage |
| [`src/astral/qa/acceptance.py`](../src/astral/qa/acceptance.py) | 324 | Generation-side promotability: exchange, firewall, tool-query hygiene, coverage — without turn floors. | `evaluate_side`, `tool_hygiene_ok`, `AcceptanceReport` | cards.contracts, qa.coverage | test_qa_acceptance |
| [`src/astral/qa/calibration.py`](../src/astral/qa/calibration.py) | 124 | Two-sided error measurement: ship-audit misses, regen-verify false alarms, per-slice rates, p_wrong recalibration. | `CalibrationLog, CalibrationVerdict, error_rates` | qa.realization, qa.coverage | test_qa_routing_score |
| [`src/astral/scanner/run.py`](../src/astral/scanner/run.py) | 122 | Eval scan runner: scan samples and compute the benchmark metric suite. | `scan_eval, scan_sample, metric_suite` | runtime.model | test_scanner |
| [`src/astral/scanner/optimize.py`](../src/astral/scanner/optimize.py) | 250 | Scanner rubric optimization via DSPy: signature builder, ground-truth extraction, dataset-split optimization against labels. | `build_signature`, `optimize_rubric` | scanner.contract, dspy | test_scanner_optimize |
| [`src/astral/scanner/bench.py`](../src/astral/scanner/bench.py) | 62 | Benchmark protocol: run an arbitrary detection model against the corpus and return the standard metric suite. | `bench_model`, `compare_models` | scanner.run, qa.acceptance | test_scanner |
| [`src/astral/scanner/trajectory.py`](../src/astral/scanner/trajectory.py) | 66 | Multi-turn BioTIER: refusal trajectory, break-turn detection, compliance summary per conversation. | `refusal_trajectory`, `break_turn`, `compliance_summary` | scanner.run, qa.acceptance | test_scanner_trajectory |
| [`src/astral/scanner/rubric.py`](../src/astral/scanner/rubric.py) | 163 | Rubric assessment: single model call per transcript with ground-truth join. | `rubric_assessment, ground_truth_for, turns_from_transcript` | runtime.model | test_scanner |
| [`src/astral/scanner/__init__.py`](../src/astral/scanner/__init__.py) | 34 | Rubric scanner package surface. | contract, rubric, run | scanner.contract, scanner.rubric, scanner.run | test_scanner |
| [`src/astral/scanner/contract.py`](../src/astral/scanner/contract.py) | 37 | Rubric scanner contract: variables, choices, card-key mapping. | `RUBRIC_VARIABLES, RUBRIC_CHOICES, CARD_VARIABLE_KEYS` | runtime.model | test_scanner |
| [`src/astral/qa/routing_score.py`](../src/astral/qa/routing_score.py) | 343 | Expected-cost ship/regen/human router with regen-success posterior and deterministic-gate authority. | `route_side, RegenSuccessModel, RouteDecision` | qa.realization, qa.coverage | test_qa_routing_score |
| [`src/astral/qa/realization_gate.py`](../src/astral/qa/realization_gate.py) | 379 | Evidence-driven realization diagnosis with confidence rating, forced causes, regen budget cap. | `diagnose, Diagnosis, VariableDelta` | qa.realization, qa.coverage | test_qa_acceptance |
| [`src/astral/qa/agreement.py`](../src/astral/qa/agreement.py) | 101 | Dual-judge agreement measurement: kappa, auto_accept helper, delegation aggregate report. | `cohens_kappa, auto_accept, aggregate_report` | qa.realization, qa.coverage | test_qa_acceptance |

Ground-truth data files (not code, hash-pinned by R04): [`src/astral/assets/grounding/biotier_routing.yaml`](../src/astral/assets/grounding/biotier_routing.yaml),
[`src/astral/assets/grounding/variable_roleplay_guide.yaml`](../src/astral/assets/grounding/variable_roleplay_guide.yaml), [`src/astral/assets/grounding/jailbreak_list.yaml`](../src/astral/assets/grounding/jailbreak_list.yaml),
<<<<<<< HEAD
[`src/astral/assets/grounding/pathogen_list.yaml`](../src/astral/assets/grounding/pathogen_list.yaml),
[`src/astral/assets/grounding/biotool_and_database_list.yaml`](../src/astral/assets/grounding/biotool_and_database_list.yaml).
=======
[`src/astral/assets/grounding/biological_agent_list.yaml`](../src/astral/assets/grounding/biological_agent_list.yaml).
>>>>>>> pr19

## Traceability matrix

| Requirement | Owning file(s) | Verifying test(s) |
|---|---|---|
| R01 | `__init__.py`, `py.typed` | test_architecture |
| R02 | all modules | test_architecture |
| R03 | this document | test_design_registry |
| R04 | cards/grounding, assets/grounding | test_grounding |
| R05 | cards/compile | test_cards |
| R06 | cards/compile, cards/contracts | test_cards |
| R07 | cards/compile | test_cards |
| R08 | cards/compile | test_cards |
| R33 | cards/tool_select, cards/compile, assets/grounding | test_grounding, test_cards |
| R09 | cards/compile | test_cards |
| R10 | cards/compile, cards/grounding | test_cards |
| R11 | all modules | test_architecture |
| R12 | cards/contracts | test_cards |
| R13 | cards/compile | test_cards |
| R14 | cards/grounding, cards/compile | test_grounding, test_cards |
| R15 | cards/compile | test_cards |
| R16 | runtime/run | test_runtime |
| R17 | runtime/run, runtime/engines | test_runtime |
| R18 | runtime/engines | test_runtime |
| R24 | bridge/bloom | test_bridge |
| R25 | scripts/metrics_report | test_metrics |
| R19 | cards/grounding, assets/grounding | test_grounding |
| R20 | cards/grounding, assets/grounding | test_grounding |
| R21 | cards/grounding | test_grounding |
| R22–R23 | (deferred — ablation process and human gate, no CI claim) | — |

## Type checking

Strict mypy is the blocking type gate. ty is an advisory second opinion and must
be invoked with an explicit interpreter:

```bash
ty check --python .venv/bin/python src
```

CI and the gate manifest run that same frozen command as non-blocking. Promote ty
to a blocking AND-gate only after it is pinned, CI-stable, and false-positive quiet.
Do not replace mypy with ty.

## Change process

1. **Add or change a requirement atomically.** One requirement, one owner, one
   enforcement mechanism.
2. **Register every file.** New modules enter the registry with function, public
   surface, dependencies, and tests in the same commit; deletions remove their rows
   in the same commit. Removed code persists in git history and the archive tag;
   it is never imported.
3. **Admission for new components:** deterministic default first, then a one-variable
   ablation against the frozen control with persisted outputs, raw failures, and a
   recorded decision. Components that do not beat the control are dropped.
4. **Subjective checks stay deferred.** Realism, coverage claims, and validity
   (R22–R23) are never claimed from CI or a single run, and never asserted by the
   model that produced the artifact.
5. **Doc truthfulness:** public docs describe current behavior. Planning history
   lives outside tracked documentation.
| [`src/astral/scanner/refusal.py`](../src/astral/scanner/refusal.py) | 82 | Refusal benchmark: run a target model through multi-turn elicitation and measure its refusal trajectory, rate, persistence, break turn. | \`refusal_run\`, \`bench_refusal\` | scanner.trajectory, runtime.model | test_scanner_refusal |
