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
