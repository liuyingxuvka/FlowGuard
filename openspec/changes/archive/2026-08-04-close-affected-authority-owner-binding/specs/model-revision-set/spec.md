## ADDED Requirements

### Requirement: Affected native-owner routes consume explicit semantic model evidence
For every native owner route present in the exact affected revision closure, the
revision evidence plan SHALL declare exactly one explicit binding to one or more
existing semantic model children. Missing, duplicate, foreign, or unmaterialized
bindings SHALL block before native-owner evidence is written. The system SHALL
NOT assign an unknown route to a generic, similarly named, or run-all fallback
model.

#### Scenario: Affected inventory route has no semantic model binding
- **WHEN** the exact affected closure contains an authority-inventory route that is absent from the frozen owner-to-model binding plan
- **THEN** revision-owner evidence generation SHALL stop without publishing a bundle
- **AND** the finding SHALL name the unmapped route

#### Scenario: Every affected route has one current binding
- **WHEN** every route in the exact affected closure has one unique explicit binding whose model children exist in the candidate, full manifest, and exact-current full parent
- **THEN** each native owner MAY compose only those exact child receipts needed by its semantic binding and referenced changed-model closure

#### Scenario: A new affected identity category has no native route
- **WHEN** the derived revision closure contains an affected identity outside the explicitly classified model-relation, root, coverage, unresolved-gap, system-property, or typed endpoint categories
- **THEN** closure derivation SHALL fail with the exact unclassified affected identity
- **AND** the identity SHALL NOT be assigned to ModelMesh or another generic owner
