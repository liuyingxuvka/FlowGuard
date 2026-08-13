## Why

FlowGuard can already describe software and non-code workflows, but its provider registry, semantic self-mesh, and architecture-reduction report do not yet expose one trustworthy, target-neutral qualification path. This change closes that gap before the Guard-family repositories depend on FlowGuard as their shared DNA kernel.

## What Changes

- Add an explicit provider-neutral profile capability so external domain skills can register their own target profile, layer plan, and evidence owner without embedding domain behavior in FlowGuard.
- Add a current project-owned native owner binding declaration. FlowGuard validates
  its exact model denominator, route set, protected failures, and evidence
  freshness; it never recognizes a downstream product by model names.
- Separate static blueprint readiness from semantic self-mesh qualification, with a current, bound, non-candidate status required for a qualified self-DNA claim.
- Expose machine-readable qualification reasons and stale/unknown dispositions instead of treating a present model file or a green shallow check as proof.
- Make architecture-reduction reporting distinguish candidate inventory, proof completeness, and applied-and-verified simplification; unresolved candidates remain visible and are never silently removed.
- Make the checked-in native model directory the only DNA carrier. The repository
  tree, its model files, bindings, tests, evidence, and Git identity are the DNA;
  qualification reports their completeness and currentness without creating a
  second model authority or a generated target.
- Add focused executable tests and OpenSpec acceptance scenarios for duplicate providers, unknown profiles, stale meshes, missing bindings, and honest reduction status.

## Capabilities

### New Capabilities

- `provider-neutral-self-qualification`: A provider-neutral registry and self-DNA qualification contract that downstream Guard skills can consume without a second target authority or fallback behavior.

### Modified Capabilities

- None.

## Impact

The change affects `flowguard/model_revision_owner_evidence.py`, the current
authority rebuild path, `flowguard/target_system_blueprint.py`,
`flowguard/self_blueprint.py`, `flowguard/self_architecture_reduction.py`, the
retired standalone blueprint export command/module, their public exports,
focused tests, and the FlowGuard OpenSpec/model adoption records. It does not
add a domain-specific adapter, target-generation route, compatibility reader,
or second model authority.
