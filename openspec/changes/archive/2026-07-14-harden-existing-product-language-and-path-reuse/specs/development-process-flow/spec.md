## ADDED Requirements

### Requirement: Post-change scans gate lifecycle completion
DevelopmentProcessFlow SHALL consume a post-change owner scan after non-trivial
changes to stable business-intent inventories, behavior commitments, primary
paths, UI consistency models, materialized obligations, tests, public exports,
skills, templates, or synchronization artifacts. The scan SHALL preserve
changed artifacts, peer writes, skipped routes, stale evidence, open
obligations, and split or reduction signals, and SHALL route each unresolved
item to its existing owner before broad lifecycle confidence.

#### Scenario: Post-change scan finds stale owner evidence
- **WHEN** the post-change scan finds that a changed artifact invalidates
  Primary Path Authority, UI Flow Structure, Model-Test Alignment, TestMesh,
  install, shadow, formal-repository, or Git evidence
- **THEN** DevelopmentProcessFlow MUST derive the minimum owner-route
  revalidation and MUST NOT treat the prior evidence as current

#### Scenario: Required post-change scan is missing
- **WHEN** non-trivial work claims done, release, archive, publish, or full
  confidence without a current post-change scan for the changed artifacts
- **THEN** DevelopmentProcessFlow MUST report missing required revalidation and
  block the broad process claim

#### Scenario: Scan output is not pass evidence
- **WHEN** a post-change scan reports no new route recommendation but the
  required validation or synchronization receipts are absent
- **THEN** DevelopmentProcessFlow MUST treat the scan as routing input only and
  MUST NOT manufacture a passing validation result

#### Scenario: Background regression is visible but not terminal
- **WHEN** the post-change scan sees background regression progress without a
  current final TestMesh receipt
- **THEN** DevelopmentProcessFlow MUST preserve the run as liveness only and
  keep the associated completion gate unsatisfied

### Requirement: Synchronization domains have independent freshness gates
DevelopmentProcessFlow SHALL track repository source, editable or installed
package and skill state, shadow workspace, formal repository, and local Git
state as distinct freshness domains. Evidence from one domain MUST NOT stand in
for another domain, and a broad claim SHALL consume a current receipt for each
in-scope domain or preserve an explicit scoped boundary.

#### Scenario: Install evidence does not prove shadow or formal parity
- **WHEN** editable-install or installed-skill evidence is current but shadow
  workspace or formal-repository evidence is missing or stale
- **THEN** DevelopmentProcessFlow MUST report the missing synchronization gate
  instead of treating install success as cross-domain parity

#### Scenario: Shadow evidence does not prove local Git closure
- **WHEN** shadow-workspace validation passes but local Git evidence does not
  identify the current intended files and revision state
- **THEN** DevelopmentProcessFlow MUST keep local Git closure unsupported

#### Scenario: One synchronization domain changes after its receipt
- **WHEN** a package, installed skill, shadow copy, formal repository, or local
  Git artifact changes after that domain's receipt was produced
- **THEN** DevelopmentProcessFlow MUST stale that receipt and every dependent
  downstream claim while preserving unrelated current domain evidence

#### Scenario: All required synchronization receipts are current
- **WHEN** every in-scope install, shadow, formal-repository, and local Git gate
  has a current passing receipt for the same intended source revision
- **THEN** DevelopmentProcessFlow MAY treat synchronization freshness as
  satisfied without using one receipt as a proxy for another

### Requirement: Peer writes invalidate evidence without authorizing rollback
DevelopmentProcessFlow SHALL treat peer-agent or unknown-writer changes as
freshness events. It MUST preserve the current peer-written state, re-read and
merge against that state when work continues, and MUST NOT restore, overwrite,
or roll back peer work merely to recover an earlier green receipt.

#### Scenario: Peer writes after validation
- **WHEN** a peer or unknown writer changes an artifact after validation or
  synchronization evidence was produced
- **THEN** DevelopmentProcessFlow MUST mark the affected evidence stale and
  require validation against the current artifact state

#### Scenario: Earlier snapshot would restore green evidence
- **WHEN** restoring an earlier local snapshot would make an old receipt appear
  current but would discard peer-written content
- **THEN** DevelopmentProcessFlow MUST reject that rollback path and preserve
  the peer-written content

#### Scenario: Peer overlap cannot be merged safely
- **WHEN** current peer changes overlap the intended edit and the correct merge
  cannot be established from current evidence
- **THEN** DevelopmentProcessFlow MUST block the affected action or require
  human resolution rather than overwriting either side

