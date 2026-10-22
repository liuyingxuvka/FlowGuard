# UI Flow
Tree operation: Review a UI journey behavior node.
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.
Catches UI flows that look done but are not. A visible, enabled button with no
event, a state the user cannot leave, a failure screen with no recovery, an
internal field shown to users, a details panel that is open by default or
cannot be closed, a journey that never reaches success. The UI is a state
machine: UI event x UI state -> output and next state. Example: "Export" is
enabled in the empty state but no transition handles it -> `unmodeled_control_event`.
## Use when

- You add or change screens, dialogs, panels, controls or user journeys.
- You decide what content is shown, shown on demand, or kept internal.
- A bug was a dead button, a stuck state, or leaked internal text.
- You claim a runnable UI works and need click-to-result evidence.

## Do not use when

- The risk is a payload or config field changing: use field lifecycle.
- Backend ordering, retries or side effects: use a state/workflow model.
- You only restyle (colors, spacing) with no state, content or control change.

## Inputs

- `python -m flowguard read --find <screen words>`, then
  `python -m flowguard read --component <id>`: read `files`, `entrypoints`,
  `state`, `side_effects`, `tests`, `models`.
- From the code: states (empty, loading, failed, ...), controls per state
  (visible/enabled/disabled/hidden), events, handlers, displays, shown fields.
- For a runnable claim: the real inventory of what renders, and a test that
  clicks through it.

## Steps

