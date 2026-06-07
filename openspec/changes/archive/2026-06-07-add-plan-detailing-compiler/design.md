## Context

FlowGuard currently has strong route-specific checkers: Risk Intent, PlanIntake, WorkflowStepContracts, DevelopmentProcessFlow, AgentWorkflowRehearsal, and final confidence routes. These routes can catch stale evidence, missing receipts, overbroad claims, skipped skills, and incomplete risk surfaces once a plan has been written in a structured form.

The missing layer is before those checkers: a human or AI can start with a rough idea, write a short plan, and accidentally omit state, side effects, failure branches, rework gates, evidence receipts, or human-review questions. The system needs a first-class detail amplifier that turns the rough idea into FlowGuard-native rows and rejects under-detailed outputs.

## Goals / Non-Goals

**Goals:**
- Add a public plan-detailing compiler with typed rows for plan scope, surfaces, steps, receipts, validation, failures, rework, unknowns, and claim boundaries.
- Make the compiler deterministic over provided structured inputs. AI may draft the inputs, but FlowGuard reviews the structure.
- Provide a combined template and CLI that teaches agents to fill the plan-detail rows before writing behavior models or claiming done.
- Connect plan-detail rows to existing routes: PlanIntake, WorkflowStepContracts, DevelopmentProcessFlow, and AgentWorkflowRehearsal.
- Add executable scenarios that prove good detailed plans pass and vague, happy-path-only, evidence-free, or no-rework plans are blocked or scoped.

**Non-Goals:**
- Do not call LLMs from FlowGuard.
- Do not make FlowGuard execute the work plan.
- Do not replace route-specific proof. Plan-detail pass means the plan is detailed enough to proceed; it is not production confidence.
- Do not require existing users to rewrite all route-specific plans immediately.

## Decisions

### Add one public plan-detailing compiler module

Add `flowguard.plan_detailing` with dataclasses such as `PlanDetail`, `PlanDetailStep`, `PlanDetailSurface`, `PlanDetailArtifact`, `PlanDetailValidation`, `PlanDetailFailureBranch`, and `PlanDetailHumanQuestion`. The primary helper is `review_plan_detail(plan)`.

Alternative considered: only strengthen `RiskIntent`. That would improve modeling prompts but would not create lifecycle steps, receipts, evidence gates, or rework branches that downstream routes can consume.

### Keep generation outside FlowGuard and validation inside FlowGuard

The compiler consumes structured rows and returns findings. AI agents can generate the rows from prose, but FlowGuard does not trust prose length as evidence.

Alternative considered: add an LLM-based auto planner. That would create dependency, repeatability, and evidence problems.

### Provide projection helpers instead of duplicating existing routes

Add helpers to turn plan-detail rows into:
- `PlanIntakeCompletenessPlan`
- `WorkflowStepContract` rows
- `DevelopmentProcessPlan`
- `AgentWorkflowPlan` skeletons where applicable

The existing routes remain the proof owners.

### Make missing detail visible as blocked or scoped

For non-trivial plans, missing goal, scope, state surface, side effect mapping, validation, failure branch, rework gate, receipt, or final claim evidence should produce a finding. Broad completion claims are blocked when detail gaps remain; narrow exploratory use can be scoped.

### Add one combined public template

Add `python -m flowguard plan-detailing-template --output .` that writes a starter model plus notes. The template should include one complete plan and several broken variants so agents can see what "not detailed enough" means.

## Risks / Trade-offs

- [Risk] The plan-detail schema becomes too large and slows ordinary work. -> Mitigation: keep only core rows required to make hidden details visible; trivial work can skip with reason.
- [Risk] Agents treat plan-detail pass as implementation proof. -> Mitigation: reports and docs must state that plan-detail pass only means the plan can proceed.
- [Risk] Projections drift from downstream route expectations. -> Mitigation: add focused tests for each projection helper and template execution.
- [Risk] The first version misses domain-specific details. -> Mitigation: leave domain-specific rows in metadata and route specialized concerns to the existing satellite skills.

## Migration Plan

1. Add OpenSpec specs and executable FlowGuard model for the new capability.
2. Implement public dataclasses, review helper, projections, exports, CLI, docs, and template.
3. Update model-first skill guidance and satellite routing docs.
4. Add tests for direct review, projections, template execution, CLI listing, and installed skill wording.
5. Run focused and full regressions, then sync editable install and the shadow workspace.
6. Keep the old route-specific templates working.

Rollback: remove the new routing entry and template command. Existing route-specific helpers remain compatible.

## Open Questions

- None for first implementation. Future work can add domain packs for common planning surfaces after real usage shows stable patterns.
