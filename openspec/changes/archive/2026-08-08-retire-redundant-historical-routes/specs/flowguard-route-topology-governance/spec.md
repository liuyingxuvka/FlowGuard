## ADDED Requirements

### Requirement: Retired routes are removed after responsibility reattachment
Route topology governance SHALL remove an intentionally retired route only after every still-required admission, transition, negative case, and completion obligation is attached to exactly one current route owner.

#### Scenario: Route protection has been migrated
- **WHEN** every retained protection has a current owner and executable evidence
- **THEN** the retired node and all incoming/outgoing current relations are absent from the route declaration and generated topology

#### Scenario: Retired route remains reachable
- **WHEN** any public profile, handoff, template, prompt, CLI, or generated topology still reaches the retired route
- **THEN** topology validation blocks closure as a dangling or duplicate route owner
