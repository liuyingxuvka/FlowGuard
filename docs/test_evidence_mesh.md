# Test Evidence Mesh

Test Evidence Mesh is for projects where validation is becoming too large,
expensive, or broad to treat as one flat test command, script, or suite.

It is the test-side sibling of ModelMesh and StructureMesh. ModelMesh
partitions large models into child models, StructureMesh partitions large code
structures into child modules/scripts, and TestMesh partitions large test
structures into child suites/scripts.

Use the plain mental model:

```text
Parent test gate = total validation contract
Child suite/script = owned validation region
TestMesh review  = checks whether child evidence can support the parent gate
```

TestMesh does not run pytest, unittest, Playwright, shell scripts, or release
jobs. Project adapters run those commands and pass structured evidence into
FlowGuard. FlowGuard then checks coverage, ownership, freshness, skipped tests,
background completion, and routine-vs-release confidence.

The parent test gate should not inline every child test case, fixture, or
internal state route. It should consume each child suite/script as a contract:
owned partition, freshness rule, result status, skipped visibility, and output
evidence. A child can become its own parent gate when its internal test layout
needs another split.

Before the parent gate trusts a child-suite layout, it should record the target
split derivation from a FlowGuard validation-structure model. The derivation
names the source model, target child suites/scripts, covered partition items,
state owner fields, side-effect owner fields, and rationale for the validation
split. A partition map without this derivation is not enough for green parent
confidence.

## When To Trigger It

Run a TestMesh review when test execution or validation confidence needs a
layered plan:

- a routine test run is taking long enough that agents keep skipping or timing
  it out;
- one large regression command, test script, or suite mixes unrelated behavior,
  state, side effects, or release gates;
- a broad suite should be split into child suites/scripts with explicit owned
  validation regions;
- a parent validation claim depends on several child commands or background
  jobs;
- skipped, stale, timeout, or progress-only evidence could be hidden inside a
  green summary;
- a release-only suite should stay visible without blocking routine local
  confidence.
- a model-miss repair needs broad same-class coverage, such as parameterized
  variants, property tests, seeded fuzz, background shards, or release-only
  regressions that are too large for a direct Model-Test Alignment row set.
- a transition coverage matrix is too large, slow, UI/browser-heavy, or
  release-only to prove with one flat direct evidence row set.
- an import/export, generated artifact, save/load, or AI work-package payload
  matrix is too large, slow, manual-heavy, or release-only to prove with one
  flat direct evidence row set.

Automatic split diagnostics provide the trigger before a broad test result is
accepted as enough. When direct validation evidence reports slow duration,
large test counts, broad obligation coverage, background progress-only logs, or
release-only scope, `review_auto_mesh_splits()` routes the candidate to
TestMesh and keeps parent validation confidence blocked or scoped until current
child-suite evidence is consumed.

This is different from hierarchical model mesh only in what is being split.
Hierarchical model mesh governs FlowGuard model boundaries. TestMesh governs
test and validation boundaries.

## Partition Ownership

## Target Split Derivation

Each parent test gate should include a `TestTargetSplitDerivation`:

- `source_model_id`: the FlowGuard validation-structure model used to derive
  the split;
- `target_suite_ids`: child suites or scripts in the target layout;
- `covered_partition_item_ids`: parent validation partitions covered by the
  split;
- `state_owner_fields` and `side_effect_owner_fields`: ownership boundaries
  that shaped the split;
- `rationale`: why this suite/script layout follows from the model.

Missing source, unknown target suites, incomplete partition coverage, or
prose-only derivations block parent gate confidence.

Each parent test gate should declare partition items. A partition item can name
a behavior, state field, module, command, side effect, invariant, or release
boundary. Ownership is explicit:

- `child`: one child suite owns the item;
- `parent`: the parent gate owns the item directly;
- `read_only`: a suite observes the item but does not own it;
- `shared_kernel`: a deliberately shared validation kernel owns the item.

Missing owners are coverage gaps. Duplicate owners for the same partition,
state write, or side effect are ownership conflicts unless the overlap is
declared read-only or shared-kernel.

## Evidence Contracts

Each child suite or child test script reports a `TestSuiteEvidence` summary:

- command and layer;
- result status such as `passed`, `failed`, `timeout`, `running`, or `not_run`;
- evidence tier and freshness;
- selected, total, and skipped test counts;
- whether skipped tests are visible;
- duration, timeout, exit code, and result path;
- background log root and final artifact flags;
- optional `proof_artifact` for strict proof of the concrete suite result;
- optional `result_reused=True` plus `reuse_ticket=TestResultReuseTicket(...)`
  when an old suite result is reused because command, test source, tested
  artifact, dependency, environment, result fingerprint, and coverage scope are
  still current;
