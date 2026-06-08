# TestMesh Protocol

Use TestMesh when the question is not "does this FlowGuard model pass?" but
"can this parent/child test hierarchy support the parent validation claim?"

TestMesh is the test-side sibling of ModelMesh and StructureMesh. All three use
the same parent/child partition principle:

- ModelMesh partitions a large FlowGuard model into child model regions.
- TestMesh partitions a large test script, suite, or validation flow into child
  test scripts or child suites.
- StructureMesh partitions a large script, module, package, command, or API
  surface into child structural owners.

The parent TestMesh should consume child ownership and evidence contracts. It
should not inline every child test case, fixture, or internal state route. When
a child suite grows too large, it can become its own parent gate with another
local TestMesh.

Before child suite evidence can support parent confidence, derive the target
child suite/script structure from a FlowGuard validation-structure model. The
target split derivation should name the source model, target suite ids, covered
partition items, state ownership fields, side-effect ownership fields, and the
rationale for the validation split. A flat list of suites is not enough.

Layered proof adds four evidence kinds that TestMesh must keep distinct:
parent coverage tests, child disjointness tests, child reattachment tests, and
leaf boundary-matrix tests. A broad parent test command cannot replace missing
leaf matrix evidence, and release-only/background progress cannot support a
routine parent proof until it has final current pass artifacts.

Transition coverage matrices can also feed TestMesh. When Model-Test Alignment
or UI Flow Structure produces required transition cell ids for a large, slow,
or browser-heavy matrix, TestMesh owns the parent/child evidence hierarchy for
those ids. It preserves the model obligation and code contract target ids for
downstream alignment. It does not decide the semantic transition obligation;
Model-Test Alignment still proves that model obligation, owner code contract,
and external-contract test evidence bind the same behavior.

Artifact payload matrices can feed TestMesh the same way. When import/export,
generated artifact, or AI work-package validation has many accepted/rejected
payload cases, TestMesh owns child-suite partitioning, result artifacts,
background completion, and freshness for those case ids. It preserves payload
contract ids and case ids for downstream Model-Test Alignment, which still
decides whether observed output, error path, state writes, side effects, and
round-trip behavior match the payload contract.

## Trigger

Create or update a TestMesh when:

- a test or regression command is slow enough that routine agents skip it,
  timeout, or cannot wait for it before continuing useful work;
- a large test script or suite is being split into smaller child suites or
  child test scripts;
- one large command mixes unrelated behavior, state, side effects, or release
  gates;
- a parent validation claim depends on several child suites, background jobs,
  adapters, or manual checks;
- skipped, stale, timeout, not-run, or progress-only evidence could be hidden
  inside a green summary;
- `review_auto_mesh_splits(...)` reports a required test split for slow,
  large, broad, progress-only, or release-only direct validation evidence;
- release-only suites should stay visible without blocking routine local
  confidence.
- a transition coverage matrix is too large, slow, browser/manual-heavy, or
  release-only for direct flat evidence rows.
- an artifact payload matrix for file import/export or AI work packages is too
  large, slow, browser/manual-heavy, or release-only for direct flat evidence.

When DevelopmentProcessFlow classifies a failed or blocked validation as
`test_too_thick`, slow/layered validation, stale/skipped/progress-only
evidence, release-only evidence, or automatic split evidence that is being
hidden inside a parent confidence claim, this protocol owns the handoff. Keep
the broad command as a parent gate or compatibility check, derive child
suites/scripts, record child evidence status, and require parent validation
confidence to consume current child evidence. A later green broad command by
itself does not close a
TestMesh handoff if child evidence remains hidden.

## Partition Checklist

## Target Split Derivation

For the parent test gate, record a target split derivation before green parent
confidence:

- source FlowGuard validation-structure model id;
- target child suite or script ids;
- parent partition items represented by the target validation split;
- state and side-effect owner fields that shaped the split;
- rationale for why these suites/scripts are the target validation structure.

Missing, source-less, target-less, unknown-suite, prose-only, or
coverage-incomplete derivations are blockers. TestMesh still does not run tests;
it derives the target validation layout, then reviews the evidence supplied by
the registered child suites/scripts.

For the parent test gate, list each partition item as a grouped ownership row:

- boundary: behavior, workflow, state, module, command, side effect, invariant,
  replay adapter, release-only obligation, or layered-proof obligation;
