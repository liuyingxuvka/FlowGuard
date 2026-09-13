## Purpose

Give projects a compact, executable ModelMesh scaffold for parent/child
topology changes, without treating model count alone as evidence of a mesh.

## ADDED Requirements

### Requirement: ModelMesh template requires target-owned topology

The public ModelMesh template MUST require a target-defined parent partition,
one owner per child, one structural parent per child, explicit
shared-kernel/non-structural relations, changed-child boundaries, and
input/output/state/effect/guarantee reattachment decisions. It MUST include
joins, terminals, loops, retries, partial activation, and stale/not-run child
evidence states.

#### Scenario: Complete topology is declared

- **WHEN** every child has a unique owner and structural parent and all
  changed boundaries have reattachment decisions
- **THEN** the template can produce a target-owned mesh plan

#### Scenario: Count-only input is supplied

- **WHEN** a target declares three or more models but no parent partition or
  child relation
- **THEN** the template blocks and does not claim ModelMesh closure

### Requirement: Mesh closure has executable positive and negative cases

The template MUST provide positive cases and known-bad cases for missing
partition, overlapping siblings, two structural parents, changed child
without a parent decision, stale child receipt reuse, parent receipt used as a
child receipt, partial activation, and missing topology.

#### Scenario: Known-bad topology is exercised

- **WHEN** a negative case violates one required topology invariant
- **THEN** the target check rejects it with the declared protected error class

#### Scenario: Stale child evidence is reused

- **WHEN** a child receipt is stale or a parent receipt is presented as child
  evidence
- **THEN** the mesh check blocks and records the child-specific finding
