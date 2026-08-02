# Roadmap

ASTRAL is rebuilt one component at a time, each earning its place against the
deterministic control before the next is admitted.

## Done

1. **Stage 1 — actor cards** (`cards/`): deterministic matched pairs compiled from the
   vendored ground truth: BioTIER routing registry, variable roleplay lookup, unified
   biological agent list, and jailbreak technique lookup. Seeded route permutations cover the full
   route universe without repeats.
2. **Stage 2 — deterministic runtime control** (`runtime/`): grounded fixture engines
   play cards into transcripts with per-turn provenance and byte-identical artifacts.
3. **Bloom bridge** (`bridge/`): cards emit as Petri Bloom behaviors and round-trip
   through Bloom's own loader, ready for the model-runtime comparison.

## Next, in dependency order

1. **Model user-simulator ablation**: a model-backed user plays the same cards against
   the fixture control. Measured on realization, diversity, cost, and variance.
2. **Assistant-side empirical arm**: the evaluated assistant model in the same loop,
   one variable changed at a time.
3. **Scanner heads**: route and rubric judgment over visible transcripts, independent
   heads, labels joined after inference. Structured outputs are a candidate use for a
   validation layer.
4. **Basin KPI**: route-coverage and family-distribution reporting across generated
   corpora, with governance-evasion capped as one small family.
5. **Inspect AI / Inspect Scout adapters**: reintroduced over the same contracts once
   the empirical arms exist to replay and scan.

Every item lands with offline tests, a metrics report (`make metrics`), and an
installed-surface check before it is called admitted.
