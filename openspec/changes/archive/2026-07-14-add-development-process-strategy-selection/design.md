## Context

DevelopmentProcessFlow (DPF) is already the single public owner for staged development, validation freshness, minimum revalidation, SpecWorkPackage receipts, and final process claims. Its present model validates one supplied plan; it does not represent competing plans, prove their outcome equivalence, or compare their expected effort. TestMesh records child evidence but does not say whether a diagnostic campaign intentionally stopped early or finished enumerating its declared boundary. The finding ledger preserves findings but does not own clustering or repair strategy.

The new capability must therefore improve the existing owner instead of introducing a parallel workflow engine. It must work for diagnostic/repair examples, but its abstraction must also cover build, migration, review, synchronization, maintenance, release, and other staged processes.

## Goals / Non-Goals

**Goals:**

- Compare only candidates that satisfy the same hard outcome, evidence, safety, and authority contract.
- Recommend a deterministic, non-dominated strategy using explicit cost and information-value dimensions.
- Support fail-fast, collect-all, focused-first, bounded collection, safe parallel shards, and adaptive re-evaluation.
- Make diagnostic coverage, early stopping, clustering, root-cause hypotheses, repair batching, and post-batch revalidation machine-readable.
- Preserve DPF, TestMesh, PlanDetailing, Model-Test Alignment, OpenSpec, SpecWorkPackage, Model Miss, Contract Exhaustion, and Architecture Reduction ownership boundaries.
- Make every optimality statement bounded and auditable.

**Non-Goals:**

- Do not execute tests, edit code, create provider tasks, choose product behavior, or replace specialist route judgments.
- Do not require collect-all before every repair or make any strategy globally preferred.
- Do not solve unrestricted global optimization or claim an optimum outside an explicitly exhausted finite candidate boundary.
- Do not expose internal strategy/campaign fields as product UI content.
- Do not add a public skill or route beside `flowguard-development-process-flow`.

## Decisions

### 1. Add one DPF-owned internal strategy module and child model

Add `flowguard/development_process_strategy.py` and `.flowguard/development_process_strategy/model.py`. The Python module owns canonical data, review, Pareto comparison, and deterministic recommendation. The executable child model owns state/order invariants and known-bad traces. DPF consumes the report and remains the public facade.

Alternative: place all types directly in `development_process_flow.py`. Rejected because that module already owns lifecycle/freshness review and would become a second monolith. Alternative: create a public `flowguard-process-optimizer` skill. Rejected because it would duplicate DPF's external purpose.

### 2. Equivalence is a hard gate, cost is a later soft comparison

Each candidate references one `ProcessOutcomeContract` covering terminal outcomes, required evidence, safety constraints, protected side effects, and authority owners. The review first excludes candidates that are stale, inapplicable, incomplete, or non-equivalent. Cost comparison never compensates for a missing hard requirement.

This prevents a shorter but weaker plan from being called “better.” It also permits specialist routes to supply their own evidence without strategy selection taking ownership.

### 3. Use an explicit multi-objective cost vector and Pareto frontier

`ProcessCostVector` records effort, elapsed time, repeated work, coordination load, change risk, and negative information value (higher information value reduces effective cost). Dominance is component-wise. The report exposes all non-dominated candidate ids and selects one deterministically using a declared objective order and stable candidate-id tie break.

The report can say `valid` or `non_dominated_within_candidates` whenever the eligible set is partial. It can say `minimum_within_declared_finite_boundary` only when the candidate inventory is declared complete, every candidate has current comparable cost, and the finite boundary is named. It never says `global_minimum`.

### 4. Strategies are policies, not fixed scripts

The current strategy vocabulary is `fail_fast`, `collect_all`, `focused_first`, `bounded_collect`, `parallel_shards`, and `adaptive`. Candidate records declare applicability, stop conditions, campaign/shard identities, and expected repair/revalidation behavior. The selector has no universal default: urgency, destructiveness, diagnostic independence, failure correlation, setup cost, and evidence requirements determine eligibility.

### 5. Separate raw observations from clustering and repair decisions

`FailureObservation` points to raw test/finding/evidence ids. `FailureCluster` groups observations using explicit relation evidence. `RootCauseHypothesis` explains one or more clusters with confidence and disproof checks. `RepairBatch` selects clusters/hypotheses, owned artifacts, and mandatory revalidation ids. The finding ledger remains the raw observation owner; this module owns only strategy-level grouping and batching.

