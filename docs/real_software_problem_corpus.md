# Real Software Problem Corpus

Phase 10.6 defined a roadmap-independent corpus of real software problem cases.
Phase 10.7 expanded it with gap-focused stress cases. Phase 10.8 added an
executable corpus harness that ran every corpus case through a flowguard
checker. Phase 11 upgrades that harness into real workflow-family-specific
model bindings. The final pre-freeze baseline adds pressure cases for progress,
eventual obligations, refinement/projection, and benchmark artifact stability.
The corpus is not a roadmap mapping. The executable harness is the
behavior-test layer built from the corpus.

The goal is to avoid designing tests only around the feature currently being
built. A case belongs in the corpus because it represents a real software
workflow risk, not because current flowguard can already check it.

## What The Corpus Is

The corpus is a deterministic set of structured problem cases. Each case
describes:

- the software domain;
- the workflow family;
- the software structure;
- the operation boundary;
- the actors;
- the input pattern;
- the initial state shape;
- the state transition focus;
- the side effects;
- the expected behavior;
- the forbidden behavior;
- the failure mode;
- the evidence to check;
- the oracle nature;
- the case kind;
- the importance.

The current generated corpus contains 2100 problem-intent cases:

- 25 workflow families;
- 92 observed failure modes across broad, gap-focused, and pressure cases;
- 11 software domains;
- 34 observed oracle types;
- 5 case kinds.

The corpus is split into three sections:

- `base_1500`: broad structured coverage across the main workflow families;
- `gap_500`: targeted stress cases for weak spots that broad coverage can
  underrepresent;
- `pressure_100`: pre-freeze pressure cases for future progress, temporal,
  refinement, projection, and benchmark-stability checks.

## What The Corpus Is Not

The corpus is not a roadmap mapping. Case records must not contain:

- future phase ownership;
- current support status;
- implementation assignment;
- benchmark ownership;
- capability assessment.

Those are later analysis layers. The problem corpus itself only describes real
software situations and the evidence a checker should eventually inspect.

The corpus quality report therefore states:

```text
count_semantics: problem_intent_cases
execution_claim: not_executable_tests
```

This prevents `total_cases: 2100` from being misreported as 2100 behavior
tests. The executable behavior-test claim comes only from the executable corpus
review.

## Case Kinds

The current deterministic matrix uses these case kinds:

- `positive_correct_case`
- `negative_broken_case`
- `boundary_edge_case`
- `invalid_initial_state_case`
- `loop_or_stuck_case`

Each workflow family receives 60 cases:

- 12 positive cases;
- 20 negative cases;
- 12 boundary cases;
- 8 invalid initial-state cases;
- 8 loop/stuck cases.

Across 25 workflow families, this produces the `base_1500` section.

## Gap-Focused 500

The `gap_500` section adds targeted cases for nine areas that often create
real workflow bugs but are easy to under-test when a matrix is too evenly
generated:

- identity merge, split, and conflict;
- partial failure, atomicity, and compensation;
- ordering, deterministic interleavings, and duplicate delivery;
- permission, ownership, and module boundary;
- time, expiry, scheduling, and delayed inputs;
- sync, reconciliation, and source-of-truth conflicts;
- schema, migration, and version compatibility;
- audit, privacy, compliance, and traceability;
- external integration acknowledgement and idempotency.

These cases are still problem-space records. They do not say which later
feature should implement them, whether the current runtime can catch them, or
whether they are already executable. They describe what can go wrong, what
behavior is expected, what behavior is forbidden, and what evidence should be
available.

## Pressure-Baseline 100

The `pressure_100` section is part of the main durable corpus. It adds four
balanced pressure areas, each with 25 cases, spread across the existing 25
workflow families:

- bounded progress and fairness;
- eventual obligation and temporal order;
- contract composition and refinement;
- benchmark freeze and artifact stability.

These cases are deliberately included before the next mathematical upgrades.
They define the exam before the new checker exists. The progress/fairness
pressure cases currently produce `known_limitation`, because bottom-SCC-only
loop detection cannot prove forced progress for cycles with escape edges. That
status is an accepted expected-vs-observed outcome, not a pass.

## Executable Corpus Harness

Phase 10.8 mapped the corpus records into executable checks:

- non-loop cases run `Workflow + ScenarioReview + Invariant`;
- loop/stuck cases run `LoopCheck`;
- every case produces expected-vs-observed status;
- every negative or invalid case must produce an expected violation;
- every loop/stuck case must include graph evidence;
- `not_executable_yet` is a real failure for the main-corpus target.

That original Phase 10.8 harness did not claim each workflow family had a
real domain model. It proved the expected-vs-observed plumbing could run at
main-corpus scale.

