## ADDED Requirements

### Requirement: Global routing uses a compact canonical decision table
Global FlowGuard guidance SHALL present one compact routing decision table for
ordinary AI use and SHALL avoid repeating long helper inventories in the hot
path.

#### Scenario: Agent reads reusable AGENTS guidance
- **WHEN** an agent reads `docs/agents_snippet.md`
- **THEN** it first sees task-size triage, the FlowGuard routing decision,
  thin default path, hard gates, and a compact route table before any reference
  protocol detail

#### Scenario: Detailed route content is needed
- **WHEN** the selected route needs detailed protocol rules, helper API
  inventories, examples, or evidence ledgers
- **THEN** the guidance points to the matching skill reference or docs page
  instead of duplicating the full content in the AGENTS hot path

### Requirement: Duplicate route inventories are bounded
FlowGuard prompt tests SHALL prevent the kernel, AGENTS snippet, and satellite
skills from each carrying independent long-form route inventories.

#### Scenario: Route inventory grows in multiple hot paths
- **WHEN** tests detect duplicate long-form route/helper inventories across
  first-read prompt surfaces
- **THEN** they fail or require the extra detail to move behind the reference
  handoff before done/release confidence is claimed
