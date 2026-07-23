## ADDED Requirements

### Requirement: Project adoption audits model authority
Project adoption SHALL validate the sole observed-head pointer, immutable
snapshot fingerprint, snapshot subject revision, and declared coverage status
in addition to package, schema, skill-suite, and rendered project records.

#### Scenario: Package versions match but snapshot is stale
- **WHEN** source, installed package, and project record versions match but the observed snapshot names another software revision
- **THEN** project audit fails model-authority parity and does not claim current FlowGuard confidence

### Requirement: Version identities are never conflated
Project adoption SHALL report source, project record, installed package,
installed skills, snapshot, Git commit, tag, and release identities separately.

#### Scenario: A historical folder has an older project record
- **WHEN** an inactive historical checkout retains an older record
- **THEN** audit reports that checkout as historical or stale without treating it as the active installed authority
