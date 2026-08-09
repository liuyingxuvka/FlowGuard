# Model-Test Alignment Protocol

This route compares one current behavior obligation with its primary external
`CodeContract`, observable boundary, and current test evidence. It reports
alignment; it does not split code, models, or test execution.

## Trigger

Use this route when model obligations, external code behavior, and tests must
be compared row by row. Return undefined behavior to `flowguard`; hand large,
slow, layered evidence to TestMesh.

## Conditional Local Material

Read only the files whose trigger is present; each triggered file is mandatory.

| Trigger | Required reference |
|---|---|
| transitions, state cells, closure/retry, or parent-child traces | `model_test_transition_protocol.md` |
| field add/remove/rename/migration/projection | `model_test_field_protocol.md` |
| file, schema, serialized output, archive, or artifact payload | `model_test_payload_protocol.md` |
| a reusable long-form drafting prompt is needed | `templates/model_test_alignment_prompt_template.md` |

## Ownership Boundary

- Model-Test Alignment owns coverage bindings and gap classification.
- The behavior/model owner defines semantics.
- The primary code path owns the external `CodeContract`; a facade may only
  delegate and must have current no-independent-success evidence.
- TestMesh owns large evidence partitions and receipt reuse.
- DevelopmentProcessFlow owns execution order and freshness propagation.

Target-product roles remain inside the target model. This route records model,
contract, path, and evidence identities; it does not invent product users or
permissions for FlowGuard itself.

## Required Intake

Group the intake so omissions stay visible:

- identity — obligation id, behavior plane, intent/commitment id, selected
  primary path, candidate model fingerprint, and inventory revision;
- required evidence — native good case, one bad case per protected failure,
  oracle, current test ids, result artifacts, and covered obligation ids;
- external boundary — owner `CodeContract`, inputs, outputs, errors, side
  effects, timing/retry semantics, and any delegating facade;
- result: current terminal status, stable finding ids, skipped/not-run rows,
  scoped dispositions, and typed next owner;
- freshness: source versions, verifier versions, evidence fingerprints,
  invalidations, and currentness decision.

## Alignment Rows

For every in-scope obligation, emit one row containing:

1. model obligation and stable intent/commitment/path identity;
2. exactly one primary external `CodeContract` owner;
3. observable boundary and any required state/field/payload projection;
4. current positive, failure, negative, and replay evidence;
5. disposition: `covered`, `partially_covered`, `not_covered`, or typed
   delegation;
6. freshness and exact proof artifact identity.

Full confidence requires every obligation to have one owner contract and
current same-plane evidence. Opaque family/canonical-relation ids do not count unless
their actual member obligations are enumerated.

## Model-Purpose Gate

Before creating or materially changing a concrete model instance, freeze its
task-specific protected failures and claim boundary. Bind the exact candidate
to native good, per-failure bad, oracle, and current evidence. Reusable types
are not permanently single-purpose, and only declared FlowGuard checks may
support completion claims.

## Path-Quality Evidence Binding

For each affected new or materially changed model, consume the exact compact
`PathQualitySubject` and `PathQualityResult` from ModelMaturation. Verify that
the subject's model, purpose, effective intent, obligation, provider,
dependency, code, test, oracle, evidence, retained-element inventory, and
currentness fingerprints match the alignment row and accepted revision.

Bind every hard-semantic dimension affected by a proposed rewrite and every
retained-element `NecessityWitness` to the same current model owner, primary
`CodeContract`, exact test/native member, executable oracle, and terminal
evidence, or to one explicit scoped disposition. Test or runtime evidence may
support a witness only under its native owner; the model element's existence,
path-quality self-description, compact result, parent receipt, or copied suite
receipt cannot license it.

This route verifies bindings and current evidence. ModelMaturation alone owns
light/deep path review, candidate comparison, Pareto dominance, and bounded
path-quality conclusions. Keep a behavior-changing candidate in
`normative_target`; never align it as current `observed` implementation before
code, topology, tests, and evidence match. Missing, stale, unresolved,
cross-owner, aggregate-only, or normative-as-observed rows remain exact gaps.
The same binding shape applies to non-Python software and non-code workflows;
use their native implementation/resource/verification owners without
fabricating code or pytest members.

## Source Audit

Audit the selected primary path and all executable delegators. Reject:

- two primary paths for the same intent;
- helper-only proof with no public-boundary observation;
- stale, skipped, progress-only, or unbound evidence;
- code/runtime target names treated as semantic proof without currentness;
- locally green subsets promoted to full coverage;
- model, test, and code rows that refer to different behavior planes.

## Independent Blueprint Alignment

Use this extension only for an explicit whole-software blueprint/export/
qualification claim or an owner-declared release obligation. Ordinary
Model-Test Alignment consumes only the affected obligations, contracts,
implementation surfaces, and evidence; it does not scan or load the whole
repository.

Blueprint alignment consumes the current independent implementation inventory
and an immutable binding report. It checks both directions:

1. every required model obligation has exactly one current primary
   implementation binding; and
2. every behavior-bearing implementation surface has a current model
   obligation and owner-contract binding, while a pure helper may instead have
   one `supports` or `calls` relation to a unique owning implementation.

The independent inventory, not caller-declared `CodeContract`s, defines the
source denominator. Block omitted or unresolved surfaces, orphan helpers,
hidden state/effect writers, duplicate primary implementations, stale model,
contract, source, inventory, or binding fingerprints, and mismatched planes.
Do not turn every internal helper into an external CodeContract.

