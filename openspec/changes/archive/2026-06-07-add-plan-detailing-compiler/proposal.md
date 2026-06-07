## Why

FlowGuard already checks structured plans, lifecycle freshness, step receipts, and final confidence claims, but a human or AI can still enter with a vague plan that has not declared enough detail to check. This change adds a first-class plan detailing layer so rough ideas are forced into explicit scope, state, steps, evidence, failure, rework, and claim boundaries before modeling or implementation.

## What Changes

- Add a public plan-detailing compiler capability that converts a rough task idea into a structured FlowGuard-ready plan draft.
- Add typed plan-detail records for goals, assumptions, scope, artifacts, state surfaces, side effects, steps, receipts, validations, failure branches, rework gates, human-review questions, and final claim boundaries.
- Add review helpers that block or scope under-detailed plans instead of treating long prose as complete planning evidence.
- Add a template and CLI entry for a combined plan-detail, workflow-step-contract, and development-process scaffold.
- Update model-first routing so non-trivial vague plans start with plan detailing before behavior modeling.
- Update DevelopmentProcessFlow, PlanIntake, WorkflowStepContracts, and AgentWorkflowRehearsal guidance so they consume plan-detail outputs instead of relying on ad hoc prose.
- Update installed Codex skill surfaces and local sync/version records after validation.

## Capabilities

### New Capabilities
- `plan-detailing-compiler`: Compile rough ideas into structured, checkable FlowGuard plan details and review whether the plan has enough detail to proceed.

### Modified Capabilities
- `model-first-function-flow`: Route vague or under-specified non-trivial work through plan detailing before core modeling.
- `development-process-flow`: Consume plan-detail lifecycle rows as the starting point for artifact, action, evidence, freshness, and revalidation review.
- `plan-intake-claims`: Treat plan-detail risk surfaces, source evidence, scoped omissions, and unknowns as plan-intake inputs.
- `workflow-step-contracts`: Compile plan-detail steps into receipt-producing workflow step contracts.
- `flowguard-agent-workflow-rehearsal`: Treat plan-detail records as the structured workflow handoff for AI-agent planning.
- `flowguard-codex-skill-satellites`: Include the new direct satellite and installed-skill synchronization requirement.
- `flowguard-global-routing`: Route rough-plan-to-detailed-plan requests to the new plan-detailing compiler.

## Impact

- New package module, public API exports, docs, OpenSpec spec, example model, tests, and template CLI.
- Updates to model-first skill guidance, satellite skill topology, documentation, and public templates.
- No runtime dependencies are added.
- Backward compatibility is preserved: existing route-specific helpers continue to work without plan-detail records, but broad claims from vague plans gain an explicit detail gate.
