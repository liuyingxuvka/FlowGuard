## ADDED Requirements

### Requirement: TestMesh preserves diagnostic campaign topology
TestMesh SHALL record campaign id, planned/executed/failed/not-run counts, enumeration completeness, early-stop reason, and observation/cluster ids on child evidence without choosing a strategy or executing the child.

#### Scenario: Early-stopped child is reported
- **WHEN** a child suite stops under a valid fail-fast condition
- **THEN** TestMesh keeps its terminal result and early-stop reason while refusing to report complete enumeration

### Requirement: Campaign completeness claims are checked
TestMesh SHALL block a complete-enumeration claim when planned items are unaccounted, count relationships are inconsistent, or not-run diagnostics have no visible reason.

#### Scenario: Unaccounted planned test
- **WHEN** planned count is greater than executed plus not-run count
- **THEN** TestMesh reports a campaign coverage blocker
