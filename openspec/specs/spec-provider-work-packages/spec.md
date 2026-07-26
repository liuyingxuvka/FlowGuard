# spec-provider-work-packages Specification

## Purpose
Define how FlowGuard consumes OpenSpec, Spec Kit, and other declared specification work packages while preserving provider authority, stable identities, bidirectional task/obligation reconciliation, exact receipt ownership, frozen-input freshness, and provider-native archive gates.
## Requirements
### Requirement: Provider work-package runtime remains retired
FlowGuard SHALL NOT expose a provider work-package runtime, compatibility
reader, session, cache, receipt bridge, task reconciliation authority, or
archive-readiness projection. Declared provider artifacts SHALL enter only
through the provider-neutral, read-only WorkContext capability.

#### Scenario: Retired work-package input is presented
- **WHEN** a caller presents a legacy provider work-package payload or asks
  FlowGuard to resume its session, receipt, reconciliation, or archive path
- **THEN** FlowGuard SHALL reject the retired surface and SHALL direct current
  planning input through a registered WorkContext adapter without fallback

