# model-maturation-receipt Specification

## Purpose
Provide one immutable, content-addressed, independently verifiable authority for an exact model maturation result and all downstream readiness consumers.
## Requirements
### Requirement: Terminal maturation is published as a canonical receipt
A closed or blocked maturation run SHALL publish a content-addressed receipt binding the exact task, coverage demand, candidate model, input set, evidence set, decision, confidence scope, open gaps, producer, and covered obligations.

#### Scenario: Receipt content changes
- **WHEN** any bound identity, evidence, decision, gap, or obligation changes
- **THEN** the receipt fingerprint changes and the prior receipt cannot represent the new run

### Requirement: Currentness and decision are verifier-derived
Consumers SHALL obtain currentness, eligibility, decision, confidence scope, and open gaps from independent receipt verification and MUST NOT accept those authority fields from a caller-authored mapping.

#### Scenario: Caller presents a fabricated current flag
- **WHEN** supplied data claims `current=true` without a matching canonical receipt and current snapshots
- **THEN** verification fails and no readiness consumer may treat the maturation as current

### Requirement: Understanding status is a read-only receipt projection
The system SHALL provide a status projection over explicitly supplied task, model, demand, resolution, maturation, and receipt identities. Reading status SHALL NOT execute an owner, publish or renew a receipt, change current authority, or convert missing evidence into success.

#### Scenario: No maturation receipt is supplied
- **WHEN** status is requested for a task with no matching verified maturation receipt
- **THEN** understanding sufficiency is reported as not-run or unresolved and no receipt is created

#### Scenario: Receipt identity is stale
- **WHEN** the supplied receipt does not match the current task, model, demand, or resolution identity
- **THEN** status reports stale with the mismatched identity fields
