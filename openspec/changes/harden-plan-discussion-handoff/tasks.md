## 1. Route Model And Regression Coverage

- [x] 1.1 Extend the FlowGuard skill-trigger model with rough-plan and multi-skill plan routing signals.
- [x] 1.2 Add positive scenarios that select PlanDetailing for non-trivial plan discussion and AgentWorkflowRehearsal for multi-skill execution planning.
- [x] 1.3 Add broken scenarios that catch direct execution from prose or routing rough plans only to DevelopmentProcessFlow.
- [x] 1.4 Update skill-trigger tests for the expanded scenario counts and expected outcomes.

## 2. AgentWorkflowRehearsal Completion Ledger

- [x] 2.1 Add additive completion-ledger fields to `AgentWorkflowRehearsalReport`.
- [x] 2.2 Derive completed, blocked, skipped, required-recheck, and handoff rows from the existing plan and findings.
- [x] 2.3 Include the ledger in `format_text()` and `to_dict()` without breaking existing callers.
- [x] 2.4 Add tests that prove passing and blocked plans expose the ledger correctly.

## 3. Guidance And API Surfaces

- [x] 3.1 Update PlanDetailing, AgentWorkflowRehearsal, and DevelopmentProcessFlow skill/protocol docs with the new plan-discussion handoff route.
- [x] 3.2 Update global routing docs and reusable AGENTS guidance so PlanDetailing is a peer direct satellite route.
- [x] 3.3 Update API/field documentation and public template wording for the completion ledger and plan-discussion handoff.
- [x] 3.4 Update changelog and version metadata for the local release surface.

## 4. Validation And Sync

- [x] 4.1 Run focused tests for PlanDetailing, DevelopmentProcessFlow, AgentWorkflowRehearsal, and skill-trigger routing.
- [x] 4.2 Run docs/API/template/OpenSpec validation tests affected by the guidance and report-field changes.
- [x] 4.3 Run the strongest practical broader regression suite.
- [x] 4.4 Sync local editable installation and installed Codex skill copies, then verify imports and installed guidance.
- [x] 4.5 Record FlowGuard adoption evidence and predictive-KB postflight observation.
