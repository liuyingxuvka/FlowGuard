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
- release-only suites should stay visible without blocking routine local
  confidence.

## Partition Checklist

For the parent test gate, list each partition item:

- behavior or workflow boundary;
- state field or state-write owner;
- module or command boundary;
- side effect;
- invariant or replay adapter;
- release-only obligation.

Assign every item one owner: `child`, `parent`, `read_only`, or
`shared_kernel`. A child-owned item must name the owning suite. Duplicate state
or side-effect owners are blockers unless the overlap is explicitly allowed.

## Evidence Checklist

For each child suite or child test script, record:

- command and layer;
- result status;
- evidence tier;
- freshness and stale reasons;
- total, selected, and skipped counts;
- whether skipped tests are visible;
- duration, timeout, exit code, and result path;
- background log root plus final exit/result artifact flags;
- owned state and side effects;
- not-run reason.

Progress output is liveness evidence only. It is not completion evidence.
Background runs need final exit/result artifacts before a parent gate can treat
them as complete.

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

Parent gate:
- name:
- routine decision scope:
- release decision scope:

Partition items:
- behavior/state/module/side-effect:
- owner suite:
- ownership type:
- touched paths:

Child suite evidence:
- suite id:
- command:
- layer:
- result status:
- evidence tier:
- freshness:
- selected/total/skipped counts:
- skipped visible:
- background artifacts:
- owned state:
- owned side effects:
- not-run or stale reasons:

Known hazards that must fail:
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
```

## Completion Standard

A TestMesh review can support the parent only when:

- every partition item is owned;
- every child owner is registered;
- sibling ownership conflicts are absent or explicitly shared;
- parent confidence is based on child contracts rather than expanded child
  internals;
- all required suites have current pass evidence for the requested scope;
- skipped, not-run, timeout, and stale evidence remain visible;
- background jobs have final completion artifacts;
- release-only obligations are either current or explicitly deferred only under
  routine scope.
