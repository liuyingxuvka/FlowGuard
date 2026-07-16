## Context

The shadow workspace and formal Git repository both contain the completed first implementation of development-process strategy selection after the archived prerequisite sync. Its public owner and behavior boundary are correct: DevelopmentProcessFlow remains the front door, TestMesh owns execution evidence, the Finding Ledger owns raw findings, SpecWorkPackage owns provider dependencies and receipts, and Model-Test Alignment owns model-code-test closure. The over-complexity is inside the internal strategy child and its projections: thirteen strategy data types, caller-authored numeric cost vectors, six mutually exclusive policy names, four rollout stages, thirty-nine public symbols, and strategy-specific fields copied across DPF, Simulator, TestMesh, PlanDetailing, and MTA.

The archived `reconcile-spec-provider-work-packages-with-flowguard-evidence` change supplied the current OpenSpec 1.6 frozen-snapshot, exact-receipt, dependency, and reuse infrastructure. Its historical receipts cannot prove this change because optimizer, model, skill, and test inputs will change. This change therefore uses the canonical infrastructure directly, without nested FlowGuard session wrappers and without copying provider authority.

The observable architecture contract is:

- source model: `.flowguard/development_process_strategy/model.py` under public owner `.flowguard/development_process_flow/model.py`;
- public entrypoint: route `development_process_flow` and `review_development_process_flow(...)`;
- observable outputs: conditional optimizer status, selected candidate when active, visible blockers/not-run work, repair grouping, affected revalidation, and bounded claim text;
- observable state: one current optimization decision plus raw finding/TestMesh/MTA/SpecWorkPackage identities owned by their existing routes;
- observable side effects: no direct code/test/provider execution by the optimizer; only DPF plan/report state is written;
- validation boundary: executable model, mutually independent focused diagnostics, trace replay, prompt/contract parity, zero-residual audit, and one frozen OpenSpec campaign whose only complete-model and complete-pytest owners are explicit.

## Goals / Non-Goals

**Goals:**

- Preserve the original general optimization behavior without prescribing collect-all or fail-fast universally.
- Make optimization a conditional DPF submode with a zero-ceremony ordinary path.
- Represent the decision through diagnostic boundary, execution mode, compact evidence, repair groups, and DPF freshness rather than six policy objects and a parallel public report.
- Return raw facts, dependencies, ownership, and alignment to their current owners.
- Replace synthetic score optimization with evidence-based qualitative or measured comparison and replayable process traces.
- Directly remove retired runtime/API/prompt fields with no alias, dual reader, wrapper, or alternate success path.
- Keep source, shadow, formal Git, installed package, installed skills, and OpenSpec/SkillGuard evidence as separate freshness domains.

**Non-Goals:**

- Do not add a public optimizer skill, route, model owner, commitment, or product behavior.
- Do not build a general scheduling solver, numeric performance predictor, or global optimizer.
- Do not execute tests, modify provider tasks, or decide model/test semantics inside the optimizer.
- Do not change SpecWorkPackage receipt authority or duplicate the archived prerequisite's canonical OpenSpec 1.6 infrastructure.
- Do not publish, push, tag, or create a remote release without separate user authority.

## Decisions

### 1. Preserve stable ownership identities and contract the internal child

Keep skill id `flowguard-development-process-flow`, route id `development_process_flow`, internal mode id `strategy_selection`, intent/commitment ids, and existing model path. The mode's human meaning becomes conditional process optimization. This is a `change_behavior` update to one existing development-process commitment, not a new commitment.

Alternative rejected: rename every id to `process_optimization`. That improves wording but creates identity migration and stale-evidence churn without changing behavior.

### 2. Use one activation gate before any optimization records exist

`process_optimization_reasons` is empty for ordinary single-route work and contains only stable reason ids for explicit request, multiple outcome-equivalent routes, material repeated-work risk, or diagnostic-boundary choice. The DPF plan also carries only `required_process_optimization_evidence_ids`; the decision remains an independent evidence artifact produced by the optimizer and consumed through DPF's existing typed evidence/freshness mechanism. Empty reasons require no optimization-evidence references and an inactive report status. Decision evidence without reasons, or reasons without current required decision evidence, blocks an enforced claim.

Alternative rejected: run the optimizer for every non-trivial workflow. This reproduces the cognitive and schema overhead being removed.

### 3. Replace six policies with two orthogonal dimensions

An eligible candidate chooses:

- `diagnostic_boundary`: `targeted`, `declared_complete`, or `budgeted`;
- `execution_mode`: `sequential` or `safe_parallel`.

Hard invalidation/safety/dependency failures are universal stop conditions, not a `fail_fast` strategy. Material evidence changes universally stale the current decision through DPF freshness, not an `adaptive` strategy or separate reevaluation record.

Alternative rejected: retain the six labels as aliases. Current-only replacement prohibits a second successful vocabulary, and the labels mix diagnostic scope, topology, and replanning.

### 4. Keep five compact records and one review function

