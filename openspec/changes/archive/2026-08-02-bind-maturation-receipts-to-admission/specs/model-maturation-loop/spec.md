## ADDED Requirements

### Requirement: Maturation publishes one downstream authority
The model maturation loop SHALL publish its terminal result through the canonical maturation receipt boundary, and downstream normal paths SHALL consume only the verified projection of that receipt.

#### Scenario: In-memory report is passed directly downstream
- **WHEN** a caller presents an unreceipted maturation report to an admission or broad-confidence gate
- **THEN** the consumer rejects it as non-authoritative
