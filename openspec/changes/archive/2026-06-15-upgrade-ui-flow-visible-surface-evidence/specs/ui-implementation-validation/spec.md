## ADDED Requirements

### Requirement: UI evidence declares evidence kind
UI implementation validation SHALL allow render and implementation evidence to
declare the kind of evidence used for a runnable UI claim, including screenshot,
browser click-through, DOM text, computed style, geometry, accessibility or
ARIA, runtime trace, log, test result, and manual observation evidence.

#### Scenario: Screenshot evidence is accepted
- **WHEN** implementation validation records screenshot evidence for a visible
  UI surface
- **THEN** the evidence kind is accepted as a normal UI evidence type

#### Scenario: Evidence without kind is rejected
- **WHEN** implementation validation records render or implementation evidence
  without an evidence kind
- **THEN** the implementation evidence review reports the evidence as missing a
  declared kind

#### Scenario: Unknown evidence kind is rejected
- **WHEN** implementation validation records an evidence kind outside the
  supported UI evidence kind list
- **THEN** the implementation evidence review reports the evidence kind as
  unknown

### Requirement: Render evidence remains bound to UI model context
UI render evidence SHALL identify the source interaction model, implementation
target, evidence target, result, evidence reference, and model or
implementation revision before supporting a runnable UI completion claim.

#### Scenario: Render evidence names model context
- **WHEN** render evidence supports an implemented UI claim
- **THEN** it records the source UI interaction model, implementation target,
  evidence target, evidence reference, result, and current revision

#### Scenario: Stale render evidence is rejected
- **WHEN** render evidence references a model or implementation revision that
  differs from the current validation revision
- **THEN** the implementation evidence review reports stale render evidence
