# contract-audit-evidence Specification

## Purpose
TBD - created by archiving change add-contract-audit-evidence. Update Purpose after archive.
## Requirements
### Requirement: Conservative Python code contract audit
The system SHALL provide a conservative Python source audit layer that can read
real Python code ASTs and generate or validate code-contract evidence for
externally visible code surfaces.

#### Scenario: Supported external code surface
- **WHEN** the audit finds a declared public function, class, method, CLI
  handler, facade, adapter, or persisted-output writer whose AST-visible inputs,
  outputs, state access, side effects, and error paths support a declared
  `CodeContract`
- **THEN** it records code-contract evidence that can be passed to
  Model-Test Alignment with the source path, symbol, supported fields, and any
  remaining confidence boundaries

#### Scenario: Missing or unsupported code contract
- **WHEN** a required `CodeContract` points to a missing symbol or its
  AST-visible behavior does not support required external inputs, outputs, state
  reads, state writes, side effects, or error paths
- **THEN** the audit reports a missing, unsupported, or partial code-contract
  evidence finding instead of treating the declaration as proven

#### Scenario: Dynamic code requires manual review
- **WHEN** contract support depends on dynamic imports, reflection,
  monkeypatching, generated attributes, framework lifecycle hooks, concurrency,
  external services, or runtime values that the AST audit cannot conservatively
  inspect
- **THEN** the audit marks the relevant contract evidence as ambiguous or
  manual-review-required

### Requirement: Conservative Python test assertion audit
The system SHALL provide a conservative Python test audit layer that can read
real Python test ASTs and generate or validate test assertion evidence for
external code contracts.

#### Scenario: External contract assertion evidence
- **WHEN** a real Python test contains AST-visible assertions, expected
  exceptions, output checks, call checks, state checks, or persisted-output
  checks against the declared external code surface
- **THEN** the audit records `TestEvidence` with assertion scope
  `external_contract` or `mixed`, covered code-contract ids when available, and
  the assertion features that support the claim

#### Scenario: Internal path only
- **WHEN** a test invokes or asserts only private helpers, internal branches, or
  implementation details while claiming coverage for an external code contract
- **THEN** the audit records the evidence as `internal_path` or partial and
  Model-Test Alignment must not count it as full external-contract evidence

#### Scenario: Non-passing evidence remains a gap
- **WHEN** a test has AST-visible assertions but its execution evidence is
  skipped, stale, failed, timeout, not-run, running, or error
- **THEN** the audit keeps the assertion evidence visible but Model-Test
  Alignment treats it as a coverage gap for the current decision

### Requirement: Audited evidence feeds Model-Test Alignment
The system SHALL feed audited code-contract and test-assertion evidence into
the existing Model-Test Alignment review so model obligations, code contracts,
and test evidence can be compared together.

#### Scenario: Three-way alignment from audited evidence
- **WHEN** audited `CodeContract` evidence and audited `TestEvidence` rows are
  available for model-backed behavior
- **THEN** Model-Test Alignment compares them with the declared
  `ModelObligation` rows and reports missing, mismatched, stale, orphan,
  duplicate, internal-only, extra-behavior, and unknown-reference findings

#### Scenario: Audit does not replace declared obligations
- **WHEN** AST audit discovers candidate code or test behavior without a
  matching declared model obligation or reviewer-approved binding
- **THEN** the behavior is reported as a candidate, orphan, or manual-review
  item rather than silently expanding model scope

### Requirement: Audit limitations are explicit
The system SHALL explicitly report that conservative source audit is not a
perfect Python semantic proof, not a replacement for conformance replay, and not
sufficient for complex behavior without manual review.

#### Scenario: Conformance-sensitive behavior
- **WHEN** the coverage claim depends on production state, durable side effects,
  external systems, trace-level behavior, or adapter projection between model
  traces and real code
- **THEN** source audit evidence may support the claim but MUST NOT replace
  conformance replay or equivalent production-facing validation

#### Scenario: Complex behavior
- **WHEN** source or test behavior is too complex for conservative AST evidence
  to establish external-contract support
- **THEN** the audit requires manual review and the final report preserves that
  limitation as a confidence boundary
