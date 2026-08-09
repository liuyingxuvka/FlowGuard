# TestMesh Protocol

TestMesh governs validation partitions, ownership, terminal evidence, and
freshness. It does not define behavior semantics, choose code/model structure,
or execute checks.

## Trigger

Use TestMesh when evidence is large, layered, slow, background, stale, reused,
skipped, release-only, or needs parent/child ownership. Keep small direct tests
in `flowguard` unless another owner requires a mesh.

## Conditional Local Material

Read only the files whose trigger is present; a triggered file is mandatory.

| Trigger | Required reference |
|---|---|
| any result reuse or selective rerun | `test_mesh_reuse_protocol.md` |
| long, background, bounded-system, timeout, or progress evidence | `test_mesh_long_check_protocol.md` |
| release/full/parent gate or source freeze | `test_mesh_release_protocol.md` |

## Ownership Boundary

- TestMesh owns the test inventory, parent/child evidence graph, terminal
  receipts, and freshness decisions.
- Model/Test Alignment supplies semantic coverage rows.
- DevelopmentProcessFlow owns execution sequence and final lifecycle claims.
- The native check owner runs the check and publishes its result.
- WorkContext and provider status are read-only planning context, never test
  receipts or execution owners.

## Required Intake

- Parent gate — claim scope, protected failures, model obligations, inventory
  revision, and completion boundary.
- Ownership map — every surface, obligation, member, cell, case, and shard to
  exactly one native owner.
- Child suite evidence — status, run identity, input/tool/environment
  fingerprints, exit/result artifact, covered ids, versions, and freshness.
- Target split derivation — why each child exists, what it covers, and why the
  partition is disjoint or intentionally overlapping.

Provider context is not test evidence. Filenames, PIDs, logs, and progress do
not prove terminal success.

## Core Mesh Rules

1. Derive the child split from a FlowGuard validation-structure model.
2. Declare an independent current inventory; every required item has exactly
   one executed, reused, or delegated disposition.
3. Require `planned = executed + not_run` and `failed <= executed`; a
   `declared_complete` run cannot contain not-run work.
4. Persist each successful child immediately. Parent or sibling failure cannot
   erase reusable current child evidence.
5. Reject stale, skipped, progress-only, malformed, tampered, ambiguous,
   unknown-impact, and unowned evidence.
6. A receipt may fan out only within its declared covered-id boundary; copies
   are not additional executions.

## Model-Purpose Gate

Before creating or materially changing a concrete mesh, freeze task-specific
protected failures and claim boundary. Bind the exact candidate to native good,
per-failure bad, oracle, and current evidence. Only declared FlowGuard checks
may support completion claims.

## Path-Quality Evidence Ownership

When Model-Test Alignment or ModelMaturation requires path-quality evidence,
inventory each affected hard-semantic check and retained-element necessity
witness under its real test/native owner. Bind exact subject, model, code,
oracle, evidence, covered obligation/element ids, terminal receipt, and
currentness. An existing current leaf may be reused only through the ordinary
exact reuse contract; a changed subject or any consumed code/test/oracle/
evidence identity stales the matching member and declared dependants.

TestMesh owns this hierarchy and receipt currentness only. It does not create
necessity witnesses, decide whether a model path is lightweight or deep,
enumerate candidates, compare cost vectors, compute Pareto dominance, or
promote `normative_target` to observed authority. Deep evidence members enter
the mesh only for exact currently triggered affected models; a current
`single_clear_path` result adds no deep suite or candidate payload.

These rows are provider-neutral. Non-code workflows use their native oracle
and verification members rather than fabricated Python or pytest owners.

## Closure Coverage

When ModelMesh closure is in scope, include
`model_mesh_closure_to_transition_coverage` for repeat-input, blocker-token,
repair-feedback/no-delta behavior, and same-packet termination. The mesh must
cover happy, failure, negative, and replay cases; missing rows remain open.

## Evidence States

- `execute`: no current exact result exists;
- `reuse_current`: one independently verified producer receipt matches owner,
  request, inputs, dependencies, toolchain, environment, and covered ids;
- `blocked`: malformed/tampered/ambiguous/unknown-impact/in-flight evidence;
- `not_run`: visible terminal nonexecution with a reason, never a pass.

## Failure And Handoff

Return semantic gaps to Model-Test Alignment, model partition gaps to
ModelMesh, code partition gaps to StructureMesh, lifecycle sequencing to
DevelopmentProcessFlow, and broad confidence to RiskLedger. Stable finding ids
must survive selective reruns.

## Output And Completion

Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`,
`claim_boundary`, `typed_next_actions`, a validation mesh diagram, exact test
denominator, child freshness, and terminal receipt identities.

Complete only when every required inventory item has one current executed,
reused, or typed delegated disposition and the parent gate recomposes from
those exact child ids/fingerprints. A locally green subset is never the full
inventory.

## Project Test Inventory Blueprint Boundary

For explicit whole-target software scope, TestMesh owns the exact project test
inventory and evidence hierarchy consumed by `model_code_test`. Inventory rows
name admitted test source, discovered test node, parameter/case identity,
assertion or oracle target, covered obligation/surface ids, native execution
owner, terminal disposition, and current receipt fingerprint. Aggregate parent
receipts remain parents; they never replace required leaf identities.
The project blueprint embeds this complete `ProjectTestInventory`; every load
independently re-audits current test files, nodes, parameter/case structure,
manifest identity, and fingerprints before reuse.

Formal static closure uses placeholder-free `BehaviorCaseContract` rows and
real `BehaviorCoverageEdge` members. Delegated assertion helpers count only
through an explicit current acyclic graph terminating at assertion/native
members. Execution receipts remain separate `CoverageExecutionEvidence` and
`not_run` cannot be described as pass.

TestMesh does not establish `independent_semantics`, decide row-level
`model_code_test` qualification or qualify `static_blueprint`. Whole-target
collection is explicit-only.
Ordinary work materializes affected nodes plus required dependent parents.
Unknown impact or missing/duplicate/ambiguous ownership blocks; there is no
run-all, FlowGuard-self, or generic catchall fallback.

Return any supplied canonical `deepest_proven_layer` unchanged plus the first
unresolved native owner/member/evidence gap created by test inventory or
freshness. Keep user choice, maturation, and admission independent.

Project-blueprint projection also requires one terminal
`ProjectTestNodeDisposition` per discovered node: `required`, `supporting`,
`scoped_out`, `generated`, `external`, or `unresolved`. Parameter/case markers
and assertion targets stay attached to their exact node. Aggregate parent
receipts may prove a parent run, but never manufacture an omitted leaf or a
missing behavior-block binding.

## Compact evidence and final ownership

Compact reports are bounded display projections, not a reduced evidence
denominator. Keep every planned coverage id, execution owner, receipt
fingerprint, omitted count, and `not_run` reason in the canonical source. Freeze
one final parent only after source, toolchain, and impact identities are stable;
do not use background resume or repeated full runs as a freshness substitute.
