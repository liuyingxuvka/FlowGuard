## Why

FlowGuard can validate the surfaces that callers declare, but it does not yet
independently prove that the declared set is the complete set of modelable UI,
field, API, CLI, file, workflow, agent-operation, and evidence surfaces.
Meanwhile, the current `SpecContext` path gives official OpenSpec a privileged
core shape even though FlowGuard is intended to work with OpenSpec, Spec Kit,
Superpowers, declared files, and future planning systems without transferring
their lifecycle authority.

## What Changes

- **BREAKING** Replace the OpenSpec-only `SpecContext` public API, CLI,
  templates, fields, and model with a provider-neutral, read-only
  `WorkContext` and adapter registry. No compatibility alias, fallback reader,
  dual CLI, provider execution bridge, session, cache, or receipt path remains.
- Add built-in read-only adapters for official OpenSpec and explicitly declared
  files, plus a safe registration boundary for future convenience adapters.
  Spec Kit and Superpowers can participate through declared-file profiles
  without becoming hard-coded core providers.
- Strengthen Behavior Commitment Ledger with an independently derived expected
  source inventory, source roles and fingerprints, exact-set reconciliation,
  normative-source conflict detection, and explicit modeled/delegated/scoped
  disposition for every discovered modelable item.
- Join existing UI observed-surface inventories and FieldLifecycleMesh leaf
  inventories into the same mechanical completeness accounting without moving
  UI or field judgment into the ledger.
- Generalize Existing Model Preflight, PlanDetailing,
  DevelopmentProcessFlow, maintenance scan, self-maintenance, TestMesh, public
  prompts, and documentation from OpenSpec-only context fields to one or more
  current `WorkContext` rows.
- Strengthen model-authority audit so a stored observed snapshot cannot remain
  green when the current model regression/source inventory contains required
  models or source surfaces that the snapshot omitted.
- Extend `ModelRevisionSet` affected-closure derivation to account for changed
  source surfaces and owner artifacts instead of trusting caller-declared
  changed-id lists.
- Preserve the three existing subject lanes and atomic activation:
  `observed_implementation`, `normative_target`, and
  `counterfactual_experiment`.
- Update the five affected FlowGuard consumer prompts through the existing
  SkillGuard author-maintenance unit, regenerate the clean consumer projection,
  and keep official third-party skills outside SkillGuard authority.

## Capabilities

### New Capabilities

- `work-context`: Provider-neutral, project-bounded, content-addressed,
  read-only planning/work artifacts with adapter-declared roles and zero
  provider execution authority.

### Modified Capabilities

- `behavior-commitment-ledger`: Independently discover and exactly reconcile
  all expected behavior-source surfaces with modeled, delegated, or scoped
  dispositions.
- `existing-model-preflight`: Consume multiple current WorkContexts after
  plane-first lookup and preserve provider, lane, fingerprint, and ownership
  boundaries.
- `development-process-flow`: Order and stale generic WorkContext inputs while
  keeping every provider lifecycle native.
- `plan-detailing-compiler`: Normalize provider-declared artifact roles instead
  of assuming an OpenSpec artifact set.
- `test-evidence-mesh`: Bind required evidence to the same independent coverage
  inventory and reject every provider status as test execution proof.
- `field-lifecycle-mesh`: Project complete leaf-field inventory identities into
  the shared coverage reconciliation and UI handoff.
- `flowguard-ui-flow-structure`: Project observed UI controls, displays,
  journeys, and blindspots into the shared coverage reconciliation.
- `authoritative-model-system`: Compare current source/model inventory against
  the observed snapshot instead of auditing stored authority in isolation.
- `model-revision-set`: Derive changed source, commitment, field, side-effect,
  contract, and test sets from exact owner artifacts.
- `flowguard-api-registry`: Replace SpecContext exports, CLI, and templates with
  the sole current WorkContext surface.
- `flowguard-codex-skill-satellites`: Make kernel, ledger, preflight, process,
  and TestMesh prompts provider-neutral while preserving native owners.
- `project-adoption-version-gate`: Generate provider-neutral WorkContext
  guidance and current completeness gates.
- `flowguard-skill-suite-distribution`: Regenerate and transactionally install
  the exact clean consumer projection after maintained prompt changes.
- `spec-provider-work-packages`: Retire the obsolete provider work-package,
  execution, receipt, and reconciliation requirements in favor of
  `work-context`.

## Impact

The change affects the `flowguard` Python package, CLI/API exports, templates,
project adoption, model-system authority, the canonical behavior ledger,
FlowGuard self-models and regression manifest, focused and full tests,
OpenSpec main specifications, five maintained skill prompt surfaces, clean
consumer installation, package version metadata, changelog, local editable
installation, Git main, tag, and source-only GitHub Release.