1. If a new boundary needs a scaffold: `python -m flowguard template ui-flow-structure --write .`
   It writes one contract model, `.flowguard/models/ui_flow_structure.py`: `ui_journey_explorer(model)`
   explores every control sequence (the interaction reviewer is one of its invariants, with "every reached
   state is declared", "an enabled control leads somewhere" and "no dead end"), a broken variant opens an
   unknown state, and `conformance()` returns `ui_flow_code_facts(model, UI_FILES, anchors=IMPLEMENTED_BY)`
   (every control id is in the UI source, every handler exists). Its `REPLACE_ME` paths (UI files, handlers and the test) fail until they name
   your UI files. The other UI reviews (step 3) are called directly on the same model.
2. Reuse/update the owner's UI model; replace template fixtures only if step 1 needed a scaffold. Core records (`from flowguard import ...`):
   - `UIInteractionModel(model_id, initial_state_id, states=, controls=, transitions=, displays=, validation_boundaries=, rationale=)`
   - `UIStateNode(state_id, visible_controls=, enabled_controls=, disabled_controls=, hidden_controls=, recovery_controls=, terminal=, failure=, visible_displays=, hidden_displays=)`
   - `UIControl(control_id, label=, control_type=, level=, destructive=, function_key=)`
   - `UITransition(event_id, control_id, source_state_id, target_state_id, output=, side_effects=, rationale=)`
   - `UIJourneyCoverage(coverage_id, source_interaction_model_id, launch_state_id, entry_points=, feature_journeys=)`
     with `UIFeatureJourney(feature_id, entry_point_ids=, required_event_ids=, success_terminal_state_ids=, recovery_event_ids=)`.
   - `UIContentVisibilityPlan(plan_id, candidate_content_ids=, items=)` with
     `UIContentVisibilityItem(content_id, visibility_class=, user_need_refs=, reveal_event_ids=, dismiss_event_ids=, keyboard_focus_event_ids=)`.
     `visibility_class` is `user_visible`, `user_on_demand` or `internal`.
     `ui_content_visibility_candidate_ids_from_field_lifecycle(...)` takes candidates from a field-lifecycle plan.
3. Pick the reviews you need. Each returns a report with `.ok` and `.findings` (`.code`).

| Review | Question it answers |
|---|---|
| `review_ui_interaction_model` | Are states, controls, transitions complete and consistent? |
| `review_ui_journey_coverage(cov, interaction_model=m)` | Does every journey reach a success terminal from launch; does every reachable enabled control have an event? |
| `review_ui_content_visibility(plan, interaction_model=m)` | Is each content item classified; internal never shown; on-demand hidden until revealed and closable? |
| `review_ui_visible_surface` / `review_ui_observed_surface_inventory` | Is every visible or really rendered item mapped to the model or a blindspot? |
| `review_ui_control_functional_chains(chains, observed_inventory=inv)` | Does each enabled control reach event -> code owner -> function -> UI update? |
| `review_ui_functional_capability_coverage` | Does every user capability have a UI route? |
| `review_ui_human_operability` | Can a user find, understand and operate the task controls? |
| `review_ui_implementation_validation` | Do real journey runs match the model; complete or scoped claim? |
| `review_ui_render_evidence` / `review_ui_geometry_layout_evidence` / `review_ui_responsiveness_contract` / `review_ui_structure_derivation` / `review_ui_text_hierarchy` | Rendered, laid out, keyboard-reachable, hot-path feedback; regions and text roles follow the model? |
| `review_ui_product_consistency` | Do surfaces with one intent reuse the same grammar and typography? |
| `review_ui_source_baseline_interactions` / `review_ui_source_baseline_alignment` | For source-based work, is the old UI's behavior kept or mapped? |

4. In the selected native review/owner, keep relevant good/bad assertions; any persistent runner
   returns 0 only if good reports pass and relevant broken reports fail.
5. Its components come from `IMPLEMENTED_BY`; add `COMPONENTS` or `PARENT` only to place it elsewhere.
   Run `python -m flowguard map models ui_flow_structure`.
6. Run `python -m flowguard change`; execute selected checks not already current, rerunning affected checks after edits.

## What blocks

| Code | Meaning |
|---|---|
| `unmodeled_control_event` | An actionable control has no transition at all. |
| `visible_control_without_modeled_event` | A reachable state shows an enabled control with no event there and no blindspot. |
| `missing_failure_recovery` | A non-terminal failure state has no recovery control or way out. |
| `missing_feature_success_terminal` | A journey has no success terminal state. |
| `feature_state_unreachable_from_launch` | A journey needs a state that launch cannot reach. |
| `internal_content_mapped_to_ui` | Internal content is mapped to a display, text or visible item. |
| `unclassified_ui_candidate_content` | A candidate content item has no visibility row. |
| `on_demand_content_visible_in_default_state` | On-demand content is visible before a reveal event. |
| `on_demand_content_missing_dismiss_event` | On-demand content can be opened but not closed. |
| `hover_reveal_missing_keyboard_focus_equivalent` | Hover-only reveal with no keyboard/focus path. |
| `observed_visible_item_unmapped` | A really rendered item maps to no control, display or blindspot. |
| `enabled_control_missing_functional_chain` | An observed enabled control has no click-to-result chain. |


## Risk-specific regression examples

- Dead button: `export` enabled in `empty`, no `UITransition` -> `unmodeled_control_event`.
- Leak: an `internal` item (e.g. `debug_run_id`) mapped to a display -> `internal_content_mapped_to_ui`.
- Sticky panel: `user_on_demand` details visible in the initial state, no
  `dismiss_event_ids` -> `on_demand_content_visible_in_default_state`, `on_demand_content_missing_dismiss_event`.

## Done when

- [ ] The selected native UI reviews/existing-owner checks pass; any persistent runner is registered and run once.
- [ ] Relevant broken fixtures fail with their expected code (assert the code, not only `not ok`).
- [ ] Real UI tests (click-through or component tests) are in the component's `tests`.
- [ ] `python -m flowguard change` is clean.
- [ ] Report which reviews ran, which evidence classes were omitted (scoped claim), and what was skipped.

## Limits

- It checks the rows you declare. It does not render or click the UI. Only
  real UI tests show runtime behavior.
- One event cannot have several outcomes: a reused `event_id` gives
  `duplicate_event_id`. Model each outcome as its own event (`load_ok`, `load_failed`).
- `ui_journey_explorer` runs the interaction model in the core explorer; the other reviews check
  declarations only. `ui_flow_code_facts` reads the UI source; nothing is rendered. Pair the model with
  real UI tests.
