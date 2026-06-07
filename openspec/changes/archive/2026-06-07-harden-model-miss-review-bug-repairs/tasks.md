## 1. OpenSpec And Route Scope

- [x] 1.1 Add spec deltas for Model-Miss Review bug repair triggers and root-cause backpropagation.
- [x] 1.2 Add spec deltas for model-code-test binding and closure/freshness handoffs in existing routes.
- [x] 1.3 Validate the OpenSpec change strictly before implementation confidence.

## 2. Existing Skill And Guidance Updates

- [x] 2.1 Broaden the Model-Miss Review skill description, first-read guidance, hard gates, minimum workflow, and agent prompt to cover non-trivial bug repairs.
- [x] 2.2 Update the Model-Miss Review protocol with a bug repair subsection that reuses Plan Intake false-negative fields, MTA, DPF, Architecture Reduction, LegacyPathDisposition, and Risk Ledger.
- [x] 2.3 Update the model-first kernel route map and AGENTS snippet guidance so bug fixes route through Existing Model Preflight and Model-Miss Review instead of direct implementation-only work.
- [x] 2.4 Update docs for Model-Test Alignment, DevelopmentProcessFlow, Closure Contract, and Risk Evidence Ledger to make the existing bug repair handoffs explicit.

## 3. Templates And Tests

- [x] 3.1 Update the Model-Miss Review public template notes and model comments to include prior claim, root-cause backpropagation, model-code-test binding, and legacy/fallback disposition prompts.
- [x] 3.2 Add or update skill-doc and public-template tests that protect the new bug repair wording without creating a new route.
- [x] 3.3 Add or update Plan Intake, Model-Test Alignment, Risk Evidence Ledger, and Closure Contract tests for the existing bug repair evidence chain.

## 4. Validation And Sync

- [x] 4.1 Run focused OpenSpec, template, skill-doc, Plan Intake, MTA, DPF, Risk Ledger, and closure tests.
- [x] 4.2 Run broader unit regression or launch long/background checks and collect final exit/result artifacts before claiming completion.
- [x] 4.3 Bump package/project version, update changelog/readme/version records, and run project audit/upgrade checks as needed.
- [x] 4.4 Sync editable install, installed Codex FlowGuard skills, active shadow workspace, local git source repository, and git commit/tag state.
- [x] 4.5 Record FlowGuard adoption evidence with commands, findings, skipped items, risk evidence, friction, and next actions.
