## ADDED Requirements

### Requirement: TestMesh governs spec-check receipt children
TestMesh SHALL represent each required spec verification check as a child evidence owner with explicit consumers, execution status, reuse boundary, coverage, and freshness.

#### Scenario: Identical check has several consumers
- **WHEN** one current receipt satisfies several mapped tasks or obligations
- **THEN** TestMesh SHALL count one child execution and preserve all consumer references without duplicating evidence

#### Scenario: Unsafe cache hit is proposed
- **WHEN** a receipt lacks exact command/input/tool/environment/coverage identity or explicit cross-change permission
- **THEN** TestMesh SHALL report a reuse-proof blocker

### Requirement: TestMesh keeps spec-check states visible
Spec-check child evidence SHALL preserve `executed`, `reused-current`, `stale`, `not-run`, `blocked`, failed, skipped, timeout, and progress-only states.

#### Scenario: Parent summary is green with a hidden stale child
- **WHEN** any required child is stale, not-run, blocked, failed, skipped, timed out, or progress-only
- **THEN** the parent spec verification gate SHALL NOT claim current pass