A path and symbol prove traceability only. A blueprint-required binding must
also cite current source-independent semantic specifications and applicable
oracles for input/output shapes, state/effect changes, errors, and relevant
ordering, retry, timeout, and decision rules. Missing semantic or oracle
references keep blueprint closure incomplete even if ordinary
model-code-test alignment is green.

This route reports static alignment evidence only. It does not export a
blueprint.

## Closure And Mesh Handoff

When ModelMesh closure applies, include
`model_mesh_closure_to_transition_coverage` across happy-path, failure-path, negative-path, and replay
evidence. Missing transition or repair coverage is a
typed handoff, never an implicit pass.

Large or layered gaps go to TestMesh. Undefined semantics go to `flowguard`.
Field lifecycle gaps go to FieldLifecycleMesh. Broad confidence goes to
RiskLedger; ClosureContract only checks terminal integrity and agreement.

## Required Findings

At minimum detect missing owner contracts, duplicate primary paths, stale or
missing tests, orphan tests, uncovered failures, field/payload gaps, facade
drift, plane mismatch, and unresolved mesh closure coverage. For blueprint
scope also detect omitted inventory surfaces, unresolved dispositions, orphan
helpers, hidden writers/effects, duplicate primary bindings, path-only
bindings, semantic/oracle gaps, and stale inventory/binding identities.

## Output And Completion

Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`,
`claim_boundary`, `typed_next_actions`, alignment rows, and a small diagram
whose edges explicitly mean covers, partially covers, or does not cover.

Completion requires exact row coverage or visible typed dispositions for every
in-scope obligation. Do not claim code correctness, full test execution, or
broad product confidence from alignment alone.

Blueprint-scoped completion additionally requires exact bidirectional set
closure and source-independent semantic/oracle references. It still does not
prove whole blueprint qualification.

## Revision Evidence Binding

After any model, contract, primary-path, test, verifier, or inventory change,
invalidate only the rows that consume the changed identity, refresh their
evidence, and preserve unaffected current rows by exact fingerprint.

A path-quality subject/result/detail identity change follows the same rule and
also reopens any alignment row that supplies one of its hard-semantic
obligations or necessity witnesses. Exact unchanged rows remain reusable; no
deep review is implied by reuse alone.

## `model_code_test` Blueprint Layer

This route owns row-level `model_code_test` alignment. In explicit
whole-software scope, each required row binds one model obligation, one
source-independent semantic rule, one external owner `CodeContract`, one
   behavior-bearing implementation surface, one owner-declared case, one
   accepted case-and-dimension checker design assigned to an exact
   project-test-inventory node or native-check owner, and, for executed claims,
   one current terminal evidence receipt. The project blueprint must embed that
complete `ProjectTestInventory`, and alignment consumes it only after an
independent read-time audit against current test source. Both model-to-code and behavior-bearing
code-to-model directions must close.

A green parent suite, test file, helper-only test, aggregate count, generated
case, or unaccepted checker cannot satisfy the static design. A `not_run` row
cannot satisfy an executed-evidence claim. TestMesh supplies exact
test/evidence inventory and hierarchy but never invents the semantic rule.
Undefined semantics return to their native model owner. Missing, duplicate,
ambiguous, or stale owners block without fallback.

Whole-software alignment is explicit-only; ordinary alignment recalculates
affected rows. Return canonical `deepest_proven_layer` from the complete prefix
and the first unresolved owner/member/evidence gap, but never upgrade another
layer. User choice, maturation, and implementation admission remain separate.

Canonical blueprint alignment separates `BehaviorCaseContract`,
`BehaviorCoverageEdge`, and `CoverageExecutionEvidence`. Every static edge
names an exact behavior block, its block-local implementation surface and
portable input/output/state binding, concrete literal or symbolic-contract
owner-declared case, source-case lineage, semantic rule, oracle,
accepted dimension checker design, and its current pytest/native-check owner.
For an existing modeled target, the behavior's intent reference must be active
in the accepted revision's complete `CurrentEffectiveIntentView` and licensed
by the exact binding for that behavior's model owner. A latest delta, history
fold, root intent, textual similarity, or implementation path cannot fill an
empty or cross-owner intent row.
A delegated assertion helper counts only
through an explicit current acyclic call graph that terminates at real oracle
members. Placeholder cases, generated test ids, owner-wide receipts, and
full-suite receipts cannot be copied to satisfy unrelated blocks; execution
remains a separate `not_run|pass|fail|blocked` fact.

For every executed `pass`, verify the existing receipt and verification result
against the row's exact producer owner, subject, covered coverage/test/native
member, model and implementation fingerprints, inputs, toolchain, environment,
terminal result, currentness, and eligibility. A validation-parent receipt is
only parent evidence. The same leaf receipt identity cannot appear under two
native owners; one owner's receipt may cover several of that owner's affected
members only through one exact merged owner reference. Multi-owner integration
is shareable only when explicitly typed and its complete owner/member set is
declared.

## Coverage ownership in the portable projection

Every behavior block, case, and coverage edge binds to one current checker or
native test member and one execution owner. The portable projection preserves
those binding and coverage fingerprints; the compact view only bounds display.
Static checker design, portable materialization, and terminal execution remain
separate. A parent receipt without an explicit typed coverage set cannot fan out
to leaf obligations.
