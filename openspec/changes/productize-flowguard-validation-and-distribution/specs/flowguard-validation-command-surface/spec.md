## ADDED Requirements

### Requirement: Canonical Validation Result Model
Every productized validation command SHALL construct one canonical result containing status, scope/tier, counts, evidence, failures, blockers, skipped checks with reasons, residual risk, claim boundary, progress summary, and artifact references. Human and JSON output MUST project the same result semantics.

#### Scenario: JSON output is requested
- **WHEN** a validation command runs with `--json`
- **THEN** it emits encoding-stable machine-readable output with no localized-only field names or human preamble

### Requirement: Concise Default And Full Trace Access
Default human output SHALL present the final status, counts, first actionable failures, blockers, and artifact locations without printing complete traces. `--full` or referenced artifacts SHALL preserve complete trace access without changing the status decision.

#### Scenario: Self-review produces large traces
- **WHEN** the full trace exceeds the concise-output threshold
- **THEN** default output summarizes it and provides the full artifact path or explicit `--full` route

### Requirement: Composable Exit And Status Semantics
Exit codes and status values SHALL distinguish pass, fail, blocked, invalid input, timeout/cancelled, and internal error. Partial/scoped/pass-with-gaps results MUST NOT return the same broad-success semantics used by full pass.

#### Scenario: Required check is not run
- **WHEN** a full validation command has a required `not_run` check
- **THEN** it returns non-success full status and a nonzero closure exit code

### Requirement: Unified Suite Validation Entrypoint
The repository SHALL expose a documented command that composes project audit, suite inventory, seventeen SkillGuard checks, evidence-bound self-governance, model regression, tests, OpenSpec verification, and distribution parity while preserving each child result and receipt.

#### Scenario: One child validation fails
- **WHEN** distribution parity fails but all other children pass
- **THEN** the unified result reports the parity child failure and blocks full/release closure
