## ADDED Requirements

### Requirement: UI-boundary fields hand off to content admission
FieldLifecycleMesh SHALL keep every discovered field in the leaf inventory and SHALL hand every field or grouped field id whose reader reaches an ordinary UI adapter, view model, display, text, or output boundary to UI Flow Structure as UI candidate content, regardless of whether the source field role is presentation, metadata, state, permission, or another role. FieldLifecycleMesh SHALL NOT decide the final UI visibility class and SHALL NOT require fields with no ordinary-UI reader to enter the UI content plan.

#### Scenario: Field reaches the UI boundary
- **WHEN** any field has a reader that can place its value or state on an ordinary user surface
- **THEN** the field lifecycle handoff names the field or field group as UI candidate content for UI Flow Structure classification

#### Scenario: Internal field has no UI reader
- **WHEN** an internal audit, model, test, or diagnostic field remains outside the UI adapter/view-model/output boundary
- **THEN** FieldLifecycleMesh keeps it accounted internally without creating a UI content-admission row