- owner: child, parent, read-only, or shared-kernel plus the owning suite when
  child-owned;
- overlap note: duplicate state or side-effect ownership and the explicit
  sharing rationale, if any.

Assign every item one owner: `child`, `parent`, `read_only`, or
`shared_kernel`. A child-owned item must name the owning suite. Duplicate state
or side-effect owners are blockers unless the overlap is explicitly allowed.

## Evidence Checklist

For each child suite or child test script, record grouped evidence:

- identity: suite id, command, layer, and owned leaf matrix cell ids when the
  layer is `leaf_matrix_cell`, `leaf_boundary_matrix`, or `artifact_payload`;
- result summary: status, evidence tier, freshness or stale reason, selected
  and skipped counts, duration, timeout, exit code, and result path;
- visibility caveats: skipped visibility, not-run reason, background log root,
  final exit/result artifact flags, proof artifact, and test-result reuse
  ticket when an old result is reused;
- ownership summary: owned state, side effects, partition items, and release
  scope.
- payload ownership summary when applicable: payload contract ids, required
  case ids, result artifact path, and downstream Model-Test Alignment owner.

Progress output is liveness evidence only. It is not completion evidence.
An old `passed` result is not reusable parent evidence unless
`TestResultReuseTicket` and `ProofArtifactRef` are both current for the command,
test source, tested artifact, dependency, environment, result fingerprint, and
coverage scope.
When a final confidence claim depends on the parent gate, export child evidence
ids, status, freshness, and release-scope gaps to the Risk Evidence Ledger.
Background runs need final exit/result artifacts before a parent gate can treat
them as complete.

When `required_leaf_cell_ids` are declared on the parent gate, every required
cell must be owned by a registered child suite/script with current passing
evidence. A leaf matrix-cell suite that does not name its cells is a blocker,
because the parent cannot tell which finite boundary cell was proved.
Transition coverage cells use the same required id surface when they are routed
through TestMesh.

## Routine And Release Scope

Use `TEST_SCOPE_ROUTINE` for fast local confidence. Release-only suites may be
deferred only when the report keeps the release obligation visible.

Use `TEST_SCOPE_RELEASE` for publish, tag, deployment, or broad completion
claims. Release-required suites must be current and passed.

## Prompt Template

```text
Build a FlowGuard TestMesh for this repository's validation flow. Treat the
current broad test command or suite as the parent test gate and the extracted
or selected suites/scripts as child validation regions. Do not inline every
child test case into the parent; expose each child through ownership and
evidence contracts.

Use these groups:

- Parent gate: identity and routine/release scope.
- Ownership map: boundary, owner, and overlap note.
- Child suite evidence: identity, result summary, visibility caveats, and
  ownership summary.
- Required cell ids: transition or leaf matrix cells that child suites must own
  with current evidence, plus the model obligation and code contract targets
  that downstream Model-Test Alignment must bind.
- Target split derivation: source model, target suites, coverage, and
  rationale.

Known hazards that must fail:
- missing target split derivation;
- target split derivation not sourced from a FlowGuard model;
- target split derivation omits target suites or partition coverage;
- missing child owner;
- unregistered owner suite;
- flat test split with no parent/child ownership map;
- parent gate expands every child test case instead of consuming child
  contracts;
- duplicate partition or state owner;
- hidden skipped tests;
- stale evidence;
- timeout or failed suite;
- background progress without final exit/result artifacts;
- release-required suite missing under release scope.
- transition coverage required cell id missing child evidence.
- DevelopmentProcessFlow `test_too_thick` handoff treated as an ordinary
  implementation failure without child validation structure.
```

## Completion Standard

A TestMesh review can support the parent only when:

- every partition item is owned;
- the target suite/script layout is derived from a FlowGuard model and covers
  the parent partition items used by the decision;
- every child owner is registered;
- sibling ownership conflicts are absent or explicitly shared;
- parent confidence is based on child contracts rather than expanded child
  internals;
- all required suites have current pass evidence for the requested scope;
- all required transition or leaf matrix cell ids have current passing child
  evidence;
- skipped, not-run, timeout, and stale evidence remain visible;
- background jobs have final completion artifacts;
- DevelopmentProcessFlow `test_too_thick` handoffs have explicit child
  evidence status and parent consumption;
- release-only obligations are either current or explicitly deferred only under
  routine scope.
