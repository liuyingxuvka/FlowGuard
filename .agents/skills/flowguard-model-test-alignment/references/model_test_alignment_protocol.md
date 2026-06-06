# Model-Test Alignment Protocol

Use Model-Test Alignment when a FlowGuard model and ordinary tests both exist
and the question is whether they cover the same obligations. For any required
behavior in the confidence claim, include owner code external contracts between
the model obligations and the test evidence.

This protocol is independent from TestMesh, StructureMesh, and ModelMesh.
It does not split tests, split code, split models, or read mesh reports. It
compares explicit model obligations, required owner code external contracts, and
plain test evidence.

When a change touches behavior-bearing fields, consume FieldLifecycleMesh
reports or projections. `field_lifecycle_to_model_obligations(...)` and
`field_lifecycle_to_code_contracts(...)` turn field rows into the same
obligation and owner-contract rows this protocol already compares.

When the claim covers state transitions, derive a transition coverage matrix.
Use `TransitionCoverageMatrix` and
`transition_coverage_to_model_obligations(...)` so each required
`Input/Event x State -> Output x State` cell becomes an explicit
`transition_coverage` obligation. When a transition cell names a code contract,
also project it with `transition_coverage_to_code_contracts(...)`. Evidence for
a transition cell should use a stable target id and cover the same code
contract; large or slow matrices can project required cell ids to TestMesh
through `transition_coverage_to_required_leaf_cell_ids(...)`.

When the result supports a final done, release, publish, or full-confidence
claim, pass the obligation ids, code contract ids, test evidence ids, statuses,
freshness, and assertion scopes into a Risk Evidence Ledger. Alignment proves
rows agree; the ledger decides whether the broader user-risk claim is full,
scoped, or blocked.

For non-trivial bug repairs and recurring or high-risk same-class model misses,
alignment evidence is an input to closure and to the defect-family gate. Bind
the repaired model obligation, the owner code external contract, the
observed-regression test, and the same-class generalized test to the same
behavior before the Risk Evidence Ledger claim; do not make Model-Test
Alignment the family promotion route.

For related obligations that share a family-level confidence claim, add
`ObligationFamily` and `ObligationFamilyEvidence` rows. The family parity check
is not the defect-family gate; it verifies that every sibling obligation has
the same required mechanism coverage from allowed provenance sources before the
family claim is treated as full confidence.

When real code observations are available for a finite code boundary, add the
code-boundary conformance layer before trusting a hand-authored code contract.
This layer checks whether real code accepted only allowed input cases, rejected
forbidden input cases, and emitted only declared outputs, state writes, side
effects, and error paths. Use `CodeBoundaryContract`,
`CodeBoundaryObservation`, and `review_code_boundary_conformance()`. It checks
the code boundary; it is not a new skill and not a replacement for full trace
replay.

When the finite code boundary belongs to a leaf model in a parent/child mesh,
upgrade the boundary observations into a leaf boundary matrix. A matrix row is
one `Input x State` cell and records allowed outputs, next states, state
writes, side effects, error paths, evidence ids, status, and freshness. A leaf
model can support parent confidence only when every finite cell is current and
passing, or when the leaf is split further or explicitly scoped.

When real-code progress is being compared to the model, add runtime path
evidence rows. Each runtime node observation must name `model_id`,
`model_path`, `node_id`, run id, status, and the model obligation or code
contract when known. Anonymous logs or helper-only progress messages are not
model-test alignment evidence.

When a Model Topology Hazard Review names an anchored future-use hazard with a
model/test disposition, treat the hazard id as a model obligation source. Bind
current tests or code-boundary observations to that hazard, or return the gap
to model maturation and Risk Evidence Ledger.

When real Python source and tests are available, add the conservative source audit
layer before trusting hand-authored rows. This layer reads Python ASTs to
generate or check `PythonCodeContractEvidence` and
`PythonTestAssertionEvidence`, then feeds the resulting rows and confidence
boundaries into the same Model-Test Alignment review. Use
`audit_python_code_contracts()`, `audit_python_test_assertions()`, and
`review_python_contract_source_audit()` when the Python source is available.
It is an evidence collector, not a semantic proof engine.

## Trigger

Create or update a model-test alignment review when:

- a FlowGuard model adds or changes scenarios, invariants, hazards, state
  transitions, or input/output contracts;
- a report claims that modeled state transitions have matching test coverage;
- a public function, API, CLI, facade, adapter, persisted output, or other
  externally visible code surface is expected to implement a model-backed
  obligation;
- tests are added or changed for model-backed behavior;
- behavior-bearing field lifecycle projections need test and code-contract
  proof;
- a report claims that model coverage and test coverage agree;
- a report claims that code contract coverage and test coverage agree for a
  model-backed behavior;
- a model pass and test pass need to be reconciled before release or broad
  completion;
- a bug repair or post-runtime model-miss repair needs proof that tests cover
  both the observed regression and the same-class generalized bug family
  through the owner code contract;
- several sibling obligations are being promoted as one family-level claim and
  need required mechanism coverage with allowed provenance;
- reviewers suspect orphan tests, orphan code contracts, duplicated test
  claims, duplicated code contract owners, stale evidence, internal-path-only
  tests, or happy-path-only coverage of risky model obligations.
- declared `CodeContract` or `TestEvidence` rows need to be checked against
  real Python source/test files before a coverage claim is trusted.
- alignment evidence suggests the model is missing an obligation, code-boundary
  observation, state branch, split child obligation, or current evidence refresh;
  feed those rows to `review_model_maturation_loop(...)`.
