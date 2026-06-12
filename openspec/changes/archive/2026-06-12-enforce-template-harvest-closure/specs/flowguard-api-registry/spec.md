## ADDED Requirements

### Requirement: Public API exposes harvest closure helpers
FlowGuard SHALL expose template harvest closure helpers through the
`risk_template_library` route-scoped API and starter API surfaces.

#### Scenario: API registry is inspected
- **WHEN** a consumer inspects route-scoped APIs
- **THEN** `RISK_TEMPLATE_LIBRARY_API` includes `TemplateHarvestReview` and `review_template_harvest_closure`

#### Scenario: Starter API is inspected
- **WHEN** an AI consumer reads `ROUTE_STARTER_API["risk_template_library"]`
- **THEN** it includes the helper needed to review harvest closure before final claims
