## MODIFIED Requirements

### Requirement: Existing DPF skill teaches general process optimization
The installed DevelopmentProcessFlow skill SHALL activate internal process optimization only for explicit optimization, multiple outcome-equivalent routes, material repeated-work risk, or a real diagnostic-boundary choice. When active it SHALL teach hard equivalence, independent diagnostic-boundary and execution-mode selection, valid-related-diagnostics before repair unless a hard blocker invalidates descendants, immutable raw findings, evidence-backed repair grouping, affected revalidation, material-change replanning, and bounded claim wording. When inactive it SHALL omit candidates, costs, frontiers, clusters, and repair groups. The skill SHALL NOT prescribe collect-all or fail-fast universally or add another satellite skill.

#### Scenario: User describes inefficient fail-fix repetition
- **WHEN** the DPF skill receives a process where valid related diagnostics can expose one shared cause and repeated repair would create material rework
- **THEN** it selects a diagnostic boundary, preserves raw findings, groups only evidence-related failures, batches repair, and revalidates all affected obligations

#### Scenario: Hard prerequisite failure
- **WHEN** a prerequisite failure makes later checks invalid or unsafe
- **THEN** the skill stops those descendants, reports them as not run, and does not mechanically collect every failure

#### Scenario: Ordinary task has one clear route
- **WHEN** no optimizer activation reason exists
- **THEN** the skill performs ordinary lifecycle governance without outputting optimizer ceremony
