# long-check-observability Specification

## Purpose
TBD - created by archiving change standardize-long-check-observability. Update Purpose after archive.
## Requirements
### Requirement: Background checks record durable evidence
FlowGuard skill guidance SHALL require long-running background checks to record durable stdout, stderr, combined output, exit status, and metadata artifacts by default.

#### Scenario: Long check is run in the background
- **WHEN** an agent runs a long FlowGuard check outside the foreground session
- **THEN** the agent records `.out.txt`, `.err.txt`, `.combined.txt`, `.exit.txt`, and `.meta.json` artifacts under a declared log root

### Requirement: Reports cite concrete completion evidence
FlowGuard skill guidance SHALL require final task reports to cite the log root, exit code, last update time, and proof-reuse status for long-running checks.

#### Scenario: Agent reports a completed long check
- **WHEN** an agent claims a long FlowGuard check completed
- **THEN** the report names the log artifacts, exit code, last update time, and whether the result was newly executed or reused from a valid proof

### Requirement: Progress remains observability only
FlowGuard skill guidance SHALL explain that progress lines are liveness evidence only and MUST NOT replace executable check results.

#### Scenario: Progress reaches one hundred percent
- **WHEN** a progress stream reaches `100%`
- **THEN** the agent still waits for the check result and exit status before claiming pass or fail

### Requirement: Custom runners declare progress boundaries
FlowGuard skill guidance SHALL require agents to distinguish direct Explorer progress from legacy or custom runners that only emit final reports.

#### Scenario: Custom runner lacks live progress
- **WHEN** a project-specific runner bypasses direct Explorer progress
- **THEN** the agent reports that the runner is final-report-only unless that runner implements its own stderr progress
