## Why

FlowGuard already has the right AI-facing route families, summary reports,
maintenance obligations, maintenance scan, proof artifacts, and lifecycle
freshness helpers. The remaining friction is that AI agents still have to read
prompt prose and manually infer the next route, missing inputs, proof gaps, and
claim boundary after a run.

This change upgrades the existing FlowGuard workflow handoffs so agents can
follow structured next actions inside the existing route system instead of
inventing a parallel session runner or repeating manual route selection.

## What Changes

- Add structured AI action hints to FlowGuard finding ledger entries and
  maintenance obligations, including owner route, action kind, required inputs,
  proof gap codes, and claim impact.
- Add a SummaryReport-to-MaintenanceScan bridge so run results can become
  existing `MaintenanceScanPlan` inputs without agents manually rebuilding
  maintenance signals.
- Extend maintenance scan actions with structured next-route metadata while
  keeping the scan a thin router over existing specialist routes.
- Extend DevelopmentProcessFlow revalidation recommendations with route,
  proof-artifact, freshness-gap, and claim-scope metadata so agents can see the
  minimum rerun plan.
- Add a project-level ExistingModelPreflight helper that builds the existing
  preflight shape from `.flowguard`, docs, and OpenSpec inventory.
- Refresh compact AI-facing skill guidance, route-first docs, templates, tests,
  and FlowGuard self-model evidence for the upgraded handoff path.
- No new core model semantics, no new mandatory checklist, and no new parallel
  "session runner" route.

## Capabilities

### New Capabilities

- `maintenance-scan-router`: Formalizes and extends the existing maintenance
  scan helper contract for structured SummaryReport-to-route handoffs.

### Modified Capabilities

- `flowguard-ai-entry-simplification`: AI-facing hot paths must point agents to
  structured handoff outputs before manual route inference.
- `development-process-flow`: Revalidation recommendations must expose the
  minimum route/proof/freshness information needed for AI rerun decisions.
- `existing-model-preflight`: Existing-model grounding must provide a
  project-inventory helper that returns the existing preflight data shape.
- `flowguard-global-routing`: Route guidance must preserve the existing route
  map while making SummaryReport -> MaintenanceScan -> specialist handoff the
  normal AI continuation.

## Impact

- Public helper/report API: summary report, maintenance obligation,
  maintenance scan, development process flow, and existing-model preflight.
- API registry: route-scoped groups and public helper exports, without adding
  these helpers to the FlowGuard core API.
- Templates and docs: maintenance scan, development process flow, risk-intent,
  API surface docs, AGENTS snippet, and compact satellite skill shells.
- Evidence artifacts: FlowGuard self-models for maintenance scan, development
  process flow, existing-model preflight, and a small AI route handoff model.
- Tests: focused unit tests, API surface tests, skill-doc prompt budget tests,
  template CLI checks, OpenSpec strict validation, project audit, and practical
  regression.
