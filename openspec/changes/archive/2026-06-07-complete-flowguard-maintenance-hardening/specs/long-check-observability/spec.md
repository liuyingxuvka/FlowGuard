## ADDED Requirements

### Requirement: Aggregate local model regression runner
FlowGuard SHALL provide a tracked command that discovers present `.flowguard/**/run_checks.py` files, runs them, and reports every runner's status before returning a failing exit code for any failed runner.

#### Scenario: One local runner fails
- **WHEN** the aggregate model regression command encounters a runner with non-zero exit status
- **THEN** the command reports the failed runner path and exits non-zero

#### Scenario: All local runners pass
- **WHEN** every discovered local runner exits zero
- **THEN** the command reports the runner count and exits zero

### Requirement: Deep validation lane
FlowGuard CI SHALL keep fast push validation separate from deep manual or scheduled validation that can run full unit tests and aggregate model regressions without slowing ordinary pushes.

#### Scenario: Push validation
- **WHEN** a commit is pushed to `main`
- **THEN** the fast validation lane runs install, project audit, OpenSpec strict validation, self-maintenance model checks, and focused tests

#### Scenario: Manual deep validation
- **WHEN** a maintainer runs the workflow manually with deep validation enabled
- **THEN** the deep lane runs full unit tests and aggregate model regressions

