## ADDED Requirements

### Requirement: Latest-schema artifact upgrade
FlowGuard SHALL provide a deterministic upgrade review for older FlowGuard
artifacts, project records, reports, model evidence, docs, tests, and guidance
so recognized old shapes can be converted to the current schema without adding
long-lived runtime compatibility branches.

#### Scenario: Known old artifact upgrades to current shape
- **WHEN** an upgrade scan encounters a FlowGuard artifact with a known older
  field, alias, or record shape
- **THEN** the upgrade report records the original path, detected old shape,
  current replacement, and whether the item was changed
- **AND** the upgraded output uses the current schema and current route-first
  field names

#### Scenario: Unknown old artifact blocks instead of guessing
- **WHEN** an upgrade scan encounters an old or unsupported FlowGuard shape
  without a deterministic migration rule
- **THEN** the upgrade report marks the item as blocked or manual-review
  required
- **AND** FlowGuard does not claim the artifact was upgraded

#### Scenario: Runtime path remains current-only
- **WHEN** current FlowGuard route review or report code executes after an
  upgrade scan
- **THEN** it consumes current-schema artifacts and current public API shapes
- **AND** it does not accept old fields solely for backward compatibility

### Requirement: Upgrade apply is explicit and evidence-bearing
FlowGuard SHALL distinguish dry-run upgrade scans from write-applying upgrades,
and applied upgrades MUST leave enough receipt metadata for a human or agent to
understand what changed.

#### Scenario: Dry-run does not write files
- **WHEN** the artifact upgrade command runs without apply mode
- **THEN** it reports planned upgrades, unchanged items, skipped items, and
  blocked items
- **AND** it does not modify target files

#### Scenario: Apply writes only deterministic changes
- **WHEN** the artifact upgrade command runs in apply mode
- **THEN** it writes only deterministic upgrades with known replacement rules
- **AND** it reports changed file paths and any blocked paths separately

#### Scenario: Upgrade report does not replace validation
- **WHEN** an upgrade report has no blocked items
- **THEN** the report still states that affected model checks, tests, replay,
  and route-owner evidence may need rerun before broad confidence is claimed

### Requirement: Script upgrades are conservative
FlowGuard SHALL treat Python model and test scripts as behavior-bearing files
and MUST NOT rewrite them unless a deterministic, syntax-light replacement rule
is available.

#### Scenario: Known API alias is replaced
- **WHEN** a script contains a known obsolete FlowGuard API alias with a current
  replacement
- **THEN** the upgrade report may classify the edit as deterministic and
  apply it in apply mode

#### Scenario: Behavior-bearing script is ambiguous
- **WHEN** a script appears to depend on an old FlowGuard behavior but no safe
  replacement rule is registered
- **THEN** the upgrade report marks the script for manual or route-owner review
- **AND** it does not silently rewrite the behavior
