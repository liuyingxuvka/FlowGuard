## ADDED Requirements

### Requirement: Target topology separates structural and cross-boundary parents
Every target-topology node SHALL expose one `structural_parent_id` and an independently ordered set of `cross_boundary_parent_ids`. The sole topology root SHALL use the declared root sentinel for `structural_parent_id`; every other in-scope node SHALL name exactly one current structural parent. Consumer, feedback, retry, repair, shared-resource, and other cross-boundary relations SHALL be represented through `cross_boundary_parent_ids` or their typed relation records and SHALL NOT create, replace, or multiply structural parentage.

#### Scenario: Non-root node has two structural parents
- **WHEN** one non-root topology node names two structural parents or its structural relation set resolves to more than one parent
- **THEN** target-topology qualification SHALL be blocked with the exact node and competing parent identities
- **AND** moving either parent to an untyped relation SHALL NOT restore readiness

#### Scenario: Cross-boundary consumer points to an ancestor
- **WHEN** a child model also consumes an output from an ancestor or another branch
- **THEN** that owner SHALL appear as a typed cross-boundary parent or relation
- **AND** the child's sole `structural_parent_id` SHALL remain unchanged
- **AND** the cross-boundary relation SHALL NOT become a structural cycle

#### Scenario: Structural parent is omitted
- **WHEN** a non-root node has only cross-boundary parents and no exact current structural parent
- **THEN** target-topology qualification SHALL report an orphan structural node
- **AND** cross-boundary connectivity SHALL NOT substitute for hierarchy closure
