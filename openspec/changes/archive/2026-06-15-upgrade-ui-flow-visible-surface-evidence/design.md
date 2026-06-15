## Context

The current UI Flow Structure route already covers model-first UI behavior:
states, controls, transitions, journey coverage, structure derivation,
implementation validation, text hierarchy, transition projection, and stale
evidence checks. The missing pieces are not a new UI route. They are small
public helper surfaces for concerns that appear in ordinary UI work but are
currently recorded only as prose:

- the user-visible surface and whether each visible item has a useful purpose;
- the type of implementation evidence supporting runnable UI completion;
- universal geometry/layout evidence such as overflow, overlap, bounds, focus,
  and scroll ownership;
- responsiveness contracts that keep immediate user feedback separate from
  heavy cold-path work.

The route should remain general. Screenshots are normal UI evidence. The design
does not introduce screenshot restrictions and does not add specialty
map/canvas/dense-layer rules to the default route.

## Goals / Non-Goals

**Goals:**

- Add public dataclasses and review helpers in `flowguard.ui_structure` for
  visible-surface review, render/implementation evidence typing,
  geometry/layout evidence, and responsiveness contracts.
- Keep existing UI Flow Structure entry points compatible.
- Keep the compact template compact while adding a small visible-surface and
  evidence-kind prompt.
- Put new helpers in the modeling/helper API surface, not `CORE_API`.
- Update OpenSpec specs, docs, templates, and Codex skill prompts so agents know
  to model visible surface and evidence before claiming a UI is complete.
- Add tests for good and bad examples.

**Non-Goals:**

- No global screenshot ban or screenshot downgrade.
- No map/canvas/LOD/z-index/legend/hit-test specialty profile in this change.
- No final visual-design or copywriting workflow.
- No new standalone UI skill or route.
- No dependency changes.

## Decisions

1. **Extend `ui_structure.py` rather than adding a new module.**

   The new concepts are route-local and share `UIFlowStructureFinding` and the
   existing report pattern. Keeping them in `ui_structure.py` avoids a second UI
   route surface.

2. **Use separate helper surfaces instead of bloating existing core rows.**

   `UIImplementationStepEvidence` already models event-step evidence. A
   separate `UIRenderEvidence` can express evidence kind and evidence target
   without turning every click step into a catch-all render audit row.

3. **Keep visible surface independent from final copy/design.**

   Visible-surface review checks ownership, purpose, internal terminology,
   disabled reasons, placeholders, metadata, and helper-copy value. It does not
   decide final wording, brand tone, or art direction.

4. **Keep geometry evidence universal.**

   Geometry/layout review checks text overflow, overlap, viewport/dialog bounds,
   focus reachability, keyboard reachability, and scroll owner. Specialty
   surfaces can be modeled later if a future change needs them.

5. **Treat screenshots as ordinary evidence.**

   Screenshot evidence should be accepted when declared as a screenshot kind.
   Other evidence kinds remain useful because screenshots alone do not prove
   every interaction, DOM, accessibility, stale-result, or test claim.

## Risks / Trade-offs

- **Risk: helper surface becomes too verbose** -> Mitigation: keep compact
  template small and put full examples only in the full template and docs.
- **Risk: visible-surface checks become copywriting enforcement** -> Mitigation:
  restrict checks to ownership, purpose, internal terminology, duplication, and
  disabled/placeholder clarity.
- **Risk: evidence-kind validation becomes too strict** -> Mitigation: require
  at least one recognized evidence kind for implementation/render evidence but
  do not require every possible evidence kind.
- **Risk: compatibility drift in public API** -> Mitigation: add helpers to
  `MODELING_HELPER_API` and `__all__`, and explicitly assert they are not in
  `CORE_API`.
