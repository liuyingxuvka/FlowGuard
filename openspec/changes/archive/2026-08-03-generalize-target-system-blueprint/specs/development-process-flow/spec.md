## ADDED Requirements

### Requirement: Process freshness includes target-system provider identities
DevelopmentProcessFlow SHALL track the target-system descriptor, every consumed provider input and result, canonical intent inventory, portable behavior bindings, formal coverage edges, coverage execution evidence, compact understanding summary, and static blueprint result as distinct freshness-sensitive artifacts.

#### Scenario: Only one provider input changes
- **WHEN** a source, workflow, trace, resource, or authority provider input changes
- **THEN** the process SHALL stale the exact affected blueprint neighborhood and consumers
- **AND** unrelated provider evidence MAY remain reusable when its identities still match

### Requirement: Final release gate consumes static blueprint and provider freeze
Before the unique final full release validation, the process SHALL freeze the exact target-system descriptor, provider registry and results, observed model revision set, source tree, test and resource inventories, static blueprint result, reduction review, skill projections, toolchain, and owner plan.

#### Scenario: Provider registry changes after the final plan
- **WHEN** a provider identity or capability mapping changes after the final plan is frozen
- **THEN** the final plan and affected evidence SHALL become stale
- **AND** publication SHALL wait for one newly frozen full gate without rolling back peer work

### Requirement: Nested validation evidence paths are bounded without losing identity
DevelopmentProcessFlow SHALL keep deeply nested internal validation work directories within the supported platform path budget. Short internal names SHALL be deterministic projections of the exact owner identity, while the immutable receipt SHALL retain the complete owner, input, run, artifact, and result identities.

#### Scenario: A readable evidence root and long model id feed a shard-safety proof
- **WHEN** the complete nested path would exceed the supported Windows path budget
- **THEN** the proof uses a short deterministic owner hash for its internal directory
- **AND** the terminal receipt still records the full model id and exact evidence identities
