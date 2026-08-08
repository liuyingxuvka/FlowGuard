## Why

The v0.68.7 self-model regression passed all model children but the subsequent
revision-owner evidence step correctly blocked because the existing
`affected_authority_inventory` route had no explicit semantic model binding.
Without that binding, FlowGuard can describe an affected source/test/runtime
inventory while still being unable to prove which existing model owns that
inventory during an atomic revision.

## What Changes

- Bind both the `affected_authority_inventory` endpoint route and its
  `authoritative_model_system` inventory-root route to the existing
  `authoritative_model_system` model; do not create a fallback or a second
  authority model.
- Require every native owner route in an affected revision closure to have one
  unique, explicit semantic model binding before owner evidence is written.
- Add production-shaped coverage that derives the complete current candidate
  route universe and fails if either inventory route, or any later route, is
  unmapped or duplicated.
- Extend FlowGuard's own authority model with a known-bad scenario for an
  affected inventory whose semantic owner mapping is missing.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-revision-set`: affected native-owner evidence must close over an exact,
  explicit owner-to-model binding map with no generic assignment.
- `authoritative-model-system`: the affected authority inventory is governed by
  the existing authoritative model-system model and missing semantic ownership
  is a blocking authority defect.

## Impact

The change affects the model-revision owner-evidence assembler, its tests, the
authoritative model-system executable model, and the two corresponding OpenSpec
contracts. It does not add a public product route, change the target-language
boundary, or add compatibility behavior.
