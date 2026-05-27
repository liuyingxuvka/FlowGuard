## Why

Workflow-heavy UI work can have a complete interaction structure and still fail
visually because the words on the screen have no hierarchy. Agents need a
public FlowGuard route for turning modeled UI intent into a text hierarchy
blueprint before copy, layout, or implementation turns every label, heading,
status, warning, and helper note into competing prose.

UI Flow Structure already derives controls, regions, overlays, and stable
placement from a UI interaction model. The missing sibling layer is text
hierarchy: which messages are primary, which are secondary, which are local
labels or affordances, which are blocking warnings, which duplicate existing
meaning, and which should be shortened, grouped, hidden, or escalated.

## What Changes

- Add a UI Text Hierarchy Blueprint capability for model-first review of
  interface wording, text roles, priority, density, duplication, state scope,
  and blocking/assistive text.
- Position the route as a companion to UI Flow Structure: UI Flow Structure
  owns interaction topology and placement; UI Text Hierarchy Blueprint owns the
  hierarchy and state ownership of visible text inside that topology.
- Add OpenSpec requirements for text role inventory, state-scoped ownership,
  primary/secondary priority, duplicate text checks, warning/error escalation,
  empty/loading/success/failure states, and handoff to copywriting or frontend
  design.
- Add package helpers, template coverage, skill guidance, README, changelog,
  and product architecture docs for the `v0.16.0` release while preserving the
  existing `v0.15.0` UI Flow Structure material.

## Capabilities

### New Capabilities

- `ui-text-hierarchy-blueprint`: FlowGuard can review a UI text inventory and
  produce a blueprint that ranks headings, labels, helper text, status text,
  empty-state text, warning/error text, CTA text, and secondary explanatory
  copy by state, region, role, semantic key, and typography-token priority.

### Modified Capabilities

- `flowguard-ui-flow-structure`: Documentation now describes UI Text Hierarchy
  Blueprint as a follow-on or sibling route, not a replacement for interaction
  modeling, region derivation, or visual design.

## Impact

- Affected public documentation: README, CHANGELOG, and product architecture.
- Affected package helpers: `flowguard.ui_structure`,
  `flowguard.__init__`, and `flowguard.templates`.
- Affected tests: UI structure, API surface, public templates, and skill docs.
- Affected OpenSpec artifacts under
  `openspec/changes/add-ui-text-hierarchy/`.