`ProcessOptimizationContract` keeps the six inspectable equivalence dimensions and revision. `ProcessOptimizationCandidate` carries the candidate's corresponding ids, DPF step/validation references, boundary/mode, stop conditions, comparison evidence, and isolation evidence. `ProcessRepairGroup` preserves finding ids, relation evidence, a root-cause claim, disproof checks, repair action ids, affected obligation ids, ordinary owner-evidence ids, and required/current revalidation-evidence ids. `ProcessOptimizationDecision` carries activation, contract, candidates, selected id, input revision, material evidence, and repair groups. `ProcessOptimizationReport` carries the verdict, eligible/rejected identities, selected comparison basis, required revalidation, findings, and bounded claim text.

The existing DPF API group exposes only those five records plus `review_process_optimization`; there is no separate optimizer route or API group. DPF plans reference the resulting current evidence ids rather than embedding any optimizer record. The former `review_development_process_strategy`, helper projections, and standalone strategy API group are removed.

Alternative rejected: keep `ProcessOutcomeContract`, `ProcessCostVector`, campaign/cluster/hypothesis/batch/reevaluation/report/graph types. Their authoritative data already exists on DPF, TestMesh, Finding Ledger, MTA, or SpecWorkPackage surfaces.

### 5. Delegate facts and proof to existing owners

- TestMesh stores campaign id, diagnostic boundary, planned/executed/failed/not-run counts, visible not-run reason, and stable finding ids.
- Finding Ledger keeps immutable raw finding identity and evidence. A repair group never replaces or mutates a raw finding.
- SpecWorkPackage/PlanDetail retain dependencies and order. The strategy dependency graph projection is removed.
- Ordinary MTA obligations/code contracts/test evidence prove every repair group's `affected_obligation_ids`; each group cites those current `owner_evidence_ids`. The strategy-specific MTA binding is removed without replacement.
- DPF owns decision freshness, claim status, action order, and affected-revalidation selection.

### 6. Compare cost honestly and preserve bounded affected revalidation

Remove public numeric cost vectors and Pareto/frontier output. `comparison_basis` is either `qualitative` or `measured`, and every comparison cites current evidence. Qualitative evidence may include bounded estimates or structural rules, but it supports only “preferred under current declared evidence.”

Keep DPF's coverage-first affected-revalidation selection: first cover all affected requirements and side-effect boundaries, then use declared cost only to choose among equivalent covering sets. A measured finite set can support a bounded-minimum claim; estimated inputs cannot support a measured or global claim.

### 7. Use direct-current field replacement

Delete strategy-specific action, validation, rollout, campaign, cluster, reevaluation, PlanDetail, MTA, and public API fields in one repository-wide update. Do not accept old constructors or JSON keys in normal runtime. If a truly persisted project artifact is found, only `project-upgrade` may perform one deterministic old-to-current conversion at the upgrade boundary; zero old fields remain authoritative afterward.

### 8. Make prompts conditional and references demand-loaded

The DPF `SKILL.md` remains a concise route shell. It always preserves lifecycle evidence and outputs but describes optimizer details only behind the activation gate. The current monolithic protocol is reduced to a core lifecycle protocol plus two conditionally loaded references: process optimization and failure triage. The OpenAI prompt, project-adoption source, AGENTS projection, templates, docs, and SkillGuard contract use the same trigger and claim wording.

### 9. Replace synthetic scores with replayable trajectories

Trace tests first assert equal terminal result, required obligation coverage, safety, authority, and protected side effects. They then compare deterministic event counts: check executions, repair rounds, revalidation rounds, coordination handoffs, and visible not-run accounting. Wall-clock time is recorded only in real receipts and is not a stable unit-test oracle.

Required traces include repeated fail-fix versus boundary-first batch repair, hard blocker, safe parallel combinations, budgeted stop, material-change replan, ordinary no-op, and at least one non-test workflow.

### 10. Freeze one validation plan and one final execution owner

During implementation, run only affected model/tests/checks, allowing safe independent checks to execute asynchronously when their inputs are frozen and their owners do not overlap. The final full registered-model plus pytest campaign starts only after source, model, toolchain, formal/shadow/install projections, and impact plan are frozen. One parent owner records exact child check owners and immutable receipts. OpenSpec, SkillGuard, TestMesh, and release consumers verify/project those receipts and never rerun equivalent full commands.

`--resume` remains an execution command. A timeout/cancellation invalidates the evidence until descendant process count is zero. No Windows Scheduled Task, unattended retry, or mutable-worktree final run is allowed.

### 11. Enforce a complexity budget as a release gate

- no new public skill, route, commitment, or model owner;
- at most five optimizer dataclasses in total and no more than six public optimizer symbols, all discoverable only through the existing DPF API group;
- no duplicated TestMesh, Finding Ledger, SpecWorkPackage, PlanDetail, MTA, or DPF owner fields merely to satisfy a size target;
- strategy implementation target at most five hundred non-blank source lines while retaining every hard-equivalence and closure gate;
- DPF core protocol target at most two hundred lines and only two new conditional references;
- ordinary inactive output contains no candidates, frontier, clusters, or repair groups;
- old strategy symbols/fields have zero current-runtime residuals outside historical archives or explicit negative migration fixtures.

