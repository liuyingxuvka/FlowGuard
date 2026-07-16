## MODIFIED Requirements

### Requirement: TestMesh preserves diagnostic campaign topology
TestMesh SHALL record campaign id, `diagnostic_boundary`, planned/executed/failed/not-run counts, visible not-run reason, and stable Finding Ledger ids on child evidence without choosing a process candidate, grouping failures, or executing the child. It SHALL NOT expose the former six-policy execution field, strategy observations, or failure-cluster ids.

#### Scenario: Budgeted child stops visibly
- **WHEN** a child suite reaches a valid `budgeted` stop condition
- **THEN** TestMesh keeps its terminal result, not-run count, reason, and finding ids without reporting declared completeness

#### Scenario: Hard blocker invalidates descendants
- **WHEN** a hard prerequisite failure makes descendant checks invalid
- **THEN** TestMesh records those descendants as not run with the blocker reason and does not require them to execute

### Requirement: Campaign completeness claims are checked
TestMesh SHALL require `planned_count == executed_count + not_run_count` and `failed_count <= executed_count`. It SHALL block a `declared_complete` claim when `not_run_count` is nonzero or failures lack stable finding references. `targeted` and `budgeted` boundaries MAY have not-run items only with visible reasons.

#### Scenario: Unaccounted planned test
- **WHEN** planned count is greater than executed plus not-run count
- **THEN** TestMesh reports a campaign coverage blocker

#### Scenario: Declared-complete campaign has a not-run item
- **WHEN** `diagnostic_boundary=declared_complete` and `not_run_count` is nonzero
- **THEN** TestMesh rejects the completeness claim even when the executed tests passed
