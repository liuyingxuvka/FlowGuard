## ADDED Requirements

### Requirement: Native member resume is explicit execution with exact-current reuse
The native-skill validation command SHALL expose an explicit resume operation that independently verifies every candidate member receipt and reuses it only when the receipt is terminal pass, full scope, and exact-current for the declared member inputs. Every missing, stale, failed, timed-out, blocked, partial, or unverifiable member SHALL execute its one declared owner or remain visibly non-pass.

#### Scenario: Identical native member is reused
- **WHEN** a member has an independently verified terminal-pass full receipt whose command, obligations, contract, manifest, suite inventory, declared inputs, producer, toolchain, environment, proof, and result identities all match the current invocation
- **THEN** resume SHALL report that member as `reuse_current` and SHALL NOT execute its native commands again

#### Scenario: One declared input changes
- **WHEN** any declared native command input or producer source differs from the receipt-bound snapshot
- **THEN** resume SHALL execute that member's declared owner and SHALL NOT reuse the stale receipt

#### Scenario: Resume has no fallback
- **WHEN** a candidate receipt is damaged, ambiguous, non-terminal, non-pass, partial, or cannot be verified against current inputs
- **THEN** the command SHALL NOT select an older schema, alternate store, compatibility reader, alias, or inferred success

### Requirement: Native receipts bind the complete declared input set
Each native member receipt SHALL bind every declared native command and exact path selector, the receipt producer sources, the compiled contract, check manifest, suite inventory, covered obligations, toolchain, environment, proof artifact, and result identity used by that member.

#### Scenario: Later declared command is part of currentness
- **WHEN** a member declares more than one native command
- **THEN** files selected by every command SHALL participate in the receipt's exact-current verification rather than only files selected by the first command

#### Scenario: Declared input set changes
- **WHEN** the recomputed current input artifact set is not exactly the receipt-bound artifact set
- **THEN** the receipt SHALL be ineligible for reuse even if all common files retain matching hashes

### Requirement: Native execution accounting remains visible
The native command's terminal report SHALL separately expose requested, passed, executed, and reused member counts and SHALL preserve the disposition and receipt identity for every selected member.

#### Scenario: Mixed execute and reuse
- **WHEN** some selected members have exact-current receipts and others are missing or stale
- **THEN** the terminal report SHALL distinguish the reused members from the executed members and SHALL retain every non-pass member result
