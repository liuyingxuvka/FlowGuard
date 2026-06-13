## Why

FlowGuard UI can already catch many fake visible controls, but it can still miss a more upstream failure: a required user-visible capability may never be entered into the UI model at all. That lets an agent claim a UI is complete while core functions such as load, plot, refresh, export, or save are absent rather than merely unwired.

This change strengthens the existing UI Flow Structure route instead of creating a parallel UI workflow. Functional capability coverage becomes a hard evidence layer that feeds the existing feature contracts, user task ledger, journey coverage, functional chains, implementation validation, process freshness, model-miss review, risk ledger, and closure contract.

## What Changes

- Add first-class UI functional capability inventory, output contract, capability binding, and coverage review models under the existing `ui_structure` route.
- Extend `UIFeatureContract`, `UIUserTaskCoverageLedger`, and `UIImplementationValidation` so existing UI evidence can prove capability completeness rather than only checking listed features or observed controls.
- Require every required user-visible capability to map to feature contract, user task, UI journey/control/event, code or functional-chain owner, expected output, and current evidence or a scoped blindspot.
- Treat result-producing UI functions such as charts, tables, files, generated artifacts, saved output, and status changes as output contracts with assertions, not just visible containers.
- Strengthen PlanDetailing, Model-Miss Review, DevelopmentProcessFlow, RiskEvidenceLedger, AgentWorkflowRehearsal, and ClosureContract surfaces so broad UI completion claims cannot omit required capabilities.
- Keep source-based, greenfield, and mixed UI routing generic. Source-baseline evidence remains responsible for source fidelity; capability coverage accounts the product/user-visible function inventory for all UI work modes.
- Update public docs, templates, installed skill guidance, API exports, field docs, OpenSpec specs, changelog/version, tests, editable install, installed skills, shadow workspace, and local git/tag.

## Capabilities

### New Capabilities

- `ui-functional-capability-coverage`: Accounts required user-visible UI capabilities and binds them to existing UI features, tasks, journeys, controls/events, functional chains, output contracts, evidence, and scoped blindspots.

### Modified Capabilities

- `flowguard-ui-flow-structure`: Add capability inventory as a hard layer inside the existing route before broad UI model, human-operability, implementation, or completion claims.
- `ui-implementation-validation`: Require implementation validation to consume current capability coverage when a running UI is claimed complete or runnable for user-visible functions.
- `ui-human-operability-validation`: Require task coverage to be capability-complete, not only feature-label complete.
- `plan-detailing-compiler`: Require UI plans to name capability inventory, output contracts, implementation bindings, and evidence kinds before execution-ready UI claims.
- `post-runtime-model-miss-review`: Classify user-observed missing UI functionality as a model miss when prior FlowGuard evidence was green or used for a completion claim.
- `development-process-flow`: Treat capability inventories, output contracts, and implementation bindings as freshness-sensitive UI artifacts.
- `risk-evidence-ledger`: Add a UI functional capability coverage gate for final risk confidence.
- `flowguard-closure-contract`: Require current capability coverage evidence before final UI done/release confidence when user-visible UI functions are in scope.
- `flowguard-agent-workflow-rehearsal`: Require a capability-inventory/checker role for multi-agent UI implementation work before full runnable UI confidence.

## Impact

- Public API additions in `flowguard.ui_structure` and `flowguard.__init__`.
- Additive fields on existing UI evidence dataclasses.
- Review logic and tests for capability omissions, dependency gaps, output-contract gaps, and overclaimed UI completion.
- Docs, public templates, route skills, OpenSpec specs, and installed Codex skills.
- Version metadata, changelog, local editable install, shadow workspace, local git tag.
