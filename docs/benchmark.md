# ASTRALBench: Eval and Benchmark Design

The eval and benchmark design that capitalizes on the paired multi-turn corpus
as a golden dataset, a reference scanner evaluation, a benchmark protocol, and
the multi-turn BioTIER flagship measurement.

## Decision and study type

Benchmark design. Stakeholders (detection teams) value golden datasets,
benchmarks, and evaluations as integration points over custom graders, which
they already own. The corpus is the product; the benchmark is the protocol any
detection model runs against; the ASTRAL scanner is the reference baseline.

## Threat model and construct

Detection teams need golden labeled biothreat conversations to train and
evaluate their own detection models. Single-prompt refusal benchmarks (BioTIER)
cannot measure whether a model's refusal holds under sustained multi-turn
elicitation. The corpus enables a multi-turn, paired, per-variable benchmark.

## The four-layer design

### Layer 0: Scanner evaluation (reference baseline)

The ASTRAL scanner is the reference detection model — the baseline to beat.

- Per-variable accuracy (SC/JB/KC/SP/AT/AV) against ground truth.
- Side discrimination: malicious vs benign twin.
- RB false-positive rate on near-neighbors.
- Slice breakdown by difficulty (high-SC, late-KC, tool-bearing, agentless).
- Compliance-quadrant agreement with the BioTIER labels.
- Robustness across target models, routes, and reasoning levels.

Acceptance: the scanner metric suite computes on the corpus and is reported as
the reference score.

### Layer 1: Golden dataset (the product)

- ~1000 paired transcripts: malicious/benign twins, same route, same variables.
- Per-variable labels (SC/JB/KC/SP/AT/AV).
- Compliance quadrant per log (permitted, correct_refusal, correct_permit,
  over_refusal).
- Difficulty slices (high-SC, late-KC, agentless, tool-bearing).
- Train/test splits for model training.

Acceptance: dataset card documents composition, labels, splits, and provenance.

### Layer 2: Benchmark protocol (the integration point)

Stakeholders run their own detection model; the protocol returns standardized
metrics. No custom grader is imposed.

- Per-variable accuracy.
- Side discrimination.
- RB false-positive rate.
- Slice breakdown.
- Leaderboard comparison against the reference scanner score.

Acceptance: the protocol runs an arbitrary detection model against the corpus
and returns the standard metric suite.

### Layer 3: Multi-turn BioTIER (the flagship)

The measurement single-prompt benchmarks cannot produce.

- Refusal trajectory: does a turn-1 refusal hold across turns.
- Break turn: the turn a refusing model starts complying.
- Technique-by-turn: which jailbreak methods break which models at which turn.
- Two-axis trajectory: refuse-compliance and permit-compliance as curves.

Acceptance: per-turn compliance is computable from the corpus and reported as a
trajectory.

## Inputs, outputs, interfaces

- Inputs: `data/cycles/dataset/` (dataset.eval, dataset-train/test.json).
- Outputs: reference scanner metric suite, benchmark protocol results,
  multi-turn compliance trajectories.
- Interfaces: `astral.scanner.run.scan_eval`, `astral.scanner.optimize`,
  `astral campaign` for corpus regeneration.

## Dependency-ordered phases

1. Layer 1 dataset card + train/test split verification.
2. Layer 0 scanner reference eval on the corpus.
3. Layer 2 benchmark protocol (run an external model against the corpus).
4. Layer 3 multi-turn BioTIER trajectory metrics.

## Metrics and acceptance gates

- Reference scanner: per-variable accuracy and side discrimination computed on
  the corpus with uncertainty.
- Protocol: an external detection model scores on the same metrics.
- Flagship: refusal trajectory and break-turn computed per multi-turn log.

## Risks

- Scanner self-evaluation: the reference scanner must not be its sole validator;
  external models provide the comparison.
- Label leakage: ground truth stays in metadata, never the visible transcript.
- Over-refusal blind spot: the RB surface must measure over-flagging, not just
  detection.

## Successor work

- Long-horizon trajectory generation (session arcs, escalation clustering).
- External detection-model leaderboard.
- Embedding-filter reference evaluation.
