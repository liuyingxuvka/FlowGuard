## Context

The previous 0.36.0 work split large template text, added grouped API discovery,
and expanded Model Similarity Consolidation into the right maintenance route.
The remaining problem is shape, not capability: agents still see a 29-field
`ModelSignature`, downstream routes repeat several similarity id fields, and
docs still mention the flat `MODELING_HELPER_API` index prominently enough that
it can become the first-read surface.

The user explicitly allowed removal of compatibility fields when they make the
system harder to understand. This change therefore prefers a clean replacement
over additive compatibility for redundant similarity handoff fields.

## Goals / Non-Goals

**Goals:**

- Keep Model Similarity Consolidation as the single route for similar A/B/C
  workflow maintenance, test obligations, code obligations, and false-friend
  quarantine.
- Add small constructor/profile helpers for common model-family and changed
  member reviews.
- Replace repeated downstream similarity id fields with one typed
  `SimilarityHandoff`.
- Keep full dataclasses available for advanced callers, but document them as the
  full path rather than the basic path.
- Update tests and templates so the new, clean path is the taught path.
- Bump local version and synchronize source checkout, editable install, shadow
  workspace, FlowGuard records, and local git.

**Non-Goals:**

- Do not add a new similarity-audit capability or route.
- Do not remove the maintenance-group, change-impact, test-obligation,
  code-obligation, downstream-route, or false-friend safety behavior.
- Do not preserve old repeated similarity id fields solely for compatibility.
- Do not publish a remote release.

## Decisions

1. **Use a typed handoff instead of repeated id fields.**
   Downstream routes need the same similarity provenance, but scattered fields
   force agents to remember which ids belong to which route. A single handoff
   object lets the report produce one transferable bundle and each downstream
   route read only the parts it owns.

   Alternative considered: keep old fields and add the handoff as a parallel
   option. This was rejected because it makes the AI-facing surface larger and
   keeps the exact confusion this change is meant to remove.

2. **Add helpers, not a second capability.**
   `model_signature_minimal()`, `model_signature_maintenance()`, and
   `model_similarity_plan_for_changed_member()` construct existing full-schema
   objects. They reduce routine field pressure without forking the model.

3. **Make docs route-first and tiered.**
   The first path is route group -> profile helper -> handoff -> downstream
   route. The full schema and flat helper inventory remain documented, but only
   after the basic path.

4. **Treat field cleanup as a breaking but intentional 0.x change.**
   FlowGuard is still pre-1.0. The cleaner structure is more valuable than
   preserving every intermediate compatibility field. Tests will be updated to
   prove the new surface, not both old and new surfaces.

## Risks / Trade-offs

- **Risk: callers using old scalar fields break.** -> Mitigation: document the
  breaking cleanup in changelog and version the local package as 0.37.0.
- **Risk: the handoff hides route-specific obligations.** -> Mitigation: keep
  explicit `SimilarityHandoff` fields for relations, groups, impacts, tests,
  code, impacted models, and false-friend rationales; downstream tests cover
  each route.
- **Risk: helpers under-specify complex cases.** -> Mitigation: helpers return
  full dataclasses and the full-schema path remains available.
- **Risk: background regression becomes stale after final edits.** ->
  Mitigation: rerun focused tests after final edits and inspect full regression
  final artifacts before claiming done.

## Migration Plan

1. Add OpenSpec delta specs and a FlowGuard self-model for the AI-surface
   streamlining behavior.
2. Add `SimilarityHandoff`, report conversion, and lightweight constructors in
   the existing model-similarity module.
3. Replace downstream repeated similarity id fields with `similarity_handoff`.
4. Update public exports, route API groups, templates, docs, and tests.
5. Run OpenSpec, self-model, focused tests, full regression, project audit,
   editable install check, shadow sync/verification, adoption logging, KB
   postflight, commit, and local tag.

## Open Questions

- None. The user approved removal of compatibility fields that keep FlowGuard
  unnecessarily bulky.
