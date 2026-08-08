## MODIFIED Requirements

### Requirement: Satellite topology is derived from one canonical suite map
The retained `codex_skill_satellites` model SHALL derive kernel, public-satellite, and internal/delegated route identities, roles, required files, and reported counts from the current canonical suite map and current route registry. Source code, generated contracts, formal repository projection, shadow projection, clean consumer distribution, installed projection, package version, Git identity, tag, and release identity SHALL remain distinct evidence domains. A literal historical member count, including the former seven-satellite requirement, SHALL NOT act as topology authority.

#### Scenario: Canonical suite membership changes
- **WHEN** the suite map adds, removes, or changes a member role or required file
- **THEN** the model derives the new topology and invalidates prior contract, prompt, projection, installation, and release evidence without requiring a second count edit

#### Scenario: A fixed count disagrees with the suite map
- **WHEN** model code, a test, a prompt, or a specification asserts a literal member count that differs from the canonical suite map
- **THEN** the fixed-count surface is stale or invalid and cannot become a parallel authority

#### Scenario: Reserved skill is missing, extra, duplicated, or misclassified
- **WHEN** discovery finds a missing declared member, undeclared FlowGuard-reserved member, duplicate id, wrong kernel/satellite role, or an internal/helper route exposed as public
- **THEN** topology validation fails with the exact member identity

#### Scenario: Consumer includes author-control material
- **WHEN** a formal, shadow, or installed consumer projection contains SkillGuard author contracts, receipts, router state, or private maintenance files
- **THEN** clean consumer distribution and release readiness are blocked

#### Scenario: Suite model watches only itself
- **WHEN** suite-map, governed skills, contracts, suite code/scripts, distribution checks, or suite tests change while only the model and runner fingerprints remain unchanged
- **THEN** current suite-topology evidence is stale and the model SHALL NOT claim release readiness

### Requirement: Seven route-specific satellite skills are directly discoverable
The repository SHALL expose exactly the current public-satellite members declared by the canonical suite map. Discoverability SHALL be checked by member id and role rather than a hard-coded number or historical list.

#### Scenario: Clear route request invokes a satellite
- **WHEN** a request clearly matches a current suite-map member with role `public_owner`
- **THEN** Codex can invoke that satellite directly without requiring the kernel first
