## ADDED Requirements

### Requirement: Explicit functional owner obligations
Model regression entries SHALL declare their functional obligations explicitly. Actual leaf receipts and parent coverage SHALL retain those exact obligations, with unaffected owner reuse permitted only for exact current evidence.

#### Scenario: A functional obligation is added to a model owner
- **WHEN** a functional obligation is added to a model owner
- **THEN** The owner execution contract and leaf receipt cover the added obligation and stale evidence is rejected.

