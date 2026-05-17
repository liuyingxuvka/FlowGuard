# Test Evidence Mesh

Test Evidence Mesh is for projects where validation is becoming too expensive
or too broad to treat as one flat test command.

Use the plain mental model:

```text
Parent test gate = total validation contract
Child suite      = owned validation region
TestMesh review  = checks whether child evidence can support the parent gate
```

TestMesh does not run pytest, unittest, Playwright, shell scripts, or release
jobs. Project adapters run those commands and pass structured evidence into
FlowGuard. FlowGuard then checks coverage, ownership, freshness, skipped tests,
background completion, and routine-vs-release confidence.

## When To Trigger It

Run a TestMesh review when test execution or validation confidence needs a
layered plan:

- a routine test run is taking long enough that agents keep skipping or timing
  it out;
- one large regression command mixes unrelated behavior, state, side effects,
  or release gates;
- a parent validation claim depends on several child commands or background
  jobs;
- skipped, stale, timeout, or progress-only evidence could be hidden inside a
  green summary;
- a release-only suite should stay visible without blocking routine local
  confidence.

This is different from hierarchical model mesh. Hierarchical model mesh governs
FlowGuard model boundaries. TestMesh governs test and validation evidence.

## Partition Ownership

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

Each child suite reports a `TestSuiteEvidence` summary:

- command and layer;
- result status such as `passed`, `failed`, `timeout`, `running`, or `not_run`;
- evidence tier and freshness;
- selected, total, and skipped test counts;
- whether skipped tests are visible;
- duration, timeout, exit code, and result path;
- background log root and final artifact flags;
- owned state and side effects;
- not-run and stale reasons.

Progress output is not completion evidence. A background suite is complete only
when final exit/result artifacts exist and the run is not progress-only.

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
)

report = review_test_mesh(plan)
assert report.ok
```

Create a starter scaffold:

```powershell
python -m flowguard test-mesh-template --output .
python .flowguard/test_mesh/run_checks.py
```
