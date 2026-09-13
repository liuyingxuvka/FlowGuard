## MODIFIED Requirements

### Requirement: Current layout is mandatory and human-readable

Every adopted target SHALL have one current compact `.flowguard/layout.toml` that declares the current layout contract and allowed semantic destinations. The allowed destinations SHALL be `behavior`, `models`, `structure`, `verification`, `evidence`, and exceptional non-authoritative `history`; each destination SHALL be created only when it has content. Top-level `audits`, `projections`, and `work` SHALL NOT be current roots, and ambiguous names such as `DNA`, `dna_audit`, or `software_dna` SHALL remain forbidden.

The layout contract SHALL describe path/role/kind/safety shape. It SHALL NOT store a per-member content fingerprint or require reading evidence, history, work, projection, or runtime-output bytes. Governed source and model content currentness SHALL be proven by their native owners.

#### Scenario: Compact layout with optional roots passes

- **WHEN** the compact current contract is valid and every present entry belongs to one allowed destination
- **THEN** the layout audit SHALL pass without requiring empty roots and without hashing member contents

#### Scenario: Complete current layout passes

- **WHEN** the manifest is current, the nine roots exist, and every inspected
  entry belongs to exactly one declared role
- **THEN** the layout audit SHALL pass without writing any file

#### Scenario: Missing or stale layout blocks

- **WHEN** `.flowguard`, `layout.toml`, a required role, or the current schema
  is missing or stale
- **THEN** the layout audit SHALL block before model, test, or evidence
  authority is read

#### Scenario: Runtime evidence grows

- **WHEN** a current evidence root gains a valid receipt or object that is not a layout-shape violation
- **THEN** the layout shape identity SHALL remain current
- **AND** evidence lifecycle authority SHALL classify the new material separately

#### Scenario: Retired root or unsafe entry exists

- **WHEN** a top-level retired root, path escape, reparse point, bytecode/cache entry, or ambiguous current path exists
- **THEN** layout audit SHALL block before model, test, or evidence authority is read

## ADDED Requirements

### Requirement: Layout observation is bounded and shape-only

The layout audit SHALL perform at most one shape observation for an invocation. It SHALL inspect allowed source-role paths for role, relative path, kind, and filesystem safety, but SHALL NOT read every member file merely to calculate a layout identity. Evidence and exceptional history SHALL be treated as opaque lifecycle stores after their root safety is checked.

#### Scenario: Two files contain identical bytes

- **WHEN** files in different semantic roles happen to contain identical bytes
- **THEN** layout SHALL not infer duplicate authority from byte equality alone
- **AND** native owner checks SHALL decide semantic ownership

#### Scenario: Layout is inspected twice by callers

- **WHEN** multiple project-audit stages request the layout result in one invocation
- **THEN** they SHALL consume the same shape observation rather than walking or hashing the tree again
