## ADDED Requirements

### Requirement: Similarity-driven family evidence
Model-Test Alignment SHALL be able to consume same-family-variant and
evidence-duplicate model-similarity relations when a broad same-class claim
depends on sibling model obligations or shared mechanism evidence.

#### Scenario: Family variant requires sibling evidence
- **WHEN** a model-test alignment plan claims a same-class family and cites a
  same-family-variant similarity relation
- **THEN** the review requires current evidence for each in-scope family member
  or a scoped/exempt rationale for members outside the current claim

#### Scenario: Maintenance group requires shared and variant test obligations
- **WHEN** a model-test alignment plan claims coverage for a similarity
  maintenance group
- **THEN** the plan records shared and variant test obligation ids or equivalent
  obligation-family evidence before claiming the similar workflows are covered

#### Scenario: Evidence duplicate cannot overclaim coverage
- **WHEN** two model obligations cite the same evidence through an
  evidence-duplicate similarity relation
- **THEN** the review accepts the evidence only for obligations whose external
  contract, mechanism, provenance, and freshness match the evidence scope
