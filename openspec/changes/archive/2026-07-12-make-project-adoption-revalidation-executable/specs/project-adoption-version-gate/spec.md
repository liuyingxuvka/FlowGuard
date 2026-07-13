## MODIFIED Requirements

### Requirement: Generated revalidation commands are project-relative
FlowGuard SHALL generate project-adoption minimum and required executable revalidation commands that are owned by the installed FlowGuard package, run from the target project root, and do not require FlowGuard source-repository files. Generated commands persisted in human adoption logs MUST NOT embed the resolved absolute target path. A human-only revalidation instruction MAY remain as prose but MUST NOT be represented as a successfully validated executable command.

#### Scenario: Report recommends an executable portable command
- **WHEN** project adoption, audit, or upgrade builds a report for a valid target repository that does not contain the FlowGuard source `scripts/` directory
- **THEN** its generated executable revalidation command uses `python -m flowguard project-audit --root . --json`
- **AND** the command succeeds when executed from that target project
- **AND** the returned report contains passing current project-adoption and skill-suite status

#### Scenario: Report excludes source-layout-only commands
- **WHEN** project adoption, audit, or upgrade builds required revalidation guidance for an ordinary adopted target
- **THEN** no generated executable command requires `python scripts/` or another FlowGuard source-repository-relative path
- **AND** the existing package-owned project audit remains the single target-project audit authority

#### Scenario: Human adoption log preserves privacy
- **WHEN** a writing project-adoption action records its next actions in `docs/flowguard_adoption_log.md`
- **THEN** the Markdown log contains the package-owned project-relative revalidation command
- **AND** it does not contain the target repository's resolved absolute path through those next actions
