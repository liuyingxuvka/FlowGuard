## ADDED Requirements

### Requirement: Similarity evidence in full preflight
Full Existing Model Preflight SHALL be able to consume current model-similarity
relations before deciding to reuse, extend, add a child model, create a family
variant, extract a shared kernel, route to Architecture Reduction, or keep a
new boundary separate.

#### Scenario: Similarity relation supports reuse decision
- **WHEN** a full preflight includes a current model-similarity relation that
  recommends reuse or extension of an existing model boundary
- **THEN** the preflight review may use that relation as reuse rationale while
  preserving the downstream route requirements

#### Scenario: Required similarity evidence is missing
- **WHEN** a full preflight declares that model similarity review is required
  for the boundary decision but does not include current similarity relation
  evidence
- **THEN** the preflight review reports a blocking similarity-evidence finding

#### Scenario: False friend keeps boundaries separate
- **WHEN** a full preflight includes a false-friend model-similarity relation
- **THEN** the preflight may keep the proposed boundary separate only if the
  false-friend rationale remains visible in the report

#### Scenario: Similarity maintenance group preserves sibling review
- **WHEN** a full preflight includes model-similarity relations for a changed
  workflow that belongs to a maintenance group
- **THEN** the preflight records the maintenance group ids, change-impact ids,
  and impacted sibling model ids before claiming the existing boundary review
  covered all similar workflows