- declared code boundaries need runtime observation evidence showing allowed
  inputs, rejected inputs, outputs, errors, state writes, and side effects
  stayed inside the model-declared boundary.
- topology-anchored future-use hazards need ordinary test, boundary, or
  evidence rows before they can support broad confidence.

Do not trigger this protocol merely because tests are large or slow. Use
TestMesh for parent/child test hierarchy problems. Do not trigger it merely
because source structure is being split. Use StructureMesh for code or API
partition problems.

## Input Checklist

Use grouped field families instead of a blank for every possible detail.

`ModelObligation` rows should capture:

- identity: id, type, required flag, and short description;
- required evidence: test kinds, closure role when this comes from a model
  miss, and whether shared evidence or implementation is allowed;
- external boundary when relevant: inputs, outputs, state reads/writes, side
  effects, error paths, and exactness.
- transition coverage source when generated from a matrix: cell id, source
  state, trigger, target state, expected output, and required test kinds.
- field lifecycle source when generated from FieldLifecycleMesh: field id,
  projection id, behavior impact, old-field disposition if relevant, and owner
  route.

`CodeContract` rows are required for required model obligations in the current
confidence claim. Capture:

- identity: contract id, path/symbol/surface type, role, and required flag;
- binding: implemented model obligation ids;
- boundary: inputs, outputs, state, side effects, error paths, and exactness;
- source audit status when available: AST-supported, partial, missing,
  ambiguous, dynamic, or manual-review-required.

`TestEvidence` rows should capture:

- identity: evidence id, test name/path/command, and test kind;
- result: passed, failed, timeout, skipped, not-run, running, or error;
- freshness: current, stale reason, reuse ticket, and proof artifact when an
  old result is reused;
- binding: covered obligation ids, code contract ids, evidence target id, and
  assertion scope. A test that proves a model obligation must cover a code
  contract implementing the same obligation;
- risk notes: overclaim, internal-path-only, source-audit caveat, or model-miss
  closure role.

Expand only when applicable:

- `ObligationFamily` rows for sibling obligations promoted as one claim.
- FieldLifecycleMesh reports or `FieldProjection` rows for behavior-bearing
  fields.
- `CodeBoundaryContract` and `CodeBoundaryObservation` rows for exact closed
  code boundaries.
- Leaf boundary matrix rows when a finite leaf model is being proved.
- `ModelObligation` rows for model-topology hazard candidates that became
  testable obligations.
- `TransitionCoverageMatrix` rows when transitions should become required test
  targets.
- Detailed source-audit notes when AST-visible code or tests are reviewed.

## Conservative Source Audit Checklist

Use this checklist only when real Python source or tests are in scope:

Record the audit as four grouped notes:

- code surface: symbol, path, signature, returns/raises, state writes, side
  effects, and unsupported dynamic behavior;
- test assertion: called symbol, assertion forms, expected exceptions,
  output/state/call/persisted-output checks, and fixtures/monkeypatching that
  affect confidence;
- binding confidence: explicit ids, reviewer maps, direct calls, or name-only
  candidate matches;
- coverage status: assertion scope plus execution status and freshness.

The audit must never claim perfect Python semantics. It also must not replace
conformance replay when production state, durable side effects, external
systems, trace-level behavior, or adapter projection is part of the confidence
claim.

## Required Findings

Keep findings visible by family instead of expanding every code in routine
reports:

- missing or stale coverage: missing required test kinds, missing current
  passing evidence, stale evidence, and non-passing evidence;
- code contract gaps: missing owner contracts, omitted behavior, extra exact
  behavior, and missing external-contract test evidence;
- boundary conformance gaps: missing allowed/rejected observations, forbidden
  accepted inputs, unknown accepted inputs, and extra outputs/errors/state
  writes/side effects;
- binding gaps: orphan tests or code contracts, unknown references,
  model/code/test mismatches, supporting evidence without a target, leaf matrix
  evidence without a cell id, and transition-cell evidence without a matching
  target id;
- duplication and granularity gaps: duplicate owner claims or obligations too
  coarse for primary evidence;
- model-miss gaps: missing observed-regression evidence, missing same-class
  evidence, missing owner code contract binding, or internal-path-only closure
  evidence;
- source-audit gaps: partial, dynamic, ambiguous, or manual-review-required
  audit findings.

## Prompt Template

Use `references/templates/model_test_alignment_prompt_template.md` only when
delegating or scaffolding a fresh review. Ordinary route use should follow the
checklists above without loading the full prompt body.

## Completion Standard

A model-test alignment review can support a coverage claim only when:

- required obligations have current passing evidence for required test kinds;
- required transition coverage cells have current passing evidence or are
  explicitly scoped out with a reason;
- required code contracts and exact boundaries preserve declared external
  behavior without hidden extras;
- required owner code contracts have current external-contract or mixed-scope
  test evidence;
- model-miss repairs have both observed-regression and same-class evidence when
  they are in scope;
- orphan, unknown, duplicate, stale, skipped, failed, timeout, not-run, running,
  internal-only, and overclaim findings are either absent or explicitly scoped;
- missing obligations, boundary mismatches, stale rows, and duplicate primary
  edge paths are fed to `review_model_maturation_loop(...)` before broad
  confidence;
- unresolved alignment gaps that cannot be fixed in the current task are kept
  as maintenance obligations instead of being left as prose TODOs;
- final claims supply enough evidence ids, assertion scopes, and gaps for
  `review_risk_evidence_ledger(...)`;
- conservative source-audit output is not overclaimed as semantic proof or
  production conformance.
