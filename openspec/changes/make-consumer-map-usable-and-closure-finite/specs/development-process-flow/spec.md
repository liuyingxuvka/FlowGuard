## MODIFIED Requirements

### Requirement: Routine and release lifecycle scopes are distinct

FlowGuard SHALL distinguish routine local-functional confidence from release
confidence. A local validation claim MAY defer release-tree, installation,
shadow-workspace, and remote evidence visibly, while a release claim MUST have
the exact release-required evidence. Pointer/activation/report metadata SHALL
not reopen a local functional claim when its selected functional inputs remain
unchanged.

#### Scenario: Routine local scope defers release evidence
- **WHEN** a `local_validation` claim has its affected functional evidence
  current and release-required evidence pending
- **THEN** FlowGuard allows the local claim while reporting release obligations
  as `not_requested` or `not_run`
- **AND** it does not build a release tree or run release producers

#### Scenario: Release scope requires release evidence
- **WHEN** a `release` claim lacks current release-required evidence
- **THEN** FlowGuard blocks release confidence
- **AND** it does not relabel a local parent receipt as a release receipt

#### Scenario: Pointer-only commit preserves local scope
- **WHEN** an accepted candidate is bound to a new authority pointer after local
  functional validation and no selected functional input changes
- **THEN** local validation remains current after one binding check
- **AND** no functional producer or release-tree scan is started

#### Scenario: Local functional input changes
- **WHEN** a selected code, model, contract, oracle, or necessary dependency
  changes
- **THEN** only the affected local owner closure becomes stale and is
  revalidated before a new local claim
- **AND** unrelated local owners remain eligible for exact reuse

#### Scenario: Local claim is explicitly promoted to release
- **WHEN** a caller requests a `release` claim for an otherwise current local
  result
- **THEN** FlowGuard binds the existing local functional evidence to a fresh
  exact release tree/install identity
- **AND** missing release evidence remains a visible release blocker rather
  than triggering repeated functional execution

### Requirement: Release convergence is target-neutral and finite

The same release-consumer and finite-convergence rules SHALL apply when
FlowGuard verifies an ordinary external software project. The target SHALL
provide its own version, tag, source/assets policy, and functional checks;
FlowGuard's installed package identity SHALL remain verifier provenance only.

#### Scenario: External target uses a different version and tool
- **WHEN** an ordinary target declares version `1.2.3` and is checked by FlowGuard `0.69.0`
- **THEN** the target's explicit descriptor and functional parent are verified
- **AND** the verifier does not require FlowGuard metadata or an editable FlowGuard installation inside the target root

#### Scenario: Candidate is promoted to tag and publication
- **WHEN** a target-local candidate receipt is current
- **THEN** tag and published phases consume that immutable candidate receipt
- **AND** they do not start a second functional producer or recompute a different candidate
