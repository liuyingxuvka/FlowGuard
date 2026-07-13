## ADDED Requirements

### Requirement: Generated revalidation commands are project-relative
FlowGuard SHALL generate project-adoption minimum and required revalidation commands relative to the target project root. Generated commands persisted in human adoption logs MUST NOT embed the resolved absolute target path.

#### Scenario: Report recommends portable commands
- **WHEN** project adoption, audit, or upgrade builds a report for any target repository
- **THEN** its generated audit and suite-verification commands use `--root .`
- **AND** those generated commands do not contain the resolved absolute target root

#### Scenario: Human adoption log preserves privacy
- **WHEN** a writing project-adoption action records its next actions in `docs/flowguard_adoption_log.md`
- **THEN** the Markdown log contains the project-relative revalidation commands
- **AND** it does not contain the target repository's resolved absolute path through those next actions
