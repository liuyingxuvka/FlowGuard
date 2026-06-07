## ADDED Requirements

### Requirement: Similarity relation provenance
Architecture Reduction SHALL be able to consume model-similarity relations as
candidate provenance for duplicate-boundary, adapter-only, shared-kernel, and
duplicate-validation contraction candidates.

#### Scenario: Similarity relation feeds reduction candidate
- **WHEN** an Architecture Reduction candidate cites a model-similarity
  relation that identifies duplicate ownership or adapter-only difference
- **THEN** the review includes the relation id as candidate provenance while
  still requiring observable architecture contract coverage

#### Scenario: Similarity code obligation feeds reduction candidate
- **WHEN** an Architecture Reduction candidate is motivated by a
  duplicate-boundary or adapter-only model-similarity obligation
- **THEN** the candidate records the code obligation id as provenance while
  Architecture Reduction still owns the contraction readiness decision

#### Scenario: Similarity is not proof by itself
- **WHEN** a reduction candidate only cites a similarity relation and lacks
  safe equivalence, public facade, conformance, or validation-boundary evidence
- **THEN** the review does not report the candidate as ready