Unclustered observations require an explicit scoped disposition. A batch cannot claim closure merely because code changed; its declared revalidation must be current.

### 6. Campaign completeness and dynamic re-evaluation are first-class

`DiagnosticCampaign` records planned item ids, executed ids, failed ids, not-run ids, enumeration completeness, and an early-stop reason. The identity equation is checked: every planned item is executed or visibly not run. “Complete” requires full declared enumeration; an early stop can be valid but cannot masquerade as complete.

`StrategyReevaluation` links new evidence or a completed repair batch to the prior and next candidate decision. Material new observations, changed assumptions, or repair-batch completion require re-evaluation before execution continues under the old recommendation.

### 7. Integrate by projection, not ownership transfer

- `DevelopmentProcessPlan` references a current strategy plan/report and blocks strategy-required claims when it is missing or stale.
- The simulator inserts internal `strategy_selection` between plan detailing and agent workflow/execution freshness when multiple viable sequences, expensive rework, diagnostic campaigns, or final optimization claims are present.
- TestMesh child evidence carries campaign counts/completeness/early-stop and observation/cluster ids; it still does not choose strategy or run tests.
- PlanDetail rows carry selected candidate, campaign, repair batch, and re-evaluation gate ids.
- Model-Test Alignment carries explicit strategy binding rows from clusters/batches to existing obligation and code-contract ids.
- ContractExhaustionMesh supplies finite adverse combinations; Model Miss is used only after previously green modeled evidence misses runtime behavior; Architecture Reduction owns structural deletion/contraction proposals.
- SpecWorkPackage remains the sole OpenSpec task/check/session/receipt reconciliation owner.

### 8. Use current-schema additive APIs and direct skill replacement

The package exports the new canonical types and review function through the existing facade and route metadata. Existing DPF inputs remain valid when strategy optimization is not required. No legacy aliases, dual readers, fallback success path, or compatibility command is introduced. Managed skill guidance is directly updated under SkillGuard supervision and regenerated from contract source.

### 9. Stage enforcement

Rollout stages are `shadow`, `advisory`, `opt_in`, and `conditional_default`. Shadow/advisory can report a recommendation without blocking execution. Opt-in blocks when the caller explicitly requires a strategy decision. Conditional default blocks only for policy-declared scopes and only with current equivalence/candidate evidence. Rollback is a policy-stage change, not a second implementation path.

## Risks / Trade-offs

- [Estimated cost is wrong] → Preserve component values, rationale, confidence, and bounded claim; allow re-evaluation when observations differ from estimates.
- [Candidate explosion] → Use finite declared candidates, dominance pruning, ContractExhaustion shards, and a visible partial-boundary claim.
- [Over-clustering hides independent faults] → Require relation evidence and disproof checks; retain raw observation identities.
- [Collect-all delays urgent containment] → Safety/urgency constraints make fail-fast eligible and can exclude collection strategies.
- [Parallel shards interfere] → Require disjoint or explicitly allowed shared state/side effects and retain TestMesh ownership checks.
- [New fields become stale] → Register FieldLifecycle rows, source readers/writers, model-test bindings, and DPF freshness inputs.
- [Skill/package drift] → Freeze affected SkillGuard owner plan, regenerate only maintained current contracts, validate affected targets, then run one final full owner.

## Migration Plan

1. Add and pass the executable child model with known-bad traces.
2. Add the canonical Python module, package exports, API registry membership, and focused unit tests.
3. Integrate DPF/simulator/TestMesh/PlanDetailing/alignment projections and run affected checks.
4. Update the Behavior Commitment Ledger, FieldLifecycleMesh, DCAR/alignment evidence, templates, docs, and DPF skill contract under SkillGuard.
5. Run benchmark comparisons showing when each strategy wins and proving no universal collect-all rule.
6. Keep tracked change tasks limited to implementation and pre-archive gate preparation so the archive hard gate is not made self-referential. Freeze and run the affected-only SpecWorkPackage plan, close its current post-snapshot evidence, run OpenSpec verification through the same current owner receipts, and archive only after every tracked task is complete. Archive execution, the one post-archive unified full validation, and KB postflight are orchestration handoffs outside the tracked change task list; they still remain mandatory before the repository task is complete.

## Open Questions

None block implementation. Initial cost values are caller-supplied abstract non-negative numbers; automatic measurement/calibration can be added later without changing the hard equivalence contract.
