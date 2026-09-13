## Purpose

Provide one public authoring route for proving that discovered implementation
surfaces and target model obligations form an exact bidirectional closure,
including UI-like actions and finite dynamic dispatch boundaries.

## ADDED Requirements

### Requirement: Reverse authoring uses one independent denominator

The reverse-surface template MUST reuse the existing discovery, shard, merge,
authoring-context, semantic-map, current-owner-authority, and audit
implementations. It MUST require an independent implementation denominator,
exact component groups, a target-owned obligation denominator, implementation
to model and model to implementation exact joins, owner/test/receipt/authority
joins, UI-like action joins, and persistent owner receipts.

#### Scenario: Complete reverse map is authored

- **WHEN** the discovered surface set, model-obligation set, owner receipts,
  and both join directions are equal and current
- **THEN** the audit can report reverse closure complete

#### Scenario: One-way mapping is authored

- **WHEN** a surface points to an obligation that does not point back, or a
  model obligation has no mapped surface
- **THEN** the audit blocks with a one-way or orphan finding

### Requirement: Completion cannot retain unresolved observations

Discovery MAY emit typed unresolved observations for dynamic, plugin,
receiver, callback, or ambiguous dispatch, but graduation/current authority
MUST have zero `blocked_gap`, unmapped, orphan, one-way, unmodeled UI-like,
dynamic, ambiguous, or unknown completion findings. Each such case MUST
either have a finite exact dispatch map or a deterministic external boundary.

#### Scenario: Dynamic observation is unresolved during discovery

- **WHEN** a callback target cannot yet be proved
- **THEN** discovery records a typed observation and keeps graduation blocked

#### Scenario: Dynamic observation receives a finite map

- **WHEN** every possible target is declared with exact identity and current
  evidence
- **THEN** the observation is resolved and no unresolved completion finding
  remains

### Requirement: Reverse receipts cannot impersonate other authorities

Reverse scaffold receipts MUST be owned by the reverse-surface route and MUST
NOT be used as Behavior Commitment Ledger, Model-Test Alignment, UI
operability, target-model, or release receipts. Those boundaries MAY join by
exact IDs only.

#### Scenario: Reverse receipt is presented as a target test receipt

- **WHEN** a reverse receipt lacks the target test owner and subject identity
- **THEN** the consuming check blocks with an authority-join finding
