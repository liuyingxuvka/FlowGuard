# flowguard-maintenance-hardening Specification

## Purpose
Define the evidence gates for claiming FlowGuard maintenance complete, including
project audit, OpenSpec validation, model and unit regression evidence, editable
install checks, shadow workspace synchronization, release alignment, and
peer-safe sync behavior.
## Requirements
### Requirement: Maintenance hardening release closure
FlowGuard maintenance hardening SHALL require current evidence for tracked source, local model artifacts, shadow workspace sync, editable install source, OpenSpec validation, local regression, GitHub CI, and GitHub Release alignment before claiming the maintenance release complete.

#### Scenario: Full closure claim
- **WHEN** a maintenance hardening release is claimed complete
- **THEN** the evidence set includes OpenSpec strict validation, project audit, full unit regression, aggregate FlowGuard model regression, shadow import/version verification, local editable install source verification, clean git status, pushed tag, GitHub Release, and successful GitHub CI for the released commit

### Requirement: No peer-work mirror deletion
Shadow workspace synchronization SHALL default to copying current source sets without deleting unrelated shadow-only files.

#### Scenario: Shadow-only file exists
- **WHEN** the shadow sync helper runs without an explicit destructive mode
- **THEN** files present only in the shadow workspace remain present after synchronization
