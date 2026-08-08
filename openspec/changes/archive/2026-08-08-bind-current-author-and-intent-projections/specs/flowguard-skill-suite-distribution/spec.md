## ADDED Requirements

### Requirement: Shadow synchronization preserves the author-source projection
FlowGuard SHALL provide one explicit full-suite synchronization operation for an author-source shadow skill tree. The operation SHALL project the complete current author inventory, including author-only contract artifacts, and SHALL NOT generate consumer release files or use the consumer installation route as an alternate implementation.

#### Scenario: Installer-owned consumer tree becomes an author shadow
- **WHEN** the target contains the exact unchanged FlowGuard consumer projection recorded by its installer ownership authority
- **AND** the caller explicitly requests author-source synchronization
- **THEN** the operation replaces the complete managed FlowGuard suite with the current author projection
- **AND** it removes only exact installer-owned consumer-only artifacts
- **AND** it records the resulting author-source ownership and current tree identity

#### Scenario: Already-current author shadow is synchronized again
- **WHEN** the target ownership authority and complete managed tree already equal the current author projection
- **THEN** the operation succeeds without changing any file
- **AND** reports an idempotent current result

#### Scenario: Consumer installation is requested
- **WHEN** the caller requests the ordinary install operation
- **THEN** FlowGuard continues to produce only the clean consumer distribution
- **AND** no author-only contract or maintenance artifact enters the installed consumer tree

### Requirement: Author synchronization is ownership-bounded and repository-local
Author-source synchronization SHALL examine only the declared FlowGuard skill-suite members and its own ownership authority. It SHALL preserve co-located skills and every file outside that boundary, SHALL reject unsafe paths or modified/unowned collisions, and SHALL NOT copy, reset, clean, or otherwise synchronize the surrounding repository.

#### Scenario: Other project work is co-located with the shadow skills
- **WHEN** the target repository contains unrelated skills, source files, reports, OpenSpec changes, or peer-agent edits outside the managed FlowGuard member boundary
- **THEN** author synchronization leaves all of them unchanged
- **AND** its claim is limited to the synchronized FlowGuard author tree

#### Scenario: Managed target file was modified after installation
- **WHEN** a target path that would be replaced or removed no longer matches its recorded ownership hash
- **THEN** synchronization preserves the target and fails with an exact conflict
- **AND** no partial author projection is activated

#### Scenario: Dry-run inspects a role transition
- **WHEN** the caller requests a dry-run from an exact consumer projection to author source
- **THEN** the result lists the exact copies, removals, ownership transition, and preserved co-located paths
- **AND** the target remains byte-for-byte unchanged
