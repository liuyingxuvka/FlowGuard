---
name: model-first-function-flow
description: FlowGuard kernel for ordinary behavior/state modeling, unclear FlowGuard route selection, cross-route coordination, and core model-first preflight. Use when no direct FlowGuard satellite skill clearly matches or when multiple FlowGuard routes must be coordinated; route clear existing-model preflight, staged development, UI, structure, test, mesh, alignment, and model-miss work to the matching FlowGuard satellite skill directly.
---

# FlowGuard Skill Kernel

This is the compact FlowGuard router and hard-gate layer. Keep detailed
protocols in `references/*.md` or in the matching standalone satellite skill.
Use a direct satellite when the route is obvious; use this kernel for ordinary
behavior/state modeling, unclear route selection, cross-route coordination, or
core model work before narrowing.

## Applicability

Decision: `use_flowguard`, `skip_with_reason`, or `needs_human_review`; flow lenses are `behavior_flow`, `argument_flow`, and `decision_flow`.

Use FlowGuard when order, state, ownership, retries, side effects, validation freshness, release/process steps, UI state, model-test evidence, or module boundaries can change safety. Use plan detailing first when a rough plan lacks scope, state, artifacts, evidence, or rework.

Skip only tiny copy edits, formatting-only changes, direct command answers, or read-only explanation with no behavior/state/process impact. If the boundary is unclear, narrow it or mark `needs_human_review`.

## Minimum Valuable Model

```text
risky boundary -> protected error class -> public/local risk template search
-> Input x State -> Set(Output x State)
-> state + side effects + completion evidence + known-bad case
-> FlowGuardCheckPlan + run_model_first_checks
-> inspect counterexample -> record template harvest closure
```

The default entry is compact, but it must have teeth. A new or deepened model
needs to say what real error it prevents, which public/local template it reused
or why none matched, what completion evidence proves the work, and which
representative bad implementation would fail. Complete claims still need
current evidence for the selected route, and missing/stale/skipped evidence
means partial or scoped FlowGuard evidence.

When package helpers are needed, read `AGENT_DEFAULT_API`, then the selected
`ROUTE_STARTER_API[route_id]`. Load advanced indexes or full templates only
after the route needs deep evidence.

## Hard Gates

