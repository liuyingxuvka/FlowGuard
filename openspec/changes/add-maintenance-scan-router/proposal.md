## Why

FlowGuard-managed projects can declare adoption without giving agents a small functional way to find model/code/test/structure maintenance debt after a change. This change adds a thin maintenance scan that routes agents to existing specialist FlowGuard capabilities instead of expanding AGENTS.md or skill prompts into long checklists.

## What Changes

- Add a maintenance scan/router helper that turns changed artifacts, observed evidence, and claim scope into required or suggested maintenance actions.
- Route model/code/test mismatch, stale evidence, skipped candidate skills, architecture reduction, code split, model mesh, and test mesh needs to existing FlowGuard routes.
- Keep the scan lightweight: it does not run tests, split code, split models, or replace the owning route.
- Add a small CLI/template/docs surface so agents can discover and use the scan without prompt bloat.
- Update adoption/global routing guidance to treat FlowGuard project adoption as a trigger for the scan, not as validation evidence.

## Capabilities

### New Capabilities
- `maintenance-scan-router`: Reviews project-change maintenance signals and recommends required/suggested FlowGuard maintenance routes.

### Modified Capabilities
- `flowguard-global-routing`: Adds the maintenance scan as the thin default entry for FlowGuard-managed project work before broad completion claims.

## Impact

- Public helper API and route registry.
- CLI/template command surface.
- FlowGuard docs, AGENTS snippet, and adoption guidance.
- Tests for scan decisions, API exposure, and template/CLI behavior.