Exceeding a budget item blocks closure and returns to Architecture Reduction instead of being waived by green tests.

## Risks / Trade-offs

- **[Breaking constructor/API removal]** → Update every repository caller, API registry, template, model, and test in one direct-current change; run a zero-residual scan and version the release explicitly.
- **[Loss of useful behavior during contraction]** → Preserve the observable contract and executable known-bad traces before deleting old structures; require original correlated-failure and hard-blocker scenarios.
- **[Estimated costs masquerade as proof]** → Require `comparison_basis`, current evidence ids, and bounded wording; no public Pareto/global-minimum output.
- **[Repair grouping hides raw failures]** → Repair groups reference immutable Finding Ledger ids and relation evidence; raw findings remain separately visible.
- **[Parallel validation races with edits]** → Permit background affected checks only on frozen inputs with distinct owners; reserve final full validation for the frozen integration snapshot.
- **[Other active OpenSpec changes touch nearby canonical specs]** → Treat their reports as unrelated, keep this change's exact inputs and owners frozen, and do not reuse receipts whose selector or execution identity differs.
- **[Shadow/formal/installed drift]** → Audit and preserve the formal worktree's existing changes, promote only the exact governed inventory, sync back, install once, and prove parity before final closure.

## Affected Component Inventory

The cutover is governed as exact components rather than a repository-wide cleanup:

- `component:optimizer-runtime`: `flowguard/development_process_strategy.py` and its five records plus one review function. Owner: process-optimization child under DevelopmentProcessFlow.
- `component:process-projections`: `flowguard/development_process_flow.py`, `development_process_simulator.py`, `plan_detailing.py`, `testmesh.py`, `model_test_alignment.py`, `summary_report.py`, and `flowguard/__init__.py`. Owners remain DPF, Simulator, PlanDetail, TestMesh, MTA, Summary, and API registry respectively.
- `component:behavior-models`: `.flowguard/development_process_strategy/`, DevelopmentProcessFlow, Behavior Commitment Ledger, ContractExhaustionMesh, FieldLifecycleMesh, Model-Test Alignment, Architecture Reduction, and the model registry. Each specialist keeps its existing model owner; no optimizer-owned duplicate is added.
- `component:trajectory-and-unit-evidence`: optimizer traces and the affected DPF/Simulator/TestMesh/PlanDetail/MTA/Summary/API tests, including one zero-residual test. TestMesh owns execution facts; OpenSpec owns the frozen verification plan.
- `component:agent-guidance`: the DPF `SKILL.md`, OpenAI prompt, core protocol, at most two demand-loaded references, project/AGENTS/template/documentation projections, and DPF SkillGuard contract trio. DPF owns domain wording; SkillGuard owns maintenance validation.
- `component:specification`: this OpenSpec change and the canonical specs it will update at archive. OpenSpec remains the only specification authority.
- `component:distribution`: exact shadow-to-formal source promotion, editable package installation, managed-skill installation, and parity verification. Distribution Sync owns projection; it does not own runtime semantics.

One task-level validation plan assigns exactly one execution owner to every check. Affected checks may run during development; after source, toolchain, projections, and owner plan are frozen, `check.models.full` alone owns the complete model campaign and `check.tests.full` alone owns the complete pytest campaign. Receipt consumers inspect those results and never relaunch them.

## Migration Plan

1. Freeze the affected component inventory against the archived prerequisite's canonical OpenSpec 1.6 infrastructure; record that historical reports are not reusable for changed optimizer inputs.
2. Update the existing Behavior Commitment and FlowGuard child model, ContractExhaustion cases, Architecture Reduction decision, and FieldLifecycle direct-replacement inventory.
3. Contract runtime types and projections in the shadow workspace, then run affected model and unit/integration checks.
4. Update skill/prompt/protocol/templates/docs and the DPF SkillGuard contract source; regenerate derived SkillGuard files through the current compiler.
5. Run zero-residual scans and affected OpenSpec/FlowGuard/SkillGuard checks. Fix every failure before task completion.
6. Freeze source/toolchain/impact identities, promote only exact governed files while preserving existing formal changes, sync the shadow from formal, install once, and verify source/formal/installed parity.
7. Execute one final full validation campaign under the frozen owner plan, verify this change against its own current receipts, then archive it.

Rollback is repository-level and pre-publication: the exact changed-path inventory is the rollback boundary in both shadow and formal worktrees. If promotion or installation fails, revert only this change's exact promoted paths or use the installer's atomic backup. Do not leave old and new runtime paths active together.

## Open Questions

- None for implementation. If an external consumer of the thirty-nine strategy exports is discovered outside the authoritative repositories during the formal promotion audit, stop publication and record a separate explicit external migration requirement rather than adding an in-runtime fallback.
