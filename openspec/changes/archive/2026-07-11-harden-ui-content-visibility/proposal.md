## Why

FlowGuard currently reviews UI content after it has already been selected for display, but it does not require a prior decision that the content belongs on an ordinary user surface. As a result, internal audit, model, test, routing, evidence, or diagnostic fields can be mapped to displays and text elements even when users do not need them.

## What Changes

- Add one small UI content-admission contract with three executable values: `user_visible`, `user_on_demand`, and `internal`. The first two are ordinary user-facing content; this change does not introduce user-role or permission taxonomies.
- Require every in-scope UI candidate content item to have exactly one visibility classification before it can enter display, text, visible-surface, or observed-surface modeling.
- Require `user_visible` content to identify a real user task, state, recovery, or safety need.
- Require `user_on_demand` content to be hidden by default and revealed only by an explicit click, expand, or hover action with a keyboard/focus equivalent and a close or collapse path.
- Prohibit `internal` and unclassified content from mapping to ordinary visible UI.
- Keep ordinary task-owned controls and their normal labels outside the extra content ledger; apply the contract to displayed values, status/helper/metadata content, non-action labels, optional details, and other content that can expose system state.
- Extend the existing UI Flow Structure owner, real-surface validation model, behavior commitment ledger, compact/full templates, skill prompts, documentation, and tests. Do not create a parallel UI disclosure skill.
- Preserve constructor compatibility with empty defaults, while preventing legacy unclassified content from supporting a broad or complete UI claim.

## Capabilities

### New Capabilities

None. Content admission remains part of the existing `flowguard-ui-flow-structure` route.

### Modified Capabilities

- `flowguard-ui-flow-structure`: require pre-display content classification, user-need ownership, default-hidden on-demand state behavior, and no internal-content UI mapping.
- `ui-text-hierarchy-blueprint`: consume only approved user-facing content and keep optional explanation/details hidden until explicit reveal.
- `ui-human-operability-validation`: require discoverable, closable, keyboard/focus-equivalent on-demand disclosure.
- `ui-implementation-validation`: require current evidence for default-hidden, reveal/close behavior, and absence of internal content from the observed UI.
- `field-lifecycle-mesh`: hand UI-boundary presentation and metadata field candidates to UI Flow Structure without forcing all backend fields into the high-level UI model.

## Impact

- Core API: `flowguard/ui_structure.py` and public exports in `flowguard/__init__.py`.
- Model ownership: existing `.flowguard/ui_flow_structure_skill`, `.flowguard/harden_ui_real_surface_validation`, and `.flowguard/behavior_commitment_ledger` models.
- Agent behavior: compact/full UI templates and the repository-managed `flowguard-ui-flow-structure` skill prompt, protocols, and generated SkillGuard contract.
- Validation: focused UI/API/template/skill tests, finite known-bad cases, model regression, full test regression, OpenSpec verification, project audit, installed-skill parity, and local Git/shadow synchronization.
- Out of scope: visual geometry/window redesign, fixed text-count or font-size quotas, final copywriting, and admin/operator/developer/auditor audience systems.
