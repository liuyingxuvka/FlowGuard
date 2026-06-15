## Why

FlowGuard's UI Flow Structure route already models UI states, controls,
journeys, structure, implementation validation, and text hierarchy, but the
route still treats several common UI quality risks as loose prose: what the user
actually sees, whether helper copy is useful, what kind of implementation
evidence was collected, and whether basic layout or interaction responsiveness
risks were checked.

This change upgrades those general UI route obligations without turning
project-specific rules into global policy. Screenshots remain a normal evidence
type; this change does not add a screenshot ban, and it does not add map,
canvas, or dense-layer specialty rules to the default route.

## What Changes

- Add first-class visible-surface review for user-facing controls, status text,
  helper copy, placeholders, metadata, and disabled-state reasons.
- Add implementation/render evidence typing so runnable UI completion can name
  whether evidence came from screenshot, browser click-through, DOM text,
  computed style, geometry, accessibility/ARIA, runtime trace/log, test result,
  or manual observation.
- Add focused geometry/layout evidence for universal UI risks such as text
  overflow, control overlap, viewport bounds, focus reachability, and scroll
  ownership.
- Add a lightweight responsiveness contract for hot-path feedback, cold-path
  work, stale-result guards, cancellation/coalescing, and stable region
  preservation.
- Update the UI Flow Structure compact and full templates so the compact starter
  remains short while still prompting for visible surface and evidence kind.
- Update FlowGuard UI route docs, public API docs, README routing summaries, and
  Codex skill prompts so agents understand the route's new obligations.
- Add regression tests for the new public helpers, templates, skills, docs, and
  API placement.
- No breaking changes are intended. Existing UI Flow Structure helpers and
  templates should keep their current entry points.

## Capabilities

### New Capabilities

- None. The new behavior extends existing UI Flow Structure capabilities rather
  than introducing a separate route.

### Modified Capabilities

- `flowguard-ui-flow-structure`: require the UI route to account for visible
  surface quality, implementation evidence kinds, geometry/layout evidence, and
  responsiveness contracts when those claims are in scope.
- `ui-implementation-validation`: require implementation validation evidence to
  declare evidence kind and keep screenshots as one allowed evidence type among
  other UI evidence modes.
- `ui-text-hierarchy-blueprint`: require helper copy, placeholders, status text,
  and disabled reasons to stay owned by state/region/control intent rather than
  competing with the primary task or duplicating labels without value.

## Impact

- `flowguard/ui_structure.py`: new data structures and review helpers for
  visible surface, render evidence, geometry/layout evidence, and
  responsiveness contracts.
- `flowguard/__init__.py` and `docs/api_surface.md`: expose the new helper
  surface in modeling/helper APIs without adding it to `CORE_API`.
- `flowguard/template_text/ui_flow_structure.py` and public template tests:
  update compact and full starter material.
- `.agents/skills/flowguard-ui-flow-structure/*`, `docs/ui_flow_structure.md`,
  `docs/agents_snippet.md`, and `README.md`: update route guidance and agent
  prompts.
- OpenSpec specs and focused tests for UI route behavior, skill docs, public
  templates, and API surface.
