## ADDED Requirements

### Requirement: Authenticated functional material and selected reads
Native producers SHALL export receipt-free architecture material with independently derived implementation inventory and current production source observations. Selected reads SHALL expose finite observed growth gaps and verify raw input currentness once after a complete selected batch.

#### Scenario: A selected batch completes
- **WHEN** a selected batch completes
- **THEN** The reader verifies all observed raw inputs and authority identities and blocks the entire batch if they changed.

