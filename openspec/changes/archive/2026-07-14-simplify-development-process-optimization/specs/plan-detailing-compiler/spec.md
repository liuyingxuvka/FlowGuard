## MODIFIED Requirements

### Requirement: Plan detail projects strategy execution gates
PlanDetailing SHALL preserve only process-optimization reason ids and required process-optimization evidence ids at the plan boundary. The optimization decision SHALL remain an independently produced evidence artifact consumed through DPF freshness rather than an embedded PlanDetail schema. Detailed steps and validation rows SHALL use their ordinary ordering, required/produced evidence, failure branch, repair action, and validation-requirement fields instead of copying selected policy, campaign, repair-batch, or reevaluation fields into every row.

#### Scenario: Repair group changes governed artifacts
- **WHEN** a plan applies a repair group
- **THEN** ordinary repair actions and validation rows identify its affected revalidation requirements, and DPF freshness blocks completion until current evidence exists

#### Scenario: Ordinary plan does not optimize
- **WHEN** a detailed plan has no process-optimization reason
- **THEN** its projection contains no optimization-evidence references or strategy-specific step/validation fields
