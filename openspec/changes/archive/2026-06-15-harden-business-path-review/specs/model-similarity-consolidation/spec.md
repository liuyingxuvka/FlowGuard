## ADDED Requirements

### Requirement: Business path identity participates in similarity classification
Model similarity consolidation SHALL compare business path ids, intents, and
expected terminals when classifying sibling models, adapters, shared kernels,
duplicate candidates, and false friends.

#### Scenario: Shared business path exposes duplicate candidate
- **WHEN** two model signatures share a business path id or intent and also share material state writes or side effects
- **THEN** the similarity result records business-path overlap as evidence for duplicate, adapter, shared-kernel, or maintenance-group review

#### Scenario: Similar names but different terminal expose false friend
- **WHEN** two model signatures look related by name but their business path terminals conflict
- **THEN** the similarity result records business-path divergence as evidence against unsafe consolidation

### Requirement: Business path evidence appears in similarity output
Model similarity output SHALL expose the business path overlap and divergence
that influenced relation classification.

#### Scenario: Similarity report names path evidence
- **WHEN** a similarity pair is classified using business path ids, intents, or terminals
- **THEN** the returned evidence lists those path elements so the user can see why the relation was selected
