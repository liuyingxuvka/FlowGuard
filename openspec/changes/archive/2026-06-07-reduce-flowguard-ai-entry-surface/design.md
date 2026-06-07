## Context

The v0.41.7 field cleanup removed or merged several heavy field shapes, but the
AI-facing entry points still expose broad helper lists and deep templates too
early. The target behavior is not to remove FlowGuard's full machinery; it is to
make the default path small enough that an agent can start with the correct
route and only expand when evidence demands it.

## Decisions

### Route starter API

Add `ROUTE_STARTER_API` as a mapping from route id to compact helper names. Each
route starter should contain only the names needed to start that route: a review
function, the primary plan/report rows, and a template factory when useful.

Keep existing full groups such as `MODELING_HELPER_API`,
`REPORTING_HELPER_API`, and `FLOWGUARD_ROUTE_API`, but move them behind a
documented full path. Add `ROUTE_ADVANCED_API` so a consumer can still find the
full route group without scanning `__all__`.

`API_SURFACE` should expose both starter and full surfaces:

- `agent_default`
- `route_starters`
- `route_advanced`
- `core`
- `modeling_helpers_full`
- `reporting_helpers_full`
- `evidence`

### Compact templates by default

The existing `model-miss-template`, `model-test-alignment-template`, and
`ui-flow-structure-template` commands should produce compact runnable examples.
Their compact examples must preserve the safety gates that matter:

- model miss: root-cause backpropagation, same-class evidence, owner code
  contract binding, validation after refinement;
- model-test alignment: obligation, owner code contract, test evidence,
  negative or stale evidence, and replay/check mention;
- UI flow structure: states, visible controls, transitions, one journey,
  implementation validation, and visible hierarchy evidence.

The previous deep templates remain available through full-template factories and
CLI commands:

- `model-miss-full-template`
- `model-test-alignment-full-template`
- `ui-flow-structure-full-template`

### Field inventory tiering

Do not delete more runtime fields in this change. Instead, extend the generated
field inventory with AI-surface tier metadata:

- `starter`: field is suitable for default AI entry examples.
- `advanced`: field belongs to a named route escalation.
- `internal`: field is implementation, metadata, or deep maintenance detail.

This makes the next deletion pass evidence-driven instead of another broad
manual pruning pass.

### FlowGuard self-check

Add `.flowguard/ai_entry_surface_reduction/` with a small model and runner. The
model should reject the main future regressions:

- default path uses full helper inventories first;
- compact templates drop gate/test/replay evidence;
- compact templates exceed a bounded line budget;
- full path is not discoverable;
- OpenSpec/validation/sync evidence is missing before closure.

## Risks

- Making defaults compact can hide advanced obligations. Mitigation: compact
  notes must name escalation triggers and full-template commands.
- Keeping full templates in source while defaulting to compact may look less
  aggressive than deletion. Mitigation: the behavioral win is at the generated
  template and API level; source relocation can be a later structure-only pass.
- Public exports are broad today. Mitigation: this change adds layered
  discovery without breaking existing imports.

## Validation

- `openspec validate reduce-flowguard-ai-entry-surface --strict`
- `.flowguard/ai_entry_surface_reduction/run_checks.py`
- `python -m unittest tests.test_api_surface tests.test_public_templates -v`
- `python -m unittest discover -s tests -p "test_*.py"`
- `python scripts/run_flowguard_model_regressions.py --json --tail-lines 10`
- `python scripts/generate_field_lifecycle_inventory.py --root . --output docs/field_lifecycle_inventory.md`
- Editable install, project audit, formal repository sync, and git evidence
