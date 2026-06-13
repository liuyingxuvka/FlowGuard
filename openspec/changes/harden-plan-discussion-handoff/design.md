## Context

FlowGuard already has the pieces needed for high-standard planning: PlanDetailing turns rough plans into structured rows, WorkflowStepContracts preserve receipts, DevelopmentProcessFlow reviews lifecycle freshness, and AgentWorkflowRehearsal checks multi-skill execution order. The failure mode is in the handoff: agents can produce an acceptable prose plan, skip PlanDetailing as a peer route, and later execute from memory instead of from a stable evidence contract.

## Goals / Non-Goals

**Goals:**

- Make `flowguard-plan-detailing-compiler` the direct route for non-trivial plan,方案, acceptance, and execution-step discussions that start from prose or an AI outline.
- Preserve plan subrequirements as stable ids with artifacts, validations, failure/rework gates, skipped/scoped rows, and final evidence ids.
- Expose an AgentWorkflowRehearsal completion ledger so execution and final review can see which planned steps are complete, blocked, skipped, need recheck, or provide handoff evidence.
- Keep DevelopmentProcessFlow focused on lifecycle order and evidence freshness while consuming plan-detail projections for rough plans.

**Non-Goals:**

- Do not create a new universal parent skill that every FlowGuard or Codex skill must pass through.
- Do not make FlowGuard call an LLM or execute the work plan.
- Do not treat plan-detail pass, workflow rehearsal pass, or a long Markdown plan as implementation proof.

## Decisions

1. **Promote PlanDetailing by routing, not by replacing downstream routes.**
   - PlanDetailing owns whether a plan is detailed enough to execute.
   - DevelopmentProcessFlow owns whether lifecycle evidence is current.
   - AgentWorkflowRehearsal owns multi-skill ordering and handoff gates.
   - Alternative considered: make DevelopmentProcessFlow generate detailed plans. Rejected because its current contract is evidence freshness, not plan amplification.

2. **Use additive report fields for the workflow completion ledger.**
   - Add `completed_steps`, `blocked_steps`, `skipped_steps`, `required_rechecks`, and `handoff_points` to `AgentWorkflowRehearsalReport`.
   - Derive the ledger from existing plan steps and findings so existing callers keep working.
   - Alternative considered: add a separate ledger route. Rejected because this is a report view over rehearsal findings, not a new proof owner.

3. **Model the known bad path in executable routing examples.**
   - Add skill-trigger scenarios where a rough AI plan must select PlanDetailing and multi-skill planning must select AgentWorkflowRehearsal.
   - Add broken scenarios for direct execution from prose or routing a rough plan only to DevelopmentProcessFlow.
   - This keeps the behavior from regressing into prompt-only advice.

4. **Keep installed skill guidance synchronized.**
   - Update repository-managed skills and installed local Codex skill copies so local Codex behavior sees the new routing.
   - Treat repository-only changes as insufficient for installed behavior until sync is verified.

## Risks / Trade-offs

- [Risk] PlanDetailing could over-trigger for tiny tasks. -> Keep skip-with-reason wording and tests for trivial direct answers, formatting-only edits, and read-only explanations.
- [Risk] The completion ledger may be mistaken for execution proof. -> Wording and specs state it is a rehearsal/claim-boundary ledger; downstream evidence still proves implementation.
- [Risk] Docs say the right thing but the model does not enforce it. -> Add skill-trigger and rehearsal tests for under-detailed plan hazards.
- [Risk] Other agents may be editing nearby files. -> Keep changes scoped to route/docs/tests and avoid reverting unrelated work.

## Migration Plan

1. Add OpenSpec deltas and task list.
2. Update skill-trigger model and tests for PlanDetailing/AgentWorkflowRehearsal routing.
3. Add AgentWorkflowRehearsal completion ledger fields and tests.
4. Update skill docs, route docs, API/field docs, changelog, and version surfaces.
5. Run focused model/tests, broader route/docs/API tests, and install sync checks.
6. Sync local installed package/skills and record FlowGuard adoption evidence.

Rollback: remove the new routing scenarios, report fields, and documentation deltas. Existing PlanDetailing, DevelopmentProcessFlow, and AgentWorkflowRehearsal behavior remains otherwise compatible.
