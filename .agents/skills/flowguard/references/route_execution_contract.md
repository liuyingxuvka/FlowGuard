# FlowGuard public-route execution contract

This document is the shared AI-facing operating contract for the fifteen
public FlowGuard routes. It does not add a route, a checker, a model
authority, or a second receipt store. The executable ownership source remains
`flowguard.self_maintenance.PUBLIC_ROUTE_ADMISSION` together with
`default_flowguard_route_profiles()`; this document makes the same boundary
and execution rules visible before a route-specific protocol is loaded.

## 1. Route selection and shared context

The first read is always `references/route_index.md`. Select exactly one
public owner from the structured positive and forbidden conditions in the
current `RouteProfile`. A zero-match or multi-match result is respectively
`no_match` or `conflict`; keyword similarity, declaration order, a caller's
assertion, or a broad “run every route” request cannot resolve it.

After selection, pass one immutable `RouteContext` envelope to the selected
owner. The envelope contains only the current task boundary and the fields
needed by the route:

- `task_facts` and `task_coverage_demand`, including request spans and
  preserved unknown/contradictory/scoped facts;
- project root, accepted observed-model snapshot, accepted revision/head, the
  exact current owner denominator and bindings, and affected ids;
- claim boundary, execution profile (`light|affected|full`), and modeling mode
  (`read_only_audit|model_first_change|model_maintenance|layered_boundary_proof`);
- active OpenSpec change ids and task-scope status when the work is a governed
  change, plus toolchain/environment identity and the private evidence root;
- current source/contract/check fingerprints and the existing receipt refs
  required by this owner.

The context is shared metadata, not shared semantic ownership. A route may
consume a sibling's exact receipt or typed handoff, but it must not copy the
sibling's semantics, invent a child receipt, or turn a related-plane row into
an instruction. Ordinary work reads only the affected model/evidence
neighborhood. Whole-target materialization requires an explicit whole-system,
release, integration, export, or self-qualification fact.

`light` is the default for read-only interpretation and currentness checks;
`affected` is the default for an ordinary change; `full` is reserved for an
explicit whole-system, integration, or release claim after source, model,
OpenSpec scope, owner DAG, formal/shadow/installed projections, and reverse
semantic inputs are frozen. Selecting a specialist route never upgrades its
execution profile.

## 2. Lazy reference loading

Reference loading is staged and bounded:

1. Before selection, load only `route_index.md`.
2. After one route is selected, load that route's `SKILL.md` and the first
   reference named by its `Local Material Routing`/profile row.
3. Load a conditional reference only when the named trigger in the row is
   present (for example, a transition cell, reuse request, long check, release
   gate, partition, reattachment, or payload boundary).
4. Load a downstream route only after the current owner emits its typed
   handoff. Do not preload all fifteen skills, all protocol files, all model
   shards, or all receipt trees.

Lazy loading is an input-cost rule, not an evidence shortcut. A skipped
conditional reference remains visible as `not_triggered`; a required but
unavailable reference is `blocked`.

## 3. Producer, reuse, and terminal rules

Every selected owner classifies its declared work before starting a process:

`execute | reuse_current | blocked | not_run`.

- A plan-only/read-only route does not reserve a lease, create a run
  directory, write a receipt, activate a pointer, install a projection, or
  launch a model/test/heavy producer.
- Before `execute`, freeze route, unit/member, task and coverage identities,
  source/model/contract/check/toolchain/environment identities, claim boundary,
  owner inputs, dependencies, and evidence root. An unmapped or ambiguous
  component stops before any producer and is not converted to run-all.
- `reuse_current` is legal only for an exact current terminal receipt in the
  same declared unit and route boundary with identical subject, owner,
  request, inputs, dependencies, producer, toolchain, environment, policy,
  covered obligations, and required child receipts. Reuse performs verification
  and composition only: producer count remains zero and no new run directory,
  lease, or receipt is created.
