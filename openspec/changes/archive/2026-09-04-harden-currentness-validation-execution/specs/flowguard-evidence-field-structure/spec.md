## MODIFIED Requirements

### Requirement: Lightweight evidence gate structures
FlowGuard SHALL provide one current lightweight evidence gate and detail shape
for broad evidence models. Duplicate legacy input concepts, removed flat gate
fields, old AutoSplit process metrics, and strict-adapter fixture-only fields
MUST be rejected by current constructors and APIs rather than converted,
defaulted, aliased, or accepted as a second success path.

#### Scenario: Risk evidence gates can be grouped
- **WHEN** a risk evidence row needs model, test, family, or analogous-scan gate
  state
- **THEN** that state is represented by the current reusable gate object and
  removed flat gate fields are rejected

#### Scenario: Process evidence details can be grouped
- **WHEN** process evidence includes command status, background status, or mesh
  split status
- **THEN** that state is represented by the focused current detail object and
  old AutoSplit metrics are rejected

#### Scenario: Strict adapter fixture fields reach a public constructor
- **WHEN** a test-owned strict-adapter fixture field is supplied to the current
  plan-intake or evidence API
- **THEN** validation rejects it instead of retaining production compatibility

## REMOVED Requirements

### Requirement: Compatibility conversion is explicit
**Reason**: Current runtime uses direct replacement and removed evidence fields
must not remain accepted through compatibility conversion.

**Migration**: Historical artifacts may be inspected by bounded upgrade owners,
but every current caller must construct the latest lightweight gate and detail
shapes directly.
