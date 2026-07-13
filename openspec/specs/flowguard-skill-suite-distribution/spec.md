# flowguard-skill-suite-distribution Specification

## Purpose
This capability defines how FlowGuard is distributed and explained as an
AI-agent skill suite, including the `.agents/skills/` primary surface, default
entry skill, executable check-script role, and local installed-skill sync
evidence needed before claiming active agent behavior is current.

## Requirements
### Requirement: FlowGuard is distributed as an AI-agent skill suite
FlowGuard public onboarding SHALL present `.agents/skills/` as the primary
AI-agent install and read surface.

#### Scenario: Agent reads public onboarding
- **WHEN** an AI agent reads the README or project integration guide
- **THEN** it MUST learn that complete agent setup means access to
  `AGENTS.md` and every FlowGuard `SKILL.md` under `.agents/skills/`
- **AND** it MUST NOT treat Python package installation as the skill install
  surface

#### Scenario: Default skill entry is visible
- **WHEN** an AI agent loads the FlowGuard skill suite
- **THEN** `model-first-function-flow` MUST be identified as the default
  entrypoint
- **AND** sibling FlowGuard skills MUST be described as part of the same suite

### Requirement: Executable checks are presented as skill-attached scripts
FlowGuard documentation SHALL describe executable checks as scripts or check
engine support for the skills rather than as the primary installation product.

#### Scenario: User needs executable evidence
- **WHEN** a user or agent needs to run FlowGuard checks
- **THEN** the docs MUST route to local check scripts, examples, or
  `python -m flowguard` compatibility commands as execution paths
- **AND** those commands MUST be described as check execution, not as the
  FlowGuard skill installation

### Requirement: Local active behavior requires installed skill sync
FlowGuard SHALL verify local installed AI-agent skill content after repository
skill guidance changes before claiming that active local AI behavior is
synchronized.

#### Scenario: Repository skill wording changes
- **WHEN** repository-managed FlowGuard skill files change
- **THEN** local installed Codex skill copies MUST be refreshed or reported as
  unsynced
- **AND** verification MUST compare guidance markers from the affected skill
  files rather than relying only on package version or directory existence

### Requirement: Canonical suite validation supports ownership-backed mixed roots
FlowGuard suite validation SHALL distinguish the canonical FlowGuard suite
from unrelated skills co-located in the same skill root only when a supported
official distribution ownership manifest proves the exact canonical member
boundary. It MUST continue to require exactly seventeen declared FlowGuard
members and every required member file.

#### Scenario: Official suite is co-located with unrelated skills
- **WHEN** the ownership manifest names exactly the seventeen declared
  FlowGuard members and owns each member's `SKILL.md`
- **AND** all seventeen canonical member directories and required files exist
- **AND** additional non-FlowGuard skill directories also contain
  `SKILL.md`
- **THEN** suite validation passes
- **AND** it reports seventeen declared and seventeen discovered suite members
- **AND** it reports the unrelated directories separately as co-located skills

#### Scenario: Mixed root lacks valid ownership evidence
- **WHEN** undeclared skill directories exist
- **AND** the ownership manifest is missing, unsupported, incomplete, or does
  not name exactly the declared suite
- **THEN** validation retains strict reverse discovery
- **AND** the undeclared directories produce `extra_discovered_member`
  findings

#### Scenario: Undeclared FlowGuard-like skill is present
- **WHEN** a valid ownership manifest exists
- **AND** an undeclared skill id uses a FlowGuard-reserved id or prefix
- **THEN** validation reports that id as `extra_discovered_member`
- **AND** the suite remains blocked

#### Scenario: Canonical member is missing from a mixed root
- **WHEN** a valid ownership manifest exists
- **AND** any declared FlowGuard member directory or required file is missing
- **THEN** validation reports the existing missing-member or missing-file
  finding
- **AND** co-located skills do not satisfy or hide the missing obligation

### Requirement: Mixed-root reports preserve foreign-skill visibility
FlowGuard suite reports SHALL expose allowed co-located skill ids separately
from canonical discovered member ids and SHALL state that those skills were not
validated by the FlowGuard suite check.

#### Scenario: JSON report contains co-located skills
- **WHEN** ownership-backed mixed-root validation succeeds
- **THEN** the JSON report includes the co-located skill ids
- **AND** its claim boundary states that unrelated skills are outside the
  FlowGuard suite validation claim