- A parent/aggregate receipt cannot be relabeled as an independently executed
  leaf receipt. Each route preserves its native evidence owner.
- A routine local functional cycle permits one bounded producer observation and
  then closes; an exact-current parent is read-only and is never reopened just
  to refresh a pointer. A separate formal qualification or release projection
  is admitted only when explicitly requested, with its own frozen inputs and
  one owner. Output paths, timestamps, log locations, display projections, and
  timeout policy changes do not reopen functional evidence.
- After timeout, cancellation, or interruption, the whole descendant process
  tree must be confirmed absent before evidence can be accepted or another
  owner can start. Progress, PID, log text, old receipt, or a checkbox is not a
  terminal.

Working evidence is allowed to remain under the governed private work root
while an invocation is in progress or under review. Such temporary material is
explicitly non-authoritative and release-excluded; publication/authority
projections must omit it, and cleanup is a separate explicit, gated action.
Route admission must not force immediate deletion or move evidence outside the
controlled work root merely to satisfy package boundaries.

The following are universal stop conditions. Return the typed reason and stop
at the current owner; do not retry by changing output paths, creating a new
epoch, loading a fallback route, or starting full:

- source/model/contract/toolchain/environment drift after freeze;
- missing, stale, foreign, malformed, duplicate, ambiguous, in-flight, or
  cleanup-unconfirmed evidence;
- missing owner, unknown component, unresolved reverse binding, or scope that
  exceeds the admitted route/claim boundary;
- skipped/not-run/blocked required members under a declared-complete claim;
- no current parent for a `--reuse-only` request;
- a symlink-capability failure (`WinError 1314` or equivalent) for the gate
  that requires a real reparse-point probe;
- active OpenSpec scope drift or an unavailable required external owner.

## 4. OpenSpec local acceptance alignment

These rules mirror the current local acceptance contracts; the task files remain
the source of truth and must be read directly before a governed completion:

| Local task | Contract mirrored here |
| --- | --- |
| `openspec/changes/allow-explicit-completion-objective/tasks.md:3.3` | On a symlink-capable runner only, reserve at most one full producer and then exactly one same-parent `--reuse-only`; external CI/provider/UI/install/release work stays typed `blocked`/`not_run`. If the capability probe returns `WinError 1314`, stop before both runs. |
| `openspec/changes/close-runtime-evidence-and-task-map/tasks.md:9.2` | Freeze all inputs, perform one authorized formal qualification and one same-parent reuse-only check, and do not rerun after success. |
| `openspec/changes/close-runtime-evidence-and-task-map/tasks.md:9.3` | Keep external CI/provider/release/remote operations explicitly `not_run`; perform KB postflight; close only when every local core acceptance condition has current evidence. |

The three task rows are not made complete by this document. A current receipt
and the task's own completion evidence are still required.

## 5. Fifteen public route rows

The first two columns mirror the executable route profile's trigger and
minimal-input boundary. The reference column is lazy: it is not loaded until
the row's `load trigger` is true. The producer column names the route-native
owner; the universal producer/reuse/stop rules above always apply.

