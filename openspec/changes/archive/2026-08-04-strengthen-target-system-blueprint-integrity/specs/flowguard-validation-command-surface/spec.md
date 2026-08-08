## MODIFIED Requirements

### Requirement: The target blueprint audit is the single read-only status command
The command surface SHALL provide one provider-neutral target-system blueprint audit operation for an explicit target descriptor, frozen provider evidence, and current native report set. The same operation SHALL return both the canonical machine-readable qualification report and composable `0|1|2` exit semantics. It SHALL NOT have a duplicate check alias, write a projection, modify the target, install software, or execute a missing provider.

#### Scenario: A declared workflow blueprint audit is requested
- **WHEN** a caller supplies a bounded workflow target and current observation and authority provider results
- **THEN** the command returns canonical machine-readable provider, lineage, evidence, and depth findings without requiring a programming language
- **AND** the target artifacts and authority pointers remain unchanged

#### Scenario: A target boundary lacks a deep provider
- **WHEN** audit reaches a required source, workflow, trace, resource, or authority boundary for which no registered current provider supplies the required capability
- **THEN** the command returns a non-pass result naming the exact boundary and missing provider capability
- **AND** it does not fall back to FlowGuard's Python self preset or another shallow adapter

#### Scenario: FlowGuard self-blueprint and reduction are requested together
- **WHEN** the self-blueprint check receives the explicit composed architecture-reduction option
- **THEN** it builds one current self-blueprint and returns both compact bounded results from that exact bundle
- **AND** it does not rebuild the blueprint, write a cache, or modify source

### Requirement: Blueprint command surfaces use one qualification owner before explicit export
The command surface SHALL provide a read-only implementation-inventory audit and canonical target/project blueprint audits. An explicitly invoked provider-neutral target export SHALL consume the same descriptor, frozen evidence, native report set, and qualifier as target audit; the Python-project convenience export SHALL consume its canonically assembled project bundle. Both SHALL reuse the same projection envelope, writer, and verifier rather than accepting a second raw manifest/current-label authority. Read-only commands SHALL NOT write artifacts, publish evidence, change model authority, or execute missing owners. Export SHALL write only to the explicit bounded output path, preserve the exact readiness state and gaps, and verify its manifest and shards before materialization success.

#### Scenario: Read-only project blueprint audit finds missing evidence
- **WHEN** a project blueprint audit lacks a required current binding or resource
- **THEN** it reports the exact incomplete or stale gap and performs no write or owner execution

#### Scenario: Explicit project projection export succeeds
- **WHEN** every canonical bundle layer is representable and the user supplies an allowed output path
- **THEN** the command writes deterministic content-addressed projection material and verifies every emitted reference
- **AND** it reports `materialization_ok` and `materialization_status` separately from `model_readiness_status`

#### Scenario: Explicit provider-neutral target export succeeds
- **WHEN** a TypeScript software target or non-code workflow has strict audited artifacts and the user supplies an allowed output path
- **THEN** `target-system-blueprint-export --descriptor --frozen-evidence --native-report-set --output` SHALL preserve the complete typed audit inputs and result through the shared content-addressed projection kernel
- **AND** blocked or not-run model evidence SHALL remain visible even when materialization succeeds

## ADDED Requirements

### Requirement: Audit and deterministic export are separate explicit actions
Read-only target/project audit SHALL remain separate from deterministic target/project export. Audit SHALL report the current model depth and exact gaps without writing target or projection artifacts. Export SHALL occur only through `target-system-blueprint-export` or the Python convenience `project-blueprint-export` after the same typed qualification chain has produced the result to preserve.

#### Scenario: Audit is used during ordinary maintenance
- **WHEN** ordinary affected-only maintenance invokes a target or project blueprint audit
- **THEN** it reports the licensed current understanding and writes no projection

#### Scenario: Export is explicitly requested
- **WHEN** a caller explicitly requests export for strict target artifacts or a canonically assembled project bundle
- **THEN** only the bounded output projection is written and verified
- **AND** any model gap or not-run status remains explicit in that projection and command result

## REMOVED Requirements

### Requirement: Export and reconstruction remain separately explicit
**Reason**: The old requirement preserved command flags and status language for a second empirical route that is not part of the canonical blueprint qualification workflow. The current product surface expresses positive audit and export ownership directly.

**Migration**: Use `target-system-blueprint-audit` or `project-blueprint-audit` for qualification and `project-blueprint-export` for explicit deterministic materialization.

### Requirement: Candidate and readiness commands are read-only
**Reason**: Candidate discovery remains useful, while the separately named readiness command duplicated the canonical audit's depth and gap result.

**Migration**: Use `project-blueprint-candidate` for unresolved candidate discovery and the canonical target/project audit for readiness.

## ADDED Requirements

### Requirement: Candidate blueprint discovery is read-only
FlowGuard SHALL expose a composable read-only command for candidate blueprint discovery. It SHALL perform no target-source edits, export, missing-owner execution, installation, or authority activation; canonical audit owns readiness and gap reporting.

#### Scenario: Candidate command finds unresolved semantics
- **WHEN** candidate discovery cannot independently establish one or more behavior contracts
- **THEN** the command SHALL return a nonzero or explicit incomplete terminal with all unresolved ids
- **AND** it SHALL write no project artifact unless explicit export is separately requested
