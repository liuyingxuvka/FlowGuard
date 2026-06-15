## Why

FlowGuard currently has the ingredients for minimum valuable models, but public guidance and API surfaces still present direct `Explorer(...)` as a valid minimal entry. That lets thin, happy-path-only models count as FlowGuard work and weakens the product promise that FlowGuard catches the protected failure class before confidence is claimed.

## What Changes

- **BREAKING** Remove direct `Explorer(...)` from the formal AI/default FlowGuard entry path, public starter wording, and generated starter templates.
- **BREAKING** Require one unified formal entry: `RiskIntent` + `MinimumModelContract` + executable known-bad proof + template reuse/harvest closure + `FlowGuardCheckPlan`.
- **BREAKING** Treat missing minimum-model teeth as blocked or failed for formal FlowGuard claims instead of `pass_with_gaps`.
- Add structured known-bad proof records that bind each declared bad case to an observed failing/rejected model run, scenario, replay, or proof artifact.
- Update `run_model_first_checks(...)` so a formal model check cannot pass without risk intent, minimum contract, known-bad proof, and template closure.
- Update public templates, docs, Skill guidance, and API registry tests so the single hard entry is the only advertised route.
- Add migration/audit coverage that identifies old direct-Explorer models as upgrade-required rather than compatibility-supported.

## Capabilities

### New Capabilities
- `known-bad-proof-gate`: Structured evidence that declared known-bad cases are actually caught before FlowGuard confidence can pass.

### Modified Capabilities
- `minimum-valuable-model-entry`: Upgrade confidence gaps into hard blockers for formal FlowGuard claims and require executable known-bad proof.
- `model-first-function-flow`: Replace direct-Explorer and optional-runner language with a single hard minimum valuable model entry.
- `flowguard-api-registry`: Remove `Explorer` from the agent-default entry surface and expose the formal entry helpers instead.
- `flowguard-template-structure`: Update starter templates so they demonstrate the formal hard entry instead of direct Explorer usage.
- `risk-template-library`: Clarify that reusable template known-bad case names are declarations, while model instances still require executable proof.

## Impact

- Affected public API grouping: `AGENT_DEFAULT_API`, related API surface tests, and documentation.
- Affected helper layer: `RiskIntent`, `MinimumModelContract`, `FlowGuardCheckPlan`, `run_model_first_checks(...)`, audit/report sections, template harvest review.
- Affected generated artifacts: project template, risk-intent check-plan template, risk-template-library template, Skill model template assets, public docs.
- Affected tests: risk template review, risk plan serialization, runner summaries, public templates, API surface, model-hardening fixtures, and old direct-Explorer audit cases.
- Local rollout requires editable install sync, installed Skill sync, shadow/workspace sync, focused tests, FlowGuard model regressions, OpenSpec validation, and final project audit.