| Public route | Trigger boundary | Shared context required | Lazy reference and load trigger | Native producer / reuse / route-specific stop |
| --- | --- | --- | --- | --- |
| `model_first_function_flow` | Ordinary behavior/state modeling, unclear owner, or cross-route coordination; exclude trivial work and a clear satellite owner. | Task intent, observable behavior boundary, existing model evidence, current owner bindings. | `references/modeling_protocol.md` after kernel selection; deeper core/evidence protocols only for the selected model/check. | Model-first check/maturation owner; reuse exact current model/evidence identity. Stop on unresolved owner, missing finite boundary, or missing protected failure/oracle. |
| `existing_model_preflight` | Existing modeled system needs current ownership lookup; exclude greenfield without model context. | Project root, candidate change boundary, accepted snapshot/revision, affected owner denominator. | `references/existing_model_preflight_protocol.md` after route selection. | Read-only authority/owner lookup; reuse exact snapshot/path-quality/owner closure. Stop on stale authority, ambiguous duplicate boundary, or missing binding; hand implementation to the selected downstream owner. |
| `behavior_commitment_ledger` | Broad external promises or commitment coverage must be inventoried; exclude helper-only inventories. | Change mode, bounded source surfaces, commitments, owner models, path sensitivity. | `references/behavior_commitment_ledger_protocol.md` after route selection. | Canonical live source-identity and ledger producer; reuse exact source inventory/PPA/ledger fingerprints. Stop on unsafe/unanchored globs, duplicate members, stale source, owner overlap, or PPA gap. |
| `architecture_reduction` | An existing modeled implementation may contract or retire without behavior change; exclude greenfield structure and unproved change. | Observable contract, candidate reductions, current callers/consumers/tests, model/admission identity. | `references/architecture_reduction_protocol.md` only for an explicit contraction, retirement, or full audit. | Finite proof-batch producer; reuse one exact current aggregate proof. Stop on missing necessity/equivalence/caller/facade/replacement evidence or an unresolved candidate; never refactor directly. |
| `code_structure_recommendation` | A model must drive pre-code module/function/facade/adapter/field/effect ownership; exclude existing large refactors. | FunctionBlocks, state/field/effect owners, model and admission fingerprints, public entrypoints. | `references/code_structure_recommendation_protocol.md` after admission. | Recommendation projection only; reuse exact model/admission identity. Stop on omitted/duplicate element, reverse-obligation gap, or identity drift; send existing-code work to StructureMesh. |
| `contract_exhaustion_mesh` | A declared finite boundary needs canonical bad cases, combinations, oracles, shards, or receipts; exclude open-ended discovery. | Contract dimensions, coverage universe, seeds, oracles, model axes, interaction groups, declaring owner. | `references/contract_exhaustion_mesh_protocol.md` after positive admission. | Finite case/oracle/shard producer; reuse exact universe, seed, checker, and receipt identities. Stop on unbounded boundary, missing actionable oracle/feedback, stale universe, or missing consumer handoff; never claim all bugs are covered. |
| `development_process_flow` | Staged work, risk-admitted agent-workflow ordering, freshness, sync, install, release, or final process claim; exclude one specialist semantic check. Multiple skills/tools or an external-effect label alone do not admit the internal `agent_workflow` mode; simple read-only, single-owner, single-tool, targeted-test work is `not_triggered`. | Process actions, artifacts, peers, evidence, owner DAG, OpenSpec scope, toolchain/environment, and the explicit admission facts. | `references/development_process_flow_protocol.md` after route selection; `references/agent_workflow_protocol.md` only for explicit/cross-owner/shared-write/post-validation-invalidating/route-change/multi-owner-irreversible facts; `references/distribution_release_protocol.md` only for distribution/release identity. | Shared planner/readiness/process producer; reuse exact frozen plan/readiness/terminal parent. Stop on drift, unknown owner, missing sibling evidence, unauthorized external side effect, or final claim before freeze. |
| `field_lifecycle_mesh` | Fields/schema keys/config/prompt/payload/persisted attributes are added, removed, renamed, migrated, replaced, externalized, preserved, or audited; exclude no field change. | Field boundary, field rows/groups, readers/writers, projections, old-field disposition. | `references/field_lifecycle_mesh_protocol.md` after admission. | Field inventory/projection producer; reuse exact live field inventory and lifecycle fingerprints. Stop on missing field, reader/writer, projection, or old-field disposition; hand behavior cases to ContractExhaustion/MTA/TestMesh. |
| `model_mesh_maintenance` | Affected topology crosses model boundaries, parent/child governance changes, child evidence is stale, or a whole-flow mesh claim is requested; count alone is not a trigger. | Parent/children, partition items, affected relations, coverage receipts, required child receipts. | `references/model_mesh_protocol.md` after admission; partition/reattachment/closure refs only for their named triggers. | Parent/child topology and reattachment producer; reuse exact current parent/child receipts and topology fingerprint. Stop on overlap, stale child, missing direct-child receipt, or parent that relabels a child result. |
| `model_miss_review` | Current runtime/test/replay/UI evidence exposes a missed behavior class or needs generalized repair; exclude no observed failure. | Concrete miss, root cause evidence, commitment/owner, same-class bad case and combination ids. | `references/model_miss_protocol.md` after admission. | Target-aware replay/same-class case producer; reuse only exact current miss/class evidence, never a point-green result. Stop on absent concrete failure, unsupported cause, unknown old-path disposition, or missing owner-code/test binding. |
| `model_test_alignment` | Model obligations, owner code contracts, and tests need direct comparison; exclude test hierarchy alone. | Model obligations, current-intent bindings, code contracts, exact test/native members, oracles, case ids. | `references/model_test_alignment_protocol.md` after admission; transition/field/payload refs only for their named boundaries. | Binding/alignment producer; reuse exact model/code/test/oracle fingerprints and leaf receipts. Stop on opaque/stale/skipped/cross-owner evidence, missing oracle, orphan helper, duplicate binding, or parent-only receipt. |
| `model_topology_hazard_review` | A locally green topology needs anchored future-use hazard review before broad confidence; exclude an observed runtime failure. | Usage intent, topology digest, business path, hazard candidates, BCL/preflight owner anchors. | `references/topology_hazard_protocol.md` after route selection. | Bounded topology hazard review; reuse exact topology/usage-intent digest. Stop anchored hazards lacking current owner/evidence; unanchored concerns remain observation-only and do not trigger a producer. |
| `structure_mesh_maintenance` | Existing large module/package/API/facade/config/plugin surface needs a behavior-preserving split; exclude pre-code planning. | Parent module, partition items, public entrypoints, facade/consumer/dependency/config inventory. | `references/structure_mesh_protocol.md` after admission. | Structure/parity evidence producer; reuse exact inventory/facade/equivalence fingerprints. Stop on omitted surface, missing facade/owner/cycle/config/parity evidence, or stale ArchitectureReduction handoff. |
| `test_mesh_maintenance` | Validation is large, slow, stale, skipped, background, release-only, or requires parent/child evidence; exclude semantic alignment alone. | Parent claims, child suites/scripts, required cases/shards, freshness evidence, evidence owners. | `references/test_mesh_protocol.md` after admission; reuse/long-check/release refs only for their named triggers. | Child test/evidence producer; reuse only an exact current `TestResultReuseTicket`/`ProofArtifactRef` in the same boundary. Stop on stale/foreign/malformed/in-flight evidence, hidden skips, incomplete accounting, or missing child owner. |
| `ui_flow_structure` | UI states, journeys, controls, hierarchy, operability, product language, or runnable surface evidence is in scope; exclude non-UI work. | UI states, controls, journeys, surface inventory, stable ids/fingerprints, task/state/recovery evidence. | `references/ui_flow_structure_protocol.md` after route selection. | Surface/journey/evidence producer; reuse exact surface inventory and runnable evidence fingerprints. Stop on unclassified/internal render, unmapped/conflicting disposition, missing item fingerprint, stale source/recovery evidence, or blindspot. |

## 6. Handoff and completion vocabulary

The selected route owns its domain decision. A typed handoff names the next
public owner and the exact affected ids; it does not run that owner eagerly.
`not_triggered` means the named conditional reference or downstream route was
not required by current facts. `not_run` means it was required by a broader
claim but intentionally not executed, such as external CI/provider/release
work in local completion task 9.3. `blocked` means a required gate prevented
execution. None of these states may be silently converted to pass by a parent
aggregate or by re-reading an old receipt.

The final report must keep route evidence, execution profile, model currentness,
receipt reuse, external scope, and release/install identity separate. A route
contract or a static route-doc test proves only documentation alignment; it
does not create a model/test pass or close an OpenSpec task.
