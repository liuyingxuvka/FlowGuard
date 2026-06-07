## Why

FlowGuard now has enough route, field, template, and evidence machinery that AI
agents can accidentally read the whole public surface and over-model routine
work. The next upgrade should make the default AI path small and route-first
while keeping the full machinery available for explicit deep maintenance.

## What Changes

- Add route starter API groups that expose compact per-route entry points before
  full helper inventories.
- Keep full route and helper APIs available, but document them as advanced/full
  paths instead of first-read guidance.
- Make the model-miss, model-test-alignment, and UI-flow template commands emit
  compact defaults.
- Add explicit full-template commands for the deep versions of those routes.
- Add tests that fail when starter API groups or compact templates grow back
  into full inventories.
- Update API docs, FlowGuard guidance, and adoption records so AI agents load
  starter surfaces first and escalate only when the task requires it.
- Add a FlowGuard self-check model for this AI-entry reduction so the project can
  validate that compact defaults preserve gate, test, replay, and full-path
  escalation evidence.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `flowguard-ai-entry-simplification`: require starter/full layering for AI
  entry paths and preserve gate/test/replay evidence in compact defaults.
- `flowguard-api-registry`: require route starter API groups and advanced/full
  paths behind them.
- `flowguard-template-structure`: require compact default templates plus
  explicit full-template commands for deep route scaffolds.
- `flowguard-field-prompt-reduction`: classify field inventory rows by AI
  surface tier so later field deletion can distinguish starter, advanced, and
  internal fields.

## Impact

- `flowguard/__init__.py`
- `flowguard/templates.py`
- `flowguard/__main__.py`
- `flowguard/template_text/model_miss_review.py`
- `flowguard/template_text/model_test_alignment.py`
- `flowguard/template_text/ui_flow_structure.py`
- `tests/test_api_surface.py`
- `tests/test_public_templates.py`
- `scripts/generate_field_lifecycle_inventory.py`
- `docs/api_surface.md`
- FlowGuard skill guidance in `.agents/skills/**/SKILL.md`
- OpenSpec artifacts, adoption logs, version metadata, and local sync evidence
