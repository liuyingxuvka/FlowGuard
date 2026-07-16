## Why

FlowGuard already ships reusable templates, but it lacks a fail-closed registry that can decide which validated template pack applies to a declared context and prove that the selected template instance is still current. Without that layer, agents can silently choose no template, choose incompatible templates together, or reuse stale template output.

## What Changes

- Add a validated template-pack registry with a canonical manifest, bounded hard predicates, explicit field ownership, and deterministic identities.
- Define fail-closed selection for zero, one, or multiple matches, including declared base-template behavior and explicit conflict results.
- Permit multi-template composition only when every match opts in and claimed fields are disjoint.
- Produce immutable selection and instance receipts that become stale when the manifest, selection context, parameters, or rendered instance changes.
- Add the coordinated launcher-owner handoff as a target-owned, unsealed SkillGuard-neutral projection over FlowGuard's current file-template factories; SkillGuard may supervise it but cannot infer FlowGuard routes or semantics.

## Capabilities

### New Capabilities

- `validated-template-pack-registry`: Validates template-pack manifests, selects zero/one/composable-many templates, and verifies selection and instance receipts by canonical digest.

### Modified Capabilities

None.

## Impact

- Adds the independent registry, a target-owned neutral projection adapter, and dedicated focused tests.
- Does not change `flowguard.templates`, `flowguard.risk_templates`, the public import facade, CLI, launcher, dependencies, or existing template storage/search behavior.
- The coordinated SkillGuard owner consumes the neutral projection through its current selector while FlowGuard retains factory, route, generated-file, and native-validation ownership.
