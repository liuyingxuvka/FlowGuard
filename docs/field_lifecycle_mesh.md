# FlowGuard FieldLifecycleMesh

FieldLifecycleMesh is the FlowGuard route for field-level coverage. It exists
because fields often carry behavior even when the high-level model only names a
state, branch, or feature.

## What It Covers

- every discovered field at the lowest useful field group;
- behavior-bearing fields in high-level models through `FieldProjection`;
- field owners, readers, and writers;
- a UI-boundary handoff for every field whose readers reach an ordinary UI
  adapter, view model, display, text, or output boundary;
- lifecycle state: new, active, old, replaced, deprecated, derived, or
  archive-only;
- old-field disposition: deleted, blocked, migrated, delegated,
  same-contract repaired, explicitly preserved, or scoped out with reason;
- model obligation, code contract, and required test kinds for fields that
  affect behavior;
- minimal `gate:`, `test:`, and `replay:` evidence refs for broad behavior
  field claims.

## Parent And Child Shape

Use a high-level model for important behavior fields. Use child or leaf field
groups to account for all fields, including display-only and metadata fields.
Leaf coverage can mark non-behavior fields as scoped out, but it must do so
explicitly.

A field role does not decide user visibility. Whenever a reader reaches the
ordinary UI boundary, FieldLifecycleMesh hands the field id or a justified
grouped set of source ids to the `ui_flow_structure` owner as candidate
content—even when the source role is state, permission, routing, presentation,
or metadata. UI Flow Structure alone chooses `user_visible`,
`user_on_demand`, or `internal`. FieldLifecycleMesh does not create audience
roles, does not grant display permission, and does not force fields with no
ordinary-UI reader into the UI plan.

```text
feature model
-> important behavior fields projected to obligations/contracts
-> child field group
-> every discovered field accounted
-> every ordinary-UI-reader candidate handed to UI Flow Structure
-> old fields closed by disposition evidence
```

## Default Replacement Policy

Replacing a feature, field, alias, wrapper, or fallback does not mean keeping
the old path. Unless compatibility is explicitly required, the old surface must
be deleted, blocked, migrated, delegated, same-contract repaired, or scoped out
with a reason and evidence.

## Minimal Field Route Refs

For bounded design work, a field row and projection can stay lightweight. For a
full, runtime, production, release, or closure claim, a behavior-bearing field
projection should point to the evidence route that proves the field is not just
listed in a dictionary.

Use existing `FieldProjection.evidence_refs`:

```python
FieldProjection(
    "projection:checkout_mode",
    "field:checkout_mode",
    model_obligation_id="obligation:checkout_mode_routes",
    code_contract_id="contract:checkout_mode_router",
    required_test_kinds=("negative_path", "replay"),
    evidence_refs=(
        "gate:checkout-mode-boundary",
        "test:missing-checkout-mode-rejected",
        "replay:checkout-mode-runtime-path",
    ),
)
```

These references are handoffs. They do not replace Model-Test Alignment,
Runtime Gateway Adoption, conformance replay, or Closure Contract evidence.

When a field/schema boundary needs finite bad-case coverage, project it to
ContractExhaustionMesh. FieldLifecycleMesh declares the field, owner, readers,
writers, lifecycle, replacement, and behavior projection; ContractExhaustionMesh
creates canonical missing-field, empty-value, wrong-type, unknown-enum, or
old-field case ids with explicit oracle reactions.

## Route Handoffs

- Existing Model Preflight records behavior field ids and existing field owners.
- Code Structure Recommendation records field owner/reader/writer maps.
- UI Flow Structure receives every field id or grouped source id whose readers
  reach an ordinary UI boundary, then owns the
  content-admission decision and visible behavior evidence.
- Model-Test Alignment consumes field projections as model obligations and code
  contracts.
- Architecture Reduction and Legacy Path Disposition close old fields.
- Model-Miss Review records root-cause fields, same-class field boundaries, and
  old field disposition.
- ContractExhaustionMesh generates canonical field bad-case ids from those
  root-cause or same-class field boundaries.
- DevelopmentProcessFlow stales field evidence after later field/projection or
  replacement writes.
- Closure Contract blocks broad confidence when required field lifecycle
  evidence is missing or not full confidence.
