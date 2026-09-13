## ADDED Requirements

### Requirement: Receipt reuse is independently verifiable
Receipt consumers SHALL verify raw bytes, schema, producer, subject, owner, input identity, terminal status, and cleanup before reuse; missing, corrupt, skipped, foreign, or aggregate-only receipts SHALL block.

#### Scenario: Corrupt receipt is found
- **WHEN** a receipt path exists but its raw content, subject, or terminal status fails verification
- **THEN** the consumer reports blocked and does not run a compatibility reader or silently execute a replacement owner
