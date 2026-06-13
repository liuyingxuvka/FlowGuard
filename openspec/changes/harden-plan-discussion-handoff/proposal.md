## Why

Agents can discuss a strong plan with the user, then later implement against a weaker remembered summary because the plan was never converted into structured, evidence-bound rows. This change makes non-trivial plan discussions produce a stable FlowGuard handoff before execution or completion claims.

## What Changes

- Promote PlanDetailing Compiler as the direct FlowGuard route for non-trivial plan,方案, acceptance, or execution-step discussions that start from prose or an AI outline.
- Require rough plan handoffs to preserve large items, sub-items, artifacts, validation evidence, failure/rework gates, skipped/scoped items, and final claim boundaries as structured rows before downstream routes consume them.
- Extend AgentWorkflowRehearsal reports with an explicit completion ledger so execution and review can see completed, blocked, skipped, recheck, and handoff items.
- Update DevelopmentProcessFlow guidance so it consumes plan-detail projections for lifecycle freshness but does not treat long Markdown plans as structured evidence.
- Add model and regression coverage for the known-bad path where an agent skips plan detailing, executes from a numbered prose plan, and later claims done without checking every agreed subrequirement.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plan-detailing-compiler`: Non-trivial plan discussion becomes a direct route and must expose subrequirements, validation, rework, and final evidence boundaries before execution.
- `flowguard-agent-workflow-rehearsal`: Reports must expose a completion ledger derived from planned workflow steps and findings.
- `development-process-flow`: Lifecycle review must consume plan-detail projections for rough plans and reject prose-only plan evidence for broad claims.
- `flowguard-codex-skill-satellites`: Installed Codex skill routing must make plan detailing a peer satellite route, not a hidden child of DevelopmentProcessFlow.
- `flowguard-global-routing`: Route guidance must send rough plans and AI-generated outlines to PlanDetailing before staged development or multi-skill rehearsal.

## Impact

- Affected code: FlowGuard skill-trigger examples, AgentWorkflowRehearsal report API, PlanDetailing/DevelopmentProcessFlow guidance and tests.
- Affected docs/skills: `docs/agents_snippet.md`, route docs, `.agents/skills/*/SKILL.md`, and protocol references.
- No breaking changes are intended; new report fields are additive.