- owned state and side effects;
- owned artifact payload contract ids and case ids when the child suite proves
  synthetic file or work-package cases for downstream Model-Test Alignment;
- not-run and stale reasons.

Progress output is not completion evidence. A background suite is complete only
when final exit/result artifacts exist and the run is not progress-only.
If a child suite reuses a previous result, TestMesh requires a current reuse
ticket and a current proof artifact before the child can support parent
confidence. A `passed` status string alone is not enough for reused evidence.

When a final FlowGuard confidence claim depends on these suites, feed each
child suite's evidence id, status, freshness, and scope into the Risk Evidence
Ledger. TestMesh owns the validation hierarchy; the ledger owns the final
"does this evidence support this user risk?" claim boundary.

For model-miss repair, the parent gate should keep the observed regression and
same-class generalized coverage distinct. A child suite can own the observed
case, while another owns the same-class family through parameterized tests,
property checks, seeded fuzz, or release-only runs. Routine confidence remains
scoped until release-only same-class evidence is current.

For layered boundary proof, TestMesh can own the suite/script hierarchy that
produces leaf boundary evidence, but it does not by itself prove the leaf
matrix. The layered proof still needs every finite
`Input x State -> Set(Output x State)` cell, the evidence id for that cell, and
a current pass status.

When a parent gate declares `required_leaf_cell_ids`, each id must be owned by
a child `TestSuiteEvidence` row through `owned_leaf_cell_ids`. Missing, stale,
skipped, progress-only, background-incomplete, non-passing, or invalidly reused
owners do not support the parent gate.

Transition coverage matrices can feed this same surface. Use
`transition_coverage_to_required_leaf_cell_ids(...)` to produce required cell
ids, register those ids as partition items, and let child suites own the ids
they actually prove. TestMesh checks evidence freshness and ownership for the
cells; Model-Test Alignment still owns whether those cells bind the declared
transition obligations, owner code contracts, and current external-contract
test evidence.

Artifact payload matrices can also feed this surface. Child suites can own
required payload case ids and result artifacts, but TestMesh only checks
partition ownership and evidence freshness. Model-Test Alignment still owns
whether each observed payload status, output, error path, state write, side
effect, and round-trip result matches the `ArtifactPayloadContract`.

## Routine Versus Release

`TEST_SCOPE_ROUTINE` lets teams keep a fast local gate green while reporting
release-only obligations as deferred warnings. This is useful when a slow full
regression is not required for every local slice.

`TEST_SCOPE_RELEASE` is stricter. Release-required suites must be current and
passed before the parent can report release confidence.

## Minimal API Example

```python
from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    TEST_SCOPE_ROUTINE,
    TEST_STATUS_PASSED,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    review_test_mesh,
)

plan = TestMeshPlan(
    parent_suite_id="project-validation",
    decision_scope=TEST_SCOPE_ROUTINE,
    required_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
    partition_items=(
        TestPartitionItem("unit-fast", owner_suite_id="unit"),
        TestPartitionItem("runtime-contract", owner_suite_id="runtime"),
    ),
    child_suites=(
        TestSuiteEvidence(
            "unit",
            command="python -m unittest tests.test_fast",
            result_status=TEST_STATUS_PASSED,
            evidence_tier=EVIDENCE_ABSTRACT_GREEN,
            test_count=32,
            selected_count=32,
            exit_code=0,
        ),
        TestSuiteEvidence(
            "runtime",
            command="python -m unittest tests.test_runtime",
            result_status=TEST_STATUS_PASSED,
            evidence_tier=EVIDENCE_ABSTRACT_GREEN,
            test_count=12,
            selected_count=12,
            exit_code=0,
            owns_state=("runtime_state",),
        ),
    ),
    target_split_derivation=TestTargetSplitDerivation(
        "project-validation-model",
        target_suite_ids=("unit", "runtime"),
        covered_partition_item_ids=("unit-fast", "runtime-contract"),
        state_owner_fields=("runtime_state",),
        rationale="derived from validation model partitions and runtime state ownership",
    ),
)

report = review_test_mesh(plan)
assert report.ok
```

Create a starter scaffold:

```powershell
python -m flowguard test-mesh-template --output .
python .flowguard/test_mesh/run_checks.py
```
