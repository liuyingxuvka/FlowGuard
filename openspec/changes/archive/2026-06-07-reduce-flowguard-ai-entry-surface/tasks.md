## 1. OpenSpec and FlowGuard model

- [x] 1.1 Archive the completed field-schema cleanup change without replaying stale spec deltas.
- [x] 1.2 Add this change's proposal, design, spec deltas, and task list.
- [x] 1.3 Add `.flowguard/ai_entry_surface_reduction/model.py`.
- [x] 1.4 Add `.flowguard/ai_entry_surface_reduction/run_checks.py`.
- [x] 1.5 Validate the new OpenSpec change and self-check model.

## 2. API starter surface

- [x] 2.1 Add compact route starter groups in `flowguard/__init__.py`.
- [x] 2.2 Add route advanced/full group mapping without removing existing public imports.
- [x] 2.3 Split PlanIntake first-read exposure from the full `__all__` route group.
- [x] 2.4 Update `API_SURFACE` and public supplement exports.
- [x] 2.5 Add tests for starter group budgets and full-surface separation.

## 3. Compact and full templates

- [x] 3.1 Make model-miss default template compact and runnable.
- [x] 3.2 Make model-test-alignment default template compact and runnable.
- [x] 3.3 Make UI-flow-structure default template compact and runnable.
- [x] 3.4 Add full-template factories for the previous deep template bodies.
- [x] 3.5 Add CLI commands for the full templates.
- [x] 3.6 Update template tests for compact budgets, required gates, and full-template availability.

## 4. Docs, skills, and field inventory

- [x] 4.1 Update `docs/api_surface.md` so route starter discovery appears before full helper indexes.
- [x] 4.2 Update affected FlowGuard skill prompts to load starter API/templates first.
- [x] 4.3 Add AI-surface tier columns to generated field lifecycle inventory.
- [x] 4.4 Regenerate `docs/field_lifecycle_inventory.md`.
- [x] 4.5 Update adoption log entries for this maintenance run.

## 5. Version, validation, sync

- [x] 5.1 Bump package/docs version for the local upgrade.
- [x] 5.2 Run focused API/template tests.
- [x] 5.3 Run full unittest discovery.
- [x] 5.4 Run aggregate FlowGuard model regressions.
- [x] 5.5 Install editable package and re-run project audit.
- [x] 5.6 Sync the formal local git repository without deleting peer-only files.
- [x] 5.7 Verify formal repo status, commit, and tag the local version when validation passes.
