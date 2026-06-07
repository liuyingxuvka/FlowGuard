# FlowGuard FieldLifecycleMesh

FieldLifecycleMesh is the FlowGuard route for field-level coverage. It exists
because fields often carry behavior even when the high-level model only names a
state, branch, or feature.

## What It Covers

- every discovered field at the lowest useful field group;
- behavior-bearing fields in high-level models through `FieldProjection`;
- field owners, readers, and writers;
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

```text
feature model
-> important behavior fields projected to obligations/contracts
-> child field group
-> every discovered field accounted
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

## Route Handoffs

- Existing Model Preflight records behavior field ids and existing field owners.
- Code Structure Recommendation records field owner/reader/writer maps.
- Model-Test Alignment consumes field projections as model obligations and code
  contracts.
- Architecture Reduction and Legacy Path Disposition close old fields.
- Model-Miss Review records root-cause fields, same-class field cases, and old
  field disposition.
- DevelopmentProcessFlow stales field evidence after later field/projection or
  replacement writes.
- Closure Contract blocks broad confidence when required field lifecycle
  evidence is missing or not full confidence.