- Verify the real package before modeling: `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- For real target-project use, ensure the FlowGuard AGENTS.md managed block/version record exists; if installed FlowGuard is newer, run `python -m flowguard project-upgrade --root .` with artifact/model/test upgrade scanning before relying on old models/tests/evidence.
- FlowGuard is latest-schema-first: upgrade old artifacts at project/tool boundaries; do not preserve long-lived runtime compatibility for obsolete fields, aliases, or wrappers.
- Default replacement means cleanup: old fields, aliases, wrappers, fallback paths, and compatibility-like surfaces need a disposition unless the user explicitly requests compatibility preservation.
- Important business paths need identity when route semantics affect confidence: path id, business intent, trigger, expected terminal, state writes, side effects, equivalent/exclusive paths, old-path disposition, and evidence ids.
- If import fails, connect the real toolchain or report blocked/partial; do not write a temporary mini-framework or fake mini-framework substitute.
- Represent modeled blocks as `Input x State -> Set(Output x State)`.
- Treat direct finite-engine calls as internal mechanics, not the formal entry
  for non-trivial model creation.
- Do not replace executable modeling with prose or weaken invariants to pass.
- Preserve user and peer-agent changes; later writes can stale evidence.
- Long checks may run in the background, but final confidence needs exit/status and result artifacts, not progress lines.
- Reused test results need current `TestResultReuseTicket` and `ProofArtifactRef`; old `passed` output is not current evidence by itself.
- Broad confidence needs model obligation ids, owner code contract ids, and current external-contract test evidence bound to the same behavior; model+test-only rows are scoped/blocked.
- Broad transition-test claims need a transition matrix projected to MTA code/test rows or TestMesh, or an explicit scoped-out reason.
- Same-class/finite bad-case generation routes through `contract_exhaustion_mesh`
  after the owner declares the boundary; hand-written examples are only seeds.
- Complete runnable UI claims need reachable enabled controls clicked or scoped as pure UI/deferred blindspots with structured evidence.
- File import/export, generated artifact, and AI work-package claims need synthetic payload cases for the real payload surface plus current external evidence refs or proof artifacts; prose-only manual checks are scoped/blocked.
- New/deepened models need template harvest closure before broad claims: written, merged, duplicate-linked, or accepted not-harvestable.
- After `run_model_first_checks()`, read structured ledger owner routes and maintenance obligations before manually inferring the next route.
- Before trusting one route/model, let ExistingModelPreflight consume model-angle and similarity evidence when the task may need a missing viewpoint or resembles another workflow.
- For non-trivial FlowGuard work, show a route-specific Mermaid snapshot once the route/model is stable; diagrams explain, not validate.
- Before broad done/release/publish confidence, use Risk Evidence Ledger or equivalent and keep remembered maintenance obligations, automatic state-closure, and topology-hazard gaps visible.
- Guard-family children must return closure reports with `owner_guard`, `artifact_kind`, `closure_status`, `findings`, `missing_inputs`, `stale_evidence`, `skipped_checks`, `next_actions`, `safe_claim`, and `unsafe_claim_boundary`; validate them with `assets/guard_closure_contract.py` before broad confidence.
- Treat child `partial`, `blocked`, `downgraded`, stale, skipped, or hard-finding reports as FlowGuard maintenance obligations, not passed final claims.

## Route Map

Pick the smallest named route that owns the actual risk. Helper APIs and
template CLIs are package helpers, not independently triggerable Codex skills.
Default route template CLIs are compact; use full-template commands only when
the row below calls for deep route evidence.

| Trigger | Route | Entry |
| --- | --- | --- |
| Older adopted project, old FlowGuard artifact, old model/test evidence, obsolete API aliases | `artifact_schema_upgrade` | `artifact-upgrade` or `project-upgrade` |
| FlowGuard itself feels heavy, route groups are incomplete, field layers need folding, or AI needs route-first self-maintenance | `flowguard_self_maintenance` | `review_flowguard_self_maintenance()` |
| Existing modeled system, ownership lookup, duplicate-boundary risk, missing model angle, or similar workflow/model/test family | `existing_model_preflight` | `flowguard-existing-model-preflight`; consumes model-angle and similarity rows |
| Field additions, removals, renames, migrations, replacements, prompt/config fields, payload/schema keys, old-field disposition | `field_lifecycle_mesh` | `flowguard-field-lifecycle-mesh` |
| Canonical finite bad-case generation from declared boundaries/families/payloads/transitions/mesh closure | `contract_exhaustion_mesh` | `flowguard-contract-exhaustion-mesh` |
| New/deepened model must reuse/search and close public/local template harvest | `risk_template_library` | `risk-template-search`, `risk-template-harvest`, `risk-template-harvest-review`, or `risk-template-library-template` |
| Rough plan, multi-skill/tool setup, staged execution, post-change scan, install/sync, release/archive/publish, or final process claim | `development_process_flow` | `flowguard-development-process-flow` simulator owner; may delegate `flowguard-plan-detailing-compiler` or `flowguard-agent-workflow-rehearsal` |
| Ordinary behavior/state modeling, Risk Intent, state inventory | `core_modeling` | `references/modeling_protocol.md` |
| Existing code/prompt flow should shrink without behavior loss | `architecture_reduction` | `flowguard-architecture-reduction` |
| Pre-code module/function/block ownership recommendation | `code_structure_recommendation` | `flowguard-code-structure-recommendation` |
| UI controls, screens, journeys, display/text ownership, runnable UI evidence | `ui_flow_structure` | `flowguard-ui-flow-structure` |
| Locally green model topology implies future-use hazards, duplicate/conflicting paths, or old/new route gaps before broad confidence | `model_topology_hazard_review` | `flowguard-model-topology-hazard-review` |
| Model obligations, transition coverage, files/work packages, or code/test/boundary rows | `model_test_alignment` | `flowguard-model-test-alignment` |
| Three or more models, oversized model, stale child evidence, parent/child mesh | `model_mesh_maintenance` | `flowguard-model-mesh` |
| Large/slow/stale/release-only tests or parent/child test hierarchy | `test_mesh_maintenance` | `flowguard-test-mesh` |
| Large script/module/package/API split, facade or public entrypoint parity | `structure_mesh_maintenance` | `flowguard-structure-mesh` |
| Staged development, edits, validation freshness, install/shadow/git sync | `development_process_flow` | `flowguard-development-process-flow` |
| Non-trivial bug repair, false confidence, or runtime/test/replay/manual evidence shows a missed failure class | `model_miss_review` | `flowguard-model-miss-review` |
| Model too coarse after state-closure/code/test/mesh/freshness evidence | `model_maturation_loop` | `references/modeling_protocol.md` |
| Final broad confidence boundary | `risk_evidence_ledger` | `docs/risk_evidence_ledger.md` |
| Production conformance, install sync, shadow workspace sync | `conformance_adoption` | `references/conformance_adoption_protocol.md` |
| Long-running model/test/regression check | `long_check_observability` | `references/long_check_protocol.md` |
| FlowGuard framework upgrade or benchmark/corpus claim | `framework_upgrade` | `references/framework_upgrade_protocol.md` |
| Guard-family child reports, cross-Guard gaps, stale child evidence, skipped child checks | `guard_closure_contract` | `assets/guard_closure_contract.py` |

When no direct route clearly matches, stay in this kernel and build the smallest
formal executable model first.

## Minimal Workflow

1. Decide applicability/lens, verify the package/adoption record for real project work, and model the risky finite-state boundary.
2. Search public/local risk templates before new or deepened modeling, then record used template ids or a no-match reason.
3. Make at least one representative bad path fail before trusting the pass.
4. For broad same-class/finite-boundary claims, route canonical ContractExhaustionMesh cases to MTA/TestMesh/ModelMesh/Risk Ledger.
5. Inspect counterexamples, revise model/code/tests/process, record template harvest closure, derive obligations, validate, and record evidence.

## Reference Map

- Kernel/core: `references/skill_kernel_protocol.md`, `references/modeling_protocol.md`, `references/invariant_examples.md`, `references/adoption_protocol.md`.
- Supporting protocols: `references/model_test_alignment_protocol.md`, `references/model_mesh_protocol.md`, `references/test_mesh_protocol.md`, `references/structure_mesh_protocol.md`, `references/development_process_flow_protocol.md`, `references/model_miss_protocol.md`, `references/conformance_adoption_protocol.md`, `references/long_check_protocol.md`, `references/framework_upgrade_protocol.md`, `references/project_integration.md`.
- Starter assets: `assets/model_template/model.py`, `assets/model_template/run_checks.py`, `assets/toolchain_preflight.py`.

## Constraints

Use Python standard library code in models. Keep abstract state finite,
immutable, and inspectable. Do not call LLM APIs, databases, network services,
clocks, random sources, probability models, or Monte Carlo from the model.
