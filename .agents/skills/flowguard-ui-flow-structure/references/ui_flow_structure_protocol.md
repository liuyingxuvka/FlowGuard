# UI Flow Structure Protocol Index

Use `ui_flow_structure` only after classifying work as `greenfield`, `source_based`, or `mixed`. Greenfield work derives accepted capabilities from user/product scope. Source-based and mixed work additionally require source authority, target mapping, approved differences, source interaction semantics, and observed-source alignment.

Load only the directly routed protocol needed for the active claim:

- `ui_observed_surface_protocol.md`: existing/runnable visible-surface inventory and blindspots.
- `ui_capability_interaction_protocol.md`: capability/output contracts and UI event x UI state modeling.
- `ui_journey_structure_text_protocol.md`: launch-to-terminal journeys, regions, hierarchy, stable placement, and text blueprint.
- `ui_human_operability_protocol.md`: tasks, affordances, action grammar, dialogs, keyboard/focus, and walkthroughs.
- `ui_implementation_evidence_protocol.md`: functional chains, source semantics, click-through, screenshot, DOM text, and other evidence kinds.
- `ui_geometry_transition_protocol.md`: geometry, responsiveness, and transition coverage projection.

## Route sequence

1. Declare work mode and accepted UI boundary.
2. For an existing or runnable UI, complete Observed Visible Surface Review first; a disabled control is visible without a reason is a gap.
3. Inventory required user-visible capabilities and output contracts, then build the interaction model.
4. For complete app claims, review launch-to-terminal journeys before structure and text derivation.
5. For usable/human-operable claims, run the task and human-operability package.
6. For implemented/runnable/complete claims, require current click-through and evidence-kind rows; design/model evidence is insufficient.
7. Add geometry/responsiveness and transition projection only when those claims are in scope.

## Shared hard boundary

Every reachable enabled action needs a modeled event and either a complete control -> owner -> function -> UI update -> evidence chain, a valid pure-UI disposition, or an owned blindspot. Missing recovery/cancel/error branches remain explicit.

Source-based work preserves success, cancel, error, selected-value, no-handler, and external-effect semantics; greenfield work must not invent a source baseline.

Typography handoff stays semantic and calm: semantic hierarchy levels are not a command to create one size per level; text with similar jobs should reuse treatments; avoid a one-off visual text style without a named attention/meaning role.

Screenshot, DOM text, event traces, geometry, accessibility/ARIA, test results, and manual observation are evidence kinds only when tied to a current model/implementation revision and an evidence reference. Label/API existence alone is not functional proof.

The route returns evidence, failures, blockers, skipped checks, residual risk, claim boundary, and typed next actions. It does not replace visual design, final copywriting, frontend implementation, Code Structure Recommendation, StructureMesh, Model-Test Alignment, or TestMesh.
