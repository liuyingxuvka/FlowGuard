## ADDED Requirements

### Requirement: Contract exhaustion generates finite system-interaction cases
ContractExhaustionMesh SHALL accept owner-declared finite axes for artifact/delivery variants, initial environments, finite fault profiles, malformed boundary inputs, and benchmark/test shards within one exact affected system slice. It SHALL emit stable case/oracle/shard ids but SHALL NOT execute the system checker or regenerate schedule orderings already exhaustively represented by the compiled joint-step graph.

#### Scenario: Ordering axis is declared
- **WHEN** a composite owner declares delivery-policy or finite fault variants that change the system definition/request inputs
- **THEN** ContractExhaustionMesh emits canonical cases bound to the same slice and property ids without duplicating the checker's schedule exploration

#### Scenario: Global Cartesian product is requested
- **WHEN** the request has no finite slice/owner boundary or would combine unrelated model-network axes
- **THEN** exhaustion blocks the broad claim rather than generating an unbounded matrix
