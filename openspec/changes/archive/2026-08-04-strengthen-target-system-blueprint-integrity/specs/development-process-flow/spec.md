## ADDED Requirements

### Requirement: Development validates affected owners before one frozen final gate
During implementation, DevelopmentProcessFlow SHALL execute or reuse only exact affected validation owners and SHALL keep unknown impact blocked. After all governed source, OpenSpec, model authority, SkillGuard projection, installation, version, and documentation inputs are frozen, exactly one owner SHALL run the final full gate.

#### Scenario: Focused diagnostics can run independently
- **WHEN** several focused diagnostics have isolated inputs, mutable state, side effects, and execution owners
- **THEN** they MAY run in safe parallel before source freeze
- **AND** later edits SHALL invalidate only evidence that consumes changed identities

#### Scenario: Final gate is interrupted
- **WHEN** the final owner times out, is cancelled, or is interrupted
- **THEN** its evidence SHALL be non-reusable until the entire descendant process tree is confirmed absent
- **AND** no unattended resume or second owner SHALL start from the mutable snapshot

### Requirement: Peer changes are preserved and selectively integrated
DevelopmentProcessFlow SHALL re-read concurrent or unknown-writer changes, preserve them, and stale only affected evidence. It SHALL NOT reset, overwrite, or discard peer work to restore an older green state.

#### Scenario: Peer edits an overlapping governed file
- **WHEN** another agent changes a file in the current integration boundary
- **THEN** the integration owner SHALL re-read and deliberately merge or block that file
- **AND** unrelated work SHALL continue without repository rollback

### Requirement: Release identities close in fixed order
OpenSpec verification, main-spec sync and archive, observed-model acceptance, SkillGuard source/consumer closure, local package and skill installation parity, version and changelog finalization, and cleanup review SHALL finish before the frozen final gate. Commit, immutable patch tag, push, and GitHub Release SHALL follow only a terminal passing gate.

#### Scenario: OpenSpec archive changes governed source
- **WHEN** an earlier full result predates the final archived OpenSpec tree
- **THEN** that result SHALL be stale for release
- **AND** the final gate SHALL consume the archived frozen tree

### Requirement: Blueprint lifecycle uses the exact affected owner closure
DevelopmentProcessFlow SHALL track implementation inventory, binding, resource, intent, test, topology, projection, and static-closure freshness as distinct identities. Ordinary changes SHALL revalidate only their exact affected owner closure; an explicit whole-blueprint or release obligation SHALL assemble the complete canonical owner set.

#### Scenario: Ordinary implementation changes one blueprint shard
- **WHEN** a changed file invalidates one inventory or binding shard
- **THEN** the process revalidates the affected owner closure without materializing unrelated whole-project layers

#### Scenario: A whole-blueprint claim is explicit
- **WHEN** the task explicitly requires whole-target blueprint qualification
- **THEN** the process assembles the canonical complete owner plan and preserves every child status and gap

## MODIFIED Requirements

### Requirement: Blueprint layers and distribution identities have independent freshness
DevelopmentProcessFlow SHALL track blueprint definition, implementation inventory, intent lineage, semantic evidence, model-code-test bindings, test inventory, resource/oracle closure, source tree, installed package, installed skill projection, repository commit, tag, and release as distinct versioned artifacts. A passing or current identity in one domain SHALL NOT fill another domain.

#### Scenario: Installed package is current but consumer skills are stale
- **WHEN** editable package parity passes and one affected installed skill differs from its frozen source projection
- **THEN** installation synchronization remains incomplete
- **AND** source, Git, tag, and release status are reported separately

#### Scenario: Static blueprint changes after qualification
- **WHEN** a consumed model, semantic source, implementation surface, test node, resource, oracle, intent contribution, or project definition changes
- **THEN** only the exact affected blueprint neighborhood and its consumers become stale
- **AND** unrelated current evidence MAY be reused when its identity remains exact

## REMOVED Requirements

### Requirement: Blueprint qualification and empirical reconstruction have separate lifecycle owners
**Reason**: The empirical product lane has been retired; blueprint sufficiency is owned by the canonical layered readiness result and exact affected owner lifecycle.

**Migration**: Use the exact affected owner closure for ordinary work and the canonical complete owner plan for explicit whole-blueprint claims.

### Requirement: Reconstruction remains optional and never starts from lifecycle continuation
**Reason**: Retaining a permanently idle lifecycle branch added process and prompt complexity without contributing to blueprint depth.

**Migration**: Use the canonical blueprint layers, test evidence, and readiness gaps. A separately authorized experiment, if ever needed, is an ordinary external task and has no FlowGuard product-status authority.
