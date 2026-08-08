## ADDED Requirements

### Requirement: Structural hierarchy and cross-boundary feedback close independently
ModelMesh SHALL validate an acyclic, singly parented structural graph independently from the typed cross-boundary relation graph. Cross-boundary consumers, feedback, retry, repair, and shared-resource relations SHALL remain non-structural even when they connect an ancestor, descendant, or sibling, and SHALL be evaluated for interface compatibility and closure without changing `structural_parent_id`.

#### Scenario: Cross-boundary relation is counted as a second parent
- **WHEN** one node has a valid structural parent and a cross-boundary consumer or feedback owner is also counted as structural
- **THEN** ModelMesh SHALL reject the topology classification
- **AND** the relation SHALL be reclassified or the node SHALL remain blocked rather than accepting multi-parent structure

#### Scenario: Structural graph is acyclic but feedback graph has a cycle
- **WHEN** structural parent edges form a valid tree or forest rooted at the declared root while typed cross-boundary relations contain a reachable cycle
- **THEN** structural closure MAY remain valid
- **AND** feedback closure SHALL be evaluated independently without rewriting the structural graph

### Requirement: Every real feedback component has current progress closure
Every reachable strongly connected component in the typed feedback graph with more than one member or an explicit self-loop SHALL bind one current progress contract and independent current evidence. The contract SHALL identify the repeated token or packet boundary and at least one verified blocker, repair-token change, decreasing ranking measure, monotone progress rule, or finite iteration bound that prevents unchanged unbounded circulation.

#### Scenario: Feedback SCC has only descriptive labels
- **WHEN** a reachable feedback component is labeled retry, repair, wait, or progress but has no current progress contract and independent evidence
- **THEN** mesh closure SHALL be blocked with the exact component and missing progress obligation
- **AND** member-local green results or an acyclic structural graph SHALL NOT close the feedback loop

#### Scenario: Progress contract is stale or self-certified
- **WHEN** the progress contract targets another snapshot, its evidence is stale, or the same mesh qualification result manufactures the evidence it consumes
- **THEN** the feedback component SHALL remain stale or blocked
- **AND** the contract text alone SHALL NOT license parent confidence

#### Scenario: Finite feedback closure is independently proven
- **WHEN** every member and relation in a reachable feedback component is current and an independent receipt proves the declared repair-token change, ranking decrease, blocker, or finite bound
- **THEN** ModelMesh MAY close that component for the exact current snapshot
- **AND** the closure SHALL NOT generalize to another component, snapshot, or unbound repeated input

### Requirement: Full parent closure consumes every exact-current child receipt
The current full model parent SHALL aggregate hierarchy, reattachment, feedback, and evidence results without replacing child-owned validation. Every declared in-scope child SHALL have one exact-current terminal receipt produced by its declared child execution owner, and the parent receipt SHALL list and consume that exact receipt identity and fingerprint.

#### Scenario: Full parent is green without one child receipt
- **WHEN** the full model parent reports success while any declared child receipt is missing, stale, foreign, non-terminal, or absent from the parent consumed-receipt set
- **THEN** parent closure SHALL be blocked
- **AND** parent execution, source hashes, or another child's receipt SHALL NOT substitute for the missing child result

#### Scenario: Parent consumes every current child receipt
- **WHEN** every in-scope child has one exact-current terminal receipt and the full parent binds each receipt through the current reattachment and interface contracts
- **THEN** the parent MAY report aggregate closure for that exact snapshot
- **AND** each child receipt SHALL retain its original producer, subject, scope, and result identity
