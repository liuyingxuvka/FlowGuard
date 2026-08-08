## MODIFIED Requirements

### Requirement: Project documents carry exact intent authority
The strict project blueprint document SHALL carry the complete typed intent inventory used by behavior, resource, and readiness review, including source kind, source and owner identity, expectation identity, target bindings, current fingerprints, provider capability, terminal disposition, the independently observed complete model-owner denominator, and any evidence-bound no-intent rationale. Loading the document SHALL rederive and verify the canonical intent-review fingerprint. Adding the required model-owner denominator SHALL advance both the intent-inventory schema and the enclosing project-document schema; the loader SHALL reject the former parent or child schema rather than reinterpret it, infer the denominator, or invoke a compatibility reader.

#### Scenario: Intent is supplied only beside the project document
- **WHEN** a caller supplies intent rows as an optional runtime argument but the strict project document does not contain them
- **THEN** whole-project qualification SHALL remain incomplete or reject the non-current document
- **AND** the optional argument SHALL NOT become a second intent authority

#### Scenario: Former project document omits the model-owner denominator
- **WHEN** a document uses the former project-document schema or embeds the former intent-inventory schema without `required_model_target_ids`
- **THEN** strict loading fails visibly before project qualification
- **AND** the loader SHALL NOT infer the denominator from the contributions, behaviors, manifest, or a root fallback

#### Scenario: Current project document round-trips exact intent ownership
- **WHEN** a current document embeds intent-inventory v5 and the complete required model-owner denominator
- **THEN** strict loading rederives the same intent-review, inventory, and enclosing document fingerprints
- **AND** every model-owner identity remains explicit after round-trip serialization
