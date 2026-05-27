## Context

FlowGuard's public UI route currently starts with UI behavior: controls,
events, states, transitions, failures, recovery paths, availability, and then
model-derived structure. That solves where UI functions belong, but it does
not decide how visible text competes for attention once those regions exist.

The UI Text Hierarchy Blueprint capability should give agents a structured way
to review UI wording before implementation. It is intentionally not a
copywriting generator. It is a hierarchy and ownership review: every visible
text item should have a role, state scope, region owner, priority, redundancy
rationale when duplicated, and escalation behavior when it blocks or warns.

## Goals / Non-Goals

**Goals:**

- Inventory visible UI text by state, region, and role.
- Rank text into primary, secondary, tertiary, local affordance, helper,
  status, warning, error, empty-state, loading, and success/failure roles.
- Detect competing primary messages, duplicated semantic text, orphan helper
  text, stale state-specific text, and warning/error text that is hidden at the
  wrong hierarchy level.
- Preserve accessible and assistive wording as first-class text roles rather
  than treating it as incidental copy.
- Hand a concise blueprint to visual design, frontend implementation, or
  copywriting after hierarchy and ownership are clear.

**Non-Goals:**

- Do not generate final marketing copy, brand voice, or localization.
- Do not replace UI Flow Structure's interaction model or structure derivation.
- Do not claim browser, accessibility, or frontend implementation validation
  from a text hierarchy blueprint alone.
- Do not require this route for tiny label edits with no state, warning,
  density, or hierarchy risk.

## Decisions

### Treat text hierarchy as a UI sibling route

UI Text Hierarchy Blueprint should be documented next to UI Flow Structure
because both operate before frontend execution. UI Flow Structure answers what
the interface can do and where behavior belongs. UI Text Hierarchy Blueprint
answers what the interface says, where each message belongs, and which message
is allowed to dominate attention in each state.

Alternative considered: fold text hierarchy into UI Flow Structure. That would
make the UI route too broad and risks hiding text-density failures behind a
passed interaction model.

### Require state ownership for text

Text hierarchy is stateful. A status line, recovery hint, empty-state prompt,
or destructive warning can be correct in one state and misleading in another.
The blueprint should therefore bind text items to UI states and region owners,
not only to screens.

Alternative considered: review copy as a flat page inventory. That catches
some duplication but misses stale state messages and misplaced warnings.

### Keep output as a blueprint

The public artifact should be a concise blueprint: role inventory, priority
ladder, state ownership, duplication decisions, escalation rules, and handoff
notes. It should not become a visual comp or final copy deck.

## Risks / Trade-offs

- **Over-modeling simple copy edits** -> Route guidance should keep small
  visual-only or label-only changes out of scope.
- **Confusing hierarchy with copywriting** -> Public docs should state that the
  blueprint constrains structure and priority, while final voice and exact
  wording may happen later.
- **Accessibility overclaim** -> The blueprint may preserve assistive text
  roles, but it does not replace accessibility testing.
- **API surface growth** -> Keep the helper objects small and aligned with the
  existing UI Flow Structure dataclass/reviewer style.

## Migration Plan

1. Publish the OpenSpec proposal, design, requirement spec, and task list.
2. Add `UITextHierarchyBlueprint`, `UITextElement`, `UITypographyToken`,
   `UITextHierarchyReport`, and `review_ui_text_hierarchy(...)` without
   weakening UI Flow Structure.
3. Update the UI Flow Structure template, skill route wording, README,
   CHANGELOG, and product architecture docs.
4. Validate with OpenSpec strict validation, focused tests, public template
   execution, and docs checks before release claims.
