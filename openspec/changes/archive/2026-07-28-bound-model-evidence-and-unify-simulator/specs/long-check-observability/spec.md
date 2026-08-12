## MODIFIED Requirements

### Requirement: Background checks record durable evidence
FlowGuard skill guidance SHALL require long-running background checks to record complete stdout and stderr, terminal exit status, metadata, and result artifacts by default. Complete streams MAY be retained as deterministic compressed content-addressed objects with bounded human-readable tails; guidance MUST NOT require redundant raw, combined, and parsed full-payload copies when the compressed objects are verifiable and recoverable.

#### Scenario: Long check is run in the background
- **WHEN** an agent runs a long FlowGuard check outside the foreground session
- **THEN** the agent records complete stdout/stderr object descriptors, exit status, metadata, and the terminal result under a declared evidence root

#### Scenario: Compressed stream is used
- **WHEN** complete stdout or stderr is retained as a compressed object
- **THEN** its descriptor records logical hash and size, storage hash and size, compression, and recoverable object path
