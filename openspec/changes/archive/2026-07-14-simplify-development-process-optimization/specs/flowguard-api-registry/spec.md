## ADDED Requirements

### Requirement: Process optimization is exported only through the existing process API group
The public API SHALL expose at most five compact process-optimization dataclasses and one canonical review function through the existing DevelopmentProcessFlow group: an inspectable equivalence contract, candidate, repair group, decision, report, and `review_process_optimization`. The standalone strategy API group, former `review_development_process_strategy`, cost vector, campaign/observation/cluster/hypothesis/batch/reevaluation/dependency-graph types, six-policy constants, rollout constants, Pareto helpers, and former projection helpers SHALL NOT be public or current runtime authority.

#### Scenario: API discovery
- **WHEN** a caller inspects the DevelopmentProcessFlow route API group
- **THEN** the five compact records and one optimization review are discoverable under the existing DPF group without a new public route id

#### Scenario: Retired strategy symbol remains exported
- **WHEN** any retired strategy type, constant, helper, review, or API group remains in `flowguard.__all__` or public route discovery
- **THEN** API registry validation fails

## REMOVED Requirements

### Requirement: Strategy selection is exported through the existing process API group
**Reason**: The former requirement promises strategy-specific inputs, cost comparison, and review functions that no longer exist in the current bounded optimizer API.

**Migration**: Replace the requirement directly with the process-optimization API requirement above. Keep DevelopmentProcessFlow as the sole public group and expose no compatibility alias, standalone strategy group, or retired review function.
