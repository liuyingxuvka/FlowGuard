## Context

FlowGuard UI already models visible surface, task coverage, human-operability, functional chains, implementation validation, geometry, and final done-claim evidence. The gap is upstream: the route can validate a target model that was copied from the wrong source understanding. A migration-specific interaction gate also leaked into generic skill prompts, public API names, risk gates, process evidence kinds, templates, and docs.

The upgrade must solve both issues without making the general UI skill depend on any one source technology. Some UI work is greenfield and has no legacy source. Some UI work is source-based and must preserve or deliberately change an existing UI, design, product spec, customer workflow, prototype, or other authority. Some work is mixed.

## Goals / Non-Goals

**Goals:**
- Add a generic UI work-mode model: `greenfield`, `source_based`, and `mixed`.
- Add generic source-baseline models for source-based UI work: source surfaces, regions, items, interactions, task frames, target mapping, difference dispositions, and observed alignment.
- Replace generic public names that include one specific source technology with generic source-baseline interaction names.
- Keep the no-fallback rule: old public names are removed rather than kept as aliases.
- Update FlowGuard skills, templates, OpenSpec specs, docs, tests, installed copies, editable install, shadow workspace, and version metadata together.

**Non-Goals:**
- Do not build parser adapters for every possible source. Source evidence can be structured from any authority by the calling agent or project.
- Do not require source-baseline gates for true greenfield UI work.
- Do not claim automatic human signoff for native dialogs, inaccessible legacy applications, or manually observed sources.
- Do not preserve compatibility aliases for the old source-specific public API names.

## Decisions

1. Use generic model names and generic interaction kinds.

   Replace source-specific names with `UISourceInteractionSemantics`, `UISourceBaselineInteractionGate`, `UISourceBaselineInteractionReport`, and `review_ui_source_baseline_interactions(...)`. Interaction kinds become `file_picker`, `directory_picker`, `external_open`, `save_dialog`, `custom_dialog`, `no_handler`, `navigation`, and `command`.

   Alternative considered: keep old names and add generic aliases. Rejected because this repository's replacement rule says obsolete wrappers and aliases should be removed unless compatibility is explicitly requested.

2. Add source-baseline models beside, not inside, observed-surface models.

   `UIObservedSurfaceInventory` still describes the running UI. New source-baseline objects describe the authoritative source. `UITargetSourceMapping` bridges source to target. `UIObservedSourceAlignment` compares the observed UI against the target and approved mapping. This avoids mixing "what existed before" with "what is currently rendered".

   Alternative considered: put source ids directly on existing `UIControl` and `UIVisibleSurfaceItem`. Rejected because greenfield UI would inherit irrelevant fields and source-based UI would still lack a complete difference ledger.

3. Work mode is the first routing decision.

   A UI change must classify its work mode before source-baseline gates apply. Greenfield UI requires product/user-task intent and target rationale, not source evidence. Source-based UI requires source-baseline and difference disposition evidence. Mixed UI requires both paths for their respective scope.

   Alternative considered: make source-baseline optional metadata. Rejected because that repeats the prior failure mode where target models can be self-consistent but source-wrong.

4. Difference dispositions are explicit and finite.

   Source-to-target mapping uses a small disposition set: `preserve`, `move`, `rename`, `merge`, `split`, `replace`, `hide`, `delete`, `defer`, and `new`. Anything that changes, hides, deletes, replaces, or adds behavior needs rationale and approval/evidence.

   Alternative considered: free-form migration notes. Rejected because free-form notes are hard to test and easy for AI agents to overclaim.

5. General skills must not hard-code source technology names.

   The generic FlowGuard UI route should talk about source authorities, source-based work, legacy/prototype/design/product-spec baselines, and external/native interactions. Specific source adapters can exist elsewhere later, but not as hard gates in the generic skill.

## Risks / Trade-offs

- [Risk] Breaking public API names can disrupt downstream callers. -> Mitigation: bump to `0.47.0`, update API docs/templates/tests, and let failures expose stale callers instead of silently supporting old aliases.
- [Risk] Source-baseline modeling can feel heavy for simple UI work. -> Mitigation: work mode lets greenfield and small scoped UI tasks skip source-baseline with an explicit reason.
- [Risk] A generic source model may be too abstract for some source types. -> Mitigation: keep source evidence as structured rows with `source_type` and `evidence_ref`, and allow later optional adapters without changing the core route.
- [Risk] Historical logs still mention the removed source-specific names. -> Mitigation: leave historical changelog/adoption log entries alone, but scrub active docs, skills, templates, tests, and public APIs.

## Migration Plan

1. Add generic source-baseline dataclasses, review helpers, constants, and tests.
2. Replace public exports and internal users of the old source-specific names.
3. Update development-process and risk-ledger constants and freshness/finding strings.
4. Update templates, docs, OpenSpec current specs, and installed Codex skills.
5. Update version metadata to `0.47.0`.
6. Run focused UI/process/risk/API/template tests, OpenSpec strict validation, full regression, editable install, project audit, installed-skill sync, and shadow workspace verification.

## Open Questions

- None for this implementation pass. Future source-specific adapters can be proposed separately if users ask for them.
