# post-runtime-model-miss-review Delta

## ADDED Requirements

### Requirement: Model-miss review can derive family sibling bad cases

Post-runtime model-miss review SHALL be able to use obligation-family declarations to derive same-class sibling bad cases from an observed family-member miss.

#### Scenario: Observed miss creates sibling obligations
- **WHEN** a model miss is assigned to an obligation family member
- **AND** the family has other required members sharing the same mechanism
- **THEN** FlowGuard can derive sibling same-class bad cases for those members before the repair is broadly closed.

#### Scenario: Observed-only closure remains scoped
- **WHEN** only the observed failure case has evidence
- **AND** sibling same-class bad cases have not been generated or scoped out with reasons
- **THEN** model-miss closure remains scoped rather than full family confidence.

### Requirement: Model-miss review scans analogous defect radius

Post-runtime model-miss review SHALL ask where the same failure shape may recur and record dispositions for mandatory same-family siblings before broad closure.

#### Scenario: Same-family sibling is mandatory scan radius
- **WHEN** a model miss belongs to an obligation family member
- **AND** another required member shares the failed mechanism
- **THEN** FlowGuard treats that sibling as a must-scan analogous defect candidate.

#### Scenario: Open analogous candidate blocks full closure
- **WHEN** a must-scan candidate is unreviewed, marked repair-now, or marked model-upgrade-needed
- **THEN** full model-miss closure remains blocked until the candidate is repaired, covered by current evidence, or explicitly moved to a separate scoped change.

#### Scenario: Related surfaces remain visible without endless expansion
- **WHEN** a related surface is outside the direct family but has the same abstract failure shape
- **THEN** FlowGuard may record it as should-scan or record-only
- **AND** a concrete separate-change or exclusion reason keeps the current claim scoped rather than silently broad.
