## ADDED Requirements

### Requirement: Specification providers retain native authority
FlowGuard SHALL read declared specification providers without replacing their requirement, task, strict-verification, implementation, or archive authority.

#### Scenario: OpenSpec package is consumed
- **WHEN** an OpenSpec change is discovered inside the declared project root
- **THEN** FlowGuard SHALL project it as development-process context while OpenSpec remains the owner of its artifacts, checkboxes, strict verification, and archive

#### Scenario: Spec Kit package is consumed
- **WHEN** a Spec Kit project marker and feature artifacts are discovered inside the declared project root
- **THEN** FlowGuard SHALL read the feature specification, plan, tasks, and checklists without writing them or claiming provider completion

#### Scenario: Unbounded discovery is requested implicitly
- **WHEN** no explicit project or configured provider root authorizes discovery outside the current project
- **THEN** FlowGuard SHALL NOT scan the rest of the computer

### Requirement: Work-package identities are stable and plane-safe
Every work package SHALL distinguish `spec_provider_id`, `work_package_id`, `change_id`, task ids, obligation ids, check ids, and provider version, and SHALL remain owned by the `development_process` plane.

#### Scenario: Product behavior is referenced
- **WHEN** a work package targets a product-runtime commitment
- **THEN** it SHALL record a typed target relation and SHALL NOT copy or own the product commitment

#### Scenario: Parallel changes share task words
- **WHEN** two changes have similar task text
- **THEN** their provider/change/task identities SHALL remain distinct

### Requirement: Task and obligation reconciliation is bidirectionally complete
Every in-scope provider task SHALL map to FlowGuard obligations/checks or a typed scoped-out reason, and every in-scope obligation/check SHALL map back to a provider task or an infrastructure owner.

#### Scenario: Task has no FlowGuard mapping
- **WHEN** an in-scope behavior, implementation, or validation task has neither mapped obligations/checks nor a scoped-out reason
- **THEN** reconciliation SHALL report an unmapped-task blocker

#### Scenario: Obligation has no task or owner
- **WHEN** an in-scope obligation/check has neither a provider task nor an infrastructure owner
- **THEN** reconciliation SHALL report an unmapped-obligation blocker

#### Scenario: One receipt has several consumers
- **WHEN** several tasks or obligations consume one check receipt
- **THEN** the mappings SHALL fan out to the same receipt id without copying the receipt or creating duplicate primary owners

### Requirement: Canonical inputs and derived results are disjoint
The work-package verifier SHALL classify canonical governed inputs separately from derived results, reports, receipts, logs, caches, and temporary artifacts.

#### Scenario: Derived result is produced
- **WHEN** a check writes a receipt, verification report, JUnit file, log, cache, bytecode, temporary install, SkillGuard run/report/evidence file, or ordinary result file
- **THEN** that path SHALL NOT enter the same session's input fingerprint

#### Scenario: Canonical source changes
- **WHEN** a specification, source, model, test, prompt, canonical contract, config, declared tool, or schema identity changes
- **THEN** affected receipts and post snapshots SHALL become stale

### Requirement: Verification uses same-session begin and post snapshots
Every verification session SHALL bind one immutable begin input manifest and one immutable post input manifest before close or archive readiness.

#### Scenario: Inputs stay unchanged
- **WHEN** all checks finish and the post fingerprint equals the begin fingerprint
- **THEN** the session MAY close subject to terminal receipt and reconciliation gates

#### Scenario: A check or peer changes an input
- **WHEN** any canonical input changes after begin and before post
- **THEN** the session SHALL fail with changed-path evidence and SHALL NOT support close or archive

#### Scenario: Post snapshot is missing
- **WHEN** a run has only a begin snapshot, PID, heartbeat, or progress output
- **THEN** the session SHALL remain incomplete

### Requirement: Check receipts are immutable and exact
Each check receipt SHALL bind check definition, command, cwd token, governed input fingerprint, tool/schema/version, environment boundary, coverage ids, terminal result, exit code, output hashes, and begin/post session identity.

#### Scenario: Successful execution produces a receipt
- **WHEN** a check exits successfully, required terminal evidence is complete, and canonical inputs remain unchanged
- **THEN** FlowGuard SHALL store one immutable current receipt and report `executed`

#### Scenario: Progress pretends to be success
- **WHEN** evidence is running, progress-only, skipped, failed, timed out, ambiguous, lacks final status, or lacks complete coverage
- **THEN** it SHALL NOT produce or satisfy a reusable passing receipt

### Requirement: Reuse and deduplication are fail-closed
FlowGuard SHALL execute an identical current check key once and MAY reuse its immutable passing receipt only within the declared reuse boundary.

#### Scenario: Package-local receipt is current
- **WHEN** check identity, definition, command, input, tool/schema/version, environment, and coverage are unchanged inside one work package
- **THEN** FlowGuard MAY report `reused-current` without executing the command again

#### Scenario: Cross-change reuse is not declared
- **WHEN** another change requests an otherwise identical receipt but the check is not explicitly `cross_change_safe`
- **THEN** FlowGuard SHALL execute or block within that change rather than reuse implicitly

#### Scenario: Cross-change reuse is declared and exact
- **WHEN** an explicitly cross-change-safe check has identical current execution identity and complete coverage
- **THEN** several changes MAY reference the one receipt id through consumer-local portable refs, without copying the immutable receipt or reexecuting its owner

#### Scenario: One reuse-key field changes
- **WHEN** the check definition, inputs, tools, environment, coverage, or terminal receipt identity differs
- **THEN** the previous receipt SHALL be stale and the check SHALL rerun or remain blocked

### Requirement: Provider reports distinguish execution states
Canonical JSON output SHALL distinguish `executed`, `reused-current`, `stale`, `not-run`, and `blocked` with explicit reasons and SHALL remain language-neutral.

#### Scenario: Checkbox is complete without evidence
- **WHEN** a provider task is checked but its required obligation/check receipt is missing or stale
- **THEN** FlowGuard SHALL report the task as evidence-incomplete rather than complete

#### Scenario: Human-readable projection is requested
- **WHEN** a caller renders a localized explanation
- **THEN** localization MAY occur outside canonical identities and fingerprints and SHALL NOT alter machine evidence

### Requirement: Provider archive readiness is evidence-bound
FlowGuard SHALL block an archive-readiness projection when reconciliation, snapshots, receipts, peer-write freshness, or provider-native strict verification is incomplete.

#### Scenario: Archive prerequisites are complete
- **WHEN** mappings are complete, begin/post inputs match, required receipts are current, and provider-native strict verification passes
- **THEN** FlowGuard MAY project readiness back to the provider while the provider still owns archive

#### Scenario: Archive is attempted with a gap
- **WHEN** any task/obligation is unmapped, receipt is stale or missing, a peer write lacks revalidation, or post snapshot is absent
- **THEN** archive readiness SHALL be blocked
