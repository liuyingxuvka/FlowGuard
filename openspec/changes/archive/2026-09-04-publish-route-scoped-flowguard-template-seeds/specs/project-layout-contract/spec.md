## MODIFIED Requirements

### Requirement: Role authority is explicit and conserved

The current manifest SHALL bind project identity, role roots, compact role
rules, the current model-authority pointer, and explicit non-authority
declarations for `history`, `work`, `audits`, and `projections`. It SHALL NOT
register one content fingerprint per ordinary member file. Each real entry
SHALL belong to exactly one role, while component/group inventories MAY be
owned by the semantic or verification route that needs them. Duplicate paths,
duplicate current authority, unsafe entries, missing required roots, and
ambiguous role ownership SHALL block.

#### Scenario: Material is placed in the wrong role

- **WHEN** a model is under `evidence`, a receipt is under `models`, a current
  artifact is under `history`, or an audit/work artifact is used as current
  evidence
- **THEN** audit SHALL report a typed role-authority blocker

#### Scenario: Compact role rules are conserved

- **WHEN** each observed path is assigned to exactly one declared role and no
  unsafe or ambiguous entry exists
- **THEN** audit SHALL pass without reading or hashing every ordinary member
  file

#### Scenario: A per-member inventory is supplied as current authority

- **WHEN** the layout manifest tries to make ordinary member fingerprints a
  second current authority
- **THEN** audit SHALL reject that shape and require the compact current
  layout rules

#### Scenario: Inventory is not conserved

- **WHEN** the manifest inventory and current disk entries differ by path or
  fingerprint
- **THEN** audit SHALL block and SHALL NOT read an alternate path
