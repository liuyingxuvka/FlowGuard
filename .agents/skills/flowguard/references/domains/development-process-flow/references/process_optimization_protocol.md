# Conditional Process Optimization

Use this reference only when one of these reasons is present:

- `explicit_request`
- `multiple_equivalent_routes`
- `material_rework_risk`
- `diagnostic_boundary_choice`

Otherwise return `not_needed` and create no optimization records.

## Hard Equivalence Before Preference

Compare candidates only after they match on all six boundaries:

1. terminal outcome;
2. required obligations and evidence/claim boundary;
3. safety and hard invariants;
4. protected side effects;
5. dependency authority;
6. execution-owner authority.

A mismatch is a rejection, not a cost tradeoff.

## Two Composable Choices

Choose one diagnostic boundary:

- `targeted`: the smallest informative affected boundary;
- `declared_complete`: every item in a named finite boundary;
- `budgeted`: a named time, cost, or side-effect limit, with remainder visible.

Choose one execution mode:

- `sequential`;
- `safe_parallel`, only with current dependency, mutable-state, side-effect,
  and execution-owner isolation evidence.

A hard blocker universally stops invalid descendants. Material new evidence
universally stales the decision. Neither needs to be a selectable strategy.

## Evidence And Selection

The decision lists its current evidence ids. Candidate comparison, isolation,
repair relations, ownership, and revalidation references must all resolve
within that current evidence boundary.

Each candidate declares one ordered `step_ids` list and an acyclic
`dependency_edges` graph. The declared order must be a real linearization of
every edge; an acyclic graph with a contradictory list is ineligible. Bind each
step to its artifact reads, writes, invalidations, validations, execution
owner, protected side effects, and comparable effort. A measured candidate
also binds every step cost to current cost evidence; a missing step cost or
evidence blocks measured comparison instead of becoming zero.

For the declared hard-equivalent set, derive the six visible dimensions
`invalidated_output`, `repeated_write`, `repeated_validation`, `coordination`,
`side_effect_exposure`, and `effort` as a vector. Missing values are not zero;
mixed comparison bases or incomplete vectors are ineligible for comparison.
Select only one candidate that Pareto-dominates every other eligible candidate.
When equal candidates or trade-offs remain, return the non-dominated ids and
keep selection unresolved. Declaration/lexical order, an unexplained scalar
sum, and caller preference cannot break that boundary.

Reject a candidate that fails hard equivalence, currentness, dependency,
step-metadata, cost, or evidence admission and expose its exact rejection
findings. A rejected non-selected alternative does not block selection from
the remaining valid hard-equivalent set. Block when every candidate is
rejected, the candidate-set identity is untrustworthy, or the caller points to
an invalid or higher-cost candidate.

For a unique selected candidate, emit a model-derived rationale naming the
candidate and each comparable dimension. Preserve caller rationale separately
as context; it neither selects the candidate nor substitutes for the derived
Pareto explanation. A selected result without that explanation is blocked.

Qualitative or measured evidence supports only a Pareto-dominating process
candidate within the declared hard-equivalent set. Never claim a scalar
minimum or unrestricted global optimum. This process-order comparison is not a
single-model path-quality conclusion: ModelMaturation owns model-path
`single_clear_path`, finite-set minimum, non-dominated, and local-
irreducibility vocabulary under its own exact evidence boundary.

## Repair And Revalidation

TestMesh supplies the diagnostic boundary and execution evidence. Finding
Ledger supplies raw ids. Several findings enter one `ProcessRepairGroup` only
with relation evidence and a falsifiable root-cause claim. Use ordinary
Model-Test Alignment evidence for affected obligations, the primary code
owner, and tests. The group remains open until all required affected
revalidation ids are current.

## Original Example

When several related tests are cheap and valid, finish a declared diagnostic
boundary before editing so one underlying defect can be repaired once. When a
missing prerequisite or safety failure makes later tests invalid, stop and
record them as not run. This preserves the user's goal without making
"run every test first" a universal rule.

## Public Shape

The existing DPF route exposes five records and one review:

- `ProcessOptimizationContract`
- `ProcessOptimizationCandidate`
- `ProcessRepairGroup`
- `ProcessOptimizationDecision`
- `ProcessOptimizationReport`
- `review_process_optimization`

Do not add another route, skill, commitment, model owner, compatibility
reader, or alternate success vocabulary.
