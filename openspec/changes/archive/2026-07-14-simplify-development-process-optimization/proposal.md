## Why

FlowGuard now models development-process optimization, but the current implementation turns that useful capability into a mandatory six-policy ceremony with a large public API, duplicated cross-owner fields, and caller-authored numeric costs. The result can be functionally green while making ordinary work harder and without proving that the selected process is actually lower effort.

This change preserves the original general requirement—choose a lower-rework process among outcome-equivalent routes, diagnose related failures before repair when useful, stop on true blockers, batch root-cause repairs, revalidate affected obligations, and replan on material evidence—while making the optimizer conditional and substantially smaller.

## What Changes

- Keep `flowguard-development-process-flow`, route `development_process_flow`, internal mode id `strategy_selection`, and the existing development-process behavior commitment as the sole public ownership path.
- Activate process optimization only for an explicit optimization request, multiple outcome-equivalent viable routes, material repeated-work risk, or a real diagnostic-boundary choice. Ordinary single-route work performs no candidate/frontier/cluster ritual.
- Replace the six mutually exclusive policy names with two composable decisions: diagnostic boundary (`targeted`, `declared_complete`, or `budgeted`) and execution mode (`sequential` or evidence-backed `safe_parallel`). Hard blockers become universal stop conditions and material-change replanning becomes universal optimizer behavior.
- Preserve raw findings and not-run facts, group only evidence-related findings into compact repair groups, and require revalidation of every affected obligation after repair.
- Delegate diagnostic execution facts to TestMesh, raw findings to the Finding Ledger, dependency DAGs to SpecWorkPackage/PlanDetail, and model-code-test ownership to ordinary Model-Test Alignment instead of copying those structures into the optimizer.
- Remove caller-authored cost vectors, Pareto/frontier ceremony, rollout stages, duplicate strategy projections, and the standalone public strategy review surface. Keep bounded coverage-first affected-revalidation selection inside DevelopmentProcessFlow and narrow all optimality claims to their actual evidence basis.
- Replace the synthetic score benchmark with replayable process traces that first prove equal outcome/evidence/safety/authority and then compare check runs, repair rounds, revalidation rounds, and visible not-run accounting.
- Make prompt, protocol, templates, project guidance, model artifacts, tests, and SkillGuard obligations share the same conditional activation and claim boundary.
- **BREAKING**: directly replace the current strategy dataclasses, constants, serialized fields, and public exports. Do not add aliases, dual readers, compatibility wrappers, or alternate success paths; retained persisted project artifacts may be upgraded only at the explicit project-upgrade boundary.

## Capabilities

### New Capabilities

- None. This change contracts and strengthens existing DevelopmentProcessFlow behavior instead of adding a parallel capability.

### Modified Capabilities

- `development-process-strategy-selection`: Replace mandatory six-policy/Pareto selection with conditional, evidence-grounded diagnostic-boundary and execution-mode decisions, compact repair grouping, affected revalidation, and material-change replanning.
- `development-process-simulator`: Admit the internal optimizer only from explicit reason codes while retaining the stable `strategy_selection` mode identity and mode order.
- `development-process-flow`: Reference one independently owned optimization-decision evidence artifact, enforce freshness and hard equivalence, expose inactive/selected/blocked status, and keep coverage-first affected revalidation without embedding a second optimizer schema in the plan.
- `test-evidence-mesh`: Record diagnostic boundary, execution counts, visible not-run reasons, and stable finding references without owning strategy selection or failure clusters.
- `plan-detailing-compiler`: Keep only optimization reason ids and required optimization-evidence ids at the plan boundary, and stop copying strategy/campaign/batch fields into every step and validation row.
- `model-test-alignment`: Remove the strategy-specific alignment binding and use ordinary obligation-to-code-to-test alignment for repair-group closure.
- `behavior-commitment-ledger`: Preserve the current commitment identity while changing its expected result, evidence cases, state writes, and source surfaces to the contracted optimizer.
- `flowguard-api-registry`: Retire the standalone development-process strategy API group and expose at most five compact optimizer records plus one review function through the existing DevelopmentProcessFlow group.
- `flowguard-codex-skill-satellites`: Make process optimization conditional in the DPF skill, default prompt, and protocol; always preserve the original related-failure and hard-blocker distinction.
- `flowguard-skill-suite-distribution`: Require source, shadow, formal, and installed prompt/contract parity after the direct-current replacement.

## Impact

- Runtime: `flowguard/development_process_strategy.py`, `development_process_flow.py`, `development_process_simulator.py`, `testmesh.py`, `plan_detailing.py`, `model_test_alignment.py`, `summary_report.py`, and `flowguard/__init__.py`.
- Models and governance: the existing strategy child model, Behavior Commitment Ledger, ContractExhaustionMesh cases, FieldLifecycleMesh inventory, API registry, and validation execution plan.
- Agent surfaces: the DevelopmentProcessFlow skill, conditional reference material, OpenAI prompt, project-adoption source, generated AGENTS projection, templates, and public documentation.
- Tests: strategy/model tests, trace benchmark, DPF/simulator/TestMesh/PlanDetail/MTA/API/template/SkillGuard tests, registered model inventory, and one frozen OpenSpec campaign with one complete-model owner and one complete-pytest owner.
- Change coordination: `reconcile-spec-provider-work-packages-with-flowguard-evidence` is now archived and its canonical OpenSpec 1.6 receipt/freshness infrastructure is the only current dependency. Its historical receipts do not prove this change and are not reused after optimizer inputs change.
