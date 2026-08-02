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
current same-plane evidence. Opaque family/similarity ids do not count unless
their actual member obligations are enumerated.

## Model-Purpose Gate

Before creating or materially changing a concrete model instance, freeze its
task-specific protected failures and claim boundary. Bind the exact candidate
to native good, per-failure bad, oracle, and current evidence. Reusable types
are not permanently single-purpose, and only declared FlowGuard checks may
support completion claims.

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
references keep reconstruction closure incomplete even if ordinary
model-code-test alignment is green.

This route reports static alignment evidence only. It does not export a
blueprint or launch empirical reconstruction.

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
closure and source-independent semantic/oracle references. It still proves
neither whole blueprint qualification nor empirical reconstruction.

## Revision Evidence Binding

After any model, contract, primary-path, test, verifier, or inventory change,
invalidate only the rows that consume the changed identity, refresh their
evidence, and preserve unaffected current rows by exact fingerprint.
