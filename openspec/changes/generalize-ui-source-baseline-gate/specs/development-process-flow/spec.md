## ADDED Requirements

### Requirement: Source-baseline artifacts stale UI process evidence
DevelopmentProcessFlow SHALL treat UI work-mode, source-baseline, source-target mapping, approved difference dispositions, generic source interaction gates, and observed-source alignment artifacts as freshness-sensitive UI lifecycle artifacts.

#### Scenario: Source mapping changes after implementation evidence
- **WHEN** a source-based UI source-target mapping changes after UI implementation validation or walkthrough evidence was produced
- **THEN** DevelopmentProcessFlow marks the prior UI evidence stale and recommends rerunning the relevant UI Flow Structure gates

#### Scenario: Generic source interaction changes after evidence
- **WHEN** a source interaction branch, no-handler disposition, native/manual boundary, or approved difference changes after source-baseline evidence was produced
- **THEN** DevelopmentProcessFlow marks downstream source-based UI completion evidence stale

### Requirement: DevelopmentProcessFlow uses generic source-baseline names
DevelopmentProcessFlow SHALL name generic UI source-baseline artifacts and evidence in public guidance, templates, and constants rather than naming a specific source technology.

#### Scenario: Generic process surface uses source-specific name
- **WHEN** a current DevelopmentProcessFlow skill, template, API constant, or docs row names one source technology as a generic UI freshness gate
- **THEN** the process surface is incomplete until it is generalized
