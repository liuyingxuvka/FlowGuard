## ADDED Requirements

### Requirement: Skill kernel keeps template library compact
The FlowGuard skill kernel SHALL expose risk-template reuse as a compact
pre/post model gate without moving the full template-library protocol into the
first-read skill body.

#### Scenario: Kernel first read stays compact
- **WHEN** the model-first skill kernel is read
- **THEN** it states the minimum valuable model gate and template search/harvest rule without embedding long public template catalogs

#### Scenario: Detailed protocol remains referenced
- **WHEN** an agent needs implementation detail for template library behavior
- **THEN** the kernel points to route docs, helpers, or CLI commands rather than expanding every field inline
