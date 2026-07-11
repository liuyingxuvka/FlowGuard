## ADDED Requirements

### Requirement: Text hierarchy consumes approved content
The UI Text Hierarchy Blueprint SHALL create visible text elements only from approved `user_visible` content or `user_on_demand` content in a state reached by its explicit reveal event. Internal and unclassified content SHALL NOT gain visibility through text ownership, hierarchy, typography, or rationale fields.

#### Scenario: Internal metadata has a text owner
- **WHEN** internal metadata is assigned a text role, state, region, priority, or typography token
- **THEN** the text hierarchy review blocks the item because text ownership does not grant display admission

#### Scenario: Optional detail remains quiet until requested
- **WHEN** explanation or detailed status is classified `user_on_demand`
- **THEN** the blueprint keeps it absent from the default hierarchy and includes it only in the revealed-state hierarchy
