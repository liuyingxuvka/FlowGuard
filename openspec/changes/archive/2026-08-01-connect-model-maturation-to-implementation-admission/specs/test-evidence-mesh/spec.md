## ADDED Requirements

### Requirement: Triggered test obligations contribute to maturation
TestMesh SHALL project its independently required test cells, child owners, current terminal results, stale evidence, skipped work, and not-run work into task-local maturation when layered or slow validation is triggered.

#### Scenario: Planned or running test is not passing evidence
- **WHEN** a required test is planned, not-run, running, progress-only, skipped, stale, failed, or lacks terminal artifacts
- **THEN** maturation MUST preserve the corresponding evidence gap and MUST NOT count it as current passing coverage