Phase 11 replaces the generic corpus template with real model bindings:

- every case has `model_binding_kind=real_domain_model`;
- every case has a workflow-family-specific `model_name`;
- every case has a concrete `model_variant`;
- every case has a concrete `variant_id`;
- every case records family-specific block names and state slots;
- non-loop cases run through real domain blocks such as lease allocators,
  cache builders, migration readers, document exporters, and policy evaluators;
- loop cases use workflow-family-specific graph states and transition labels;
- `generic_fallback_cases` must be `0`.

The hard Phase 11 gate is:

```text
total_cases: 2100
real_model_cases: 2100
generic_fallback_cases: 0
not_executable_yet: 0
failure_cases: 0
model_variant_total: 150
model_families_with_six_variants: 25
```

This is stronger than `executable_cases: 2100`. It means the whole problem
corpus is now grounded in real abstract domain models, not only in a generic
execution template.

Phase 11.1 deepens this into a 150-variant benchmark:

- 25 workflow families;
- six real model variants per family;
- all 150 variants used by the 2100 cases;
- no generic fallback.

Phase 11.2 hardens the benchmark so it can remain a long-term product-grade
regression baseline:

- every variant receives at least eight executable cases;
- the current balanced corpus assignment gives each variant 13 to 15 cases;
- every workflow family covers all five required case kinds;
- every workflow family covers the required bug-class matrix;
- six priority non-job-matching families have explicit scenario seed reports;
- production conformance seed replay covers all 25 benchmark workflow families
  plus `job_matching`.

## Workflow Families

The first matrix covers broad software structures, including:

- CRUD lifecycle;
- approval and review workflow;
- task queue and leasing;
- retry with side effect;
- cache and materialized view;
- file import/transform/export;
- webhook ingestion;
- notification sending;
- payment, billing, and refund;
- inventory reservation and allocation;
- scheduler and recurring job;
- permission and role transition;
- session and token expiration;
- form submission validation;
- search, ranking, and recommendation;
- sync and reconciliation;
- migration and schema evolution;
- human-in-the-loop workflow;
- moderation and triage;
- classifier routing without API calls;
- document generation/export;
- checkout/onboarding;
- audit and compliance traceability;
- deployment release gate;
- feature flag rollout.

## Failure Modes

Failure modes are intentionally broader than current executable examples. They
include duplicate side effects, stale cache, wrong state owner, missing
traceability, closed loops, unreachable success, double lease, permission
bypass, partial commit, schema mismatch, projection hiding bugs, and downstream
non-consumable outputs.

The point is to define the exam before building future answers.

## Quality Gates

The corpus review requires:

- at least 1000 cases;
- at least 20 workflow families;
- at least 20 failure modes;
- at least 50 cases per workflow family;
- at least 100 loop/stuck cases;
- at least 100 invalid initial-state cases;
- negative cases at least as numerous as positive cases;
- no duplicate `case_id`;
- no missing required fields;
- no roadmap or current-capability mapping terms in case metadata/notes;
- limited workflow-family concentration;
- limited failure-mode concentration;
- sufficient software-domain diversity;
- sufficient expected/evidence text uniqueness.
- explicit section counts for `base_1500` and `gap_500`;
- explicit per-area counts for the nine gap focus areas;
- explicit section and per-area counts for `pressure_100`.

## How To Run

Run the corpus quality review:

```powershell
python examples/problem_corpus/run_corpus_review.py
```

The runner prints a quality scorecard for the problem-intent corpus. It must
include:

```text
count_semantics: problem_intent_cases
execution_claim: not_executable_tests
```

Run the executable behavior review:

```powershell
python examples/problem_corpus/run_executable_corpus_review.py
```

This runner executes all 2100 cases. A successful real-model report
must show:

```text
total_cases: 2100
executable_cases: 2100
not_executable_yet: 0
coverage_complete: True
failure_cases: 0
real_model_cases: 2100
generic_fallback_cases: 0
model_variant_total: 150
model_families_with_six_variants: 25
```

Run the benchmark hardening review:

```powershell
python examples/problem_corpus/run_benchmark_hardening.py
```

This runner checks variant depth, family case-kind coverage, family bug-class
coverage, priority non-job-matching scenario seeds, and production conformance
seeds.

Run the normal evidence baseline separately:

```powershell
python examples/evidence_baseline/run_baseline.py
```

The baseline says what flowguard currently executes. The problem corpus says
what real software problem space future work must keep in view.

## Why This Matters

Future phases should not invent only the tests that fit the new feature. They
should be judged against this problem corpus. Over time, more problem cases can
become executable model checks, scenario reviews, loop checks, conformance
replay checks, progress checks, or contract checks. The corpus remains the
larger independent reference set.
