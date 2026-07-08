## ADDED Requirements

### Requirement: Architecture reduction disposes fallback surfaces
ArchitectureReduction SHALL classify old paths, aliases, wrappers, helper
routes, compatibility facades, and fallback candidates that overlap a primary
business intent and require a target action before broad confidence.

#### Scenario: Silent runtime fallback requires removal or blocking
- **WHEN** an architecture candidate can run as an alternate implementation
  after primary failure
- **THEN** ArchitectureReduction SHALL classify it as a silent runtime fallback
  or equivalent blocking surface

#### Scenario: Public facade delegates to primary
- **WHEN** a public compatibility facade remains in scope
- **THEN** ArchitectureReduction SHALL require evidence that it delegates to
  the primary path and does not own business behavior
