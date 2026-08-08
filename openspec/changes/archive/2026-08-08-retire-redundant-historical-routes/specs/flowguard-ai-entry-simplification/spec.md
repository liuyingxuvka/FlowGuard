## ADDED Requirements

### Requirement: AI guidance records typed current-owner coverage questions
FlowGuard AI entry guidance SHALL ask what the selected current owners prove,
which exact state, branch, child, boundary, input, output, effect, finite case,
binding, or evidence item remains uncovered, and which current owner must close
that item. It SHALL record concrete coverage items rather than requiring a
free-form model-angle route or open-ended angle inventory.

#### Scenario: Agent starts non-trivial model-first work
- **WHEN** an agent starts a non-trivial feature, workflow, bug repair, prompt,
  process, or model change
- **THEN** compact guidance MUST expose the selected current owner closure and
  any exact typed coverage gaps
- **AND** every required gap MUST route to the affected owner and
  ModelMaturation without creating an independent deliberation row

#### Scenario: A possible blindspot is not yet typed
- **WHEN** the agent suspects the current model misses behavior but cannot map
  the concern to a current owner or coverage dimension
- **THEN** guidance MUST keep an explicit unknown-coverage item open for
  ExistingModelPreflight and ModelMaturation
- **AND** the unknown MUST NOT count as validation evidence or full
  understanding

### Requirement: Current owners consume bounded canonical relations
FlowGuard SHALL use exact canonical relations emitted by current blueprint,
behavior-commitment, or topology authority as bounded provenance for sibling,
shared-kernel, adapter, duplicate-boundary, evidence-scope, and false-friend
review. The relation SHALL feed the current decision owner and SHALL NOT become
a standalone similarity route, maintenance group, or completion gate.

#### Scenario: Related workflow surfaces are reviewed
- **WHEN** exact current authority relates workflow variants, shared kernels,
  adapters, duplicate boundaries, tests, or false-friend endpoints
- **THEN** the relation MUST preserve its source authority, endpoints,
  behavior plane, affected members, and currentness
- **AND** the relevant ExistingModelPreflight, ArchitectureReduction,
  CodeStructureRecommendation, ContractExhaustionMesh, or ModelTestAlignment
  owner MUST make and validate the downstream decision

#### Scenario: Shared wording is the only relation evidence
- **WHEN** surfaces merely share labels, filenames, tokens, or structural shape
  without an exact current canonical relation
- **THEN** AI entry guidance MUST keep the ownership or relation gap visible
- **AND** it MUST NOT invoke a free-form similarity search as a replacement

## MODIFIED Requirements

### Requirement: AI hot paths prefer structured handoff outputs
FlowGuard AI-facing hot paths SHALL instruct agents to read the structured
SummaryReport ledger, maintenance obligations, typed post-change owner
findings, and revalidation recommendations before manually inferring the next
route from prompt prose.

#### Scenario: Summary report has route-owned gaps
- **WHEN** an agent finishes a model-first check and the summary report has
  route-owned gaps
- **THEN** the hot-path guidance SHALL direct each typed finding immediately to
  its named current owner before broad confidence claims
- **AND** it SHALL NOT insert a maintenance-scan owner or plan between the
  finding and that owner

#### Scenario: No structured handoff is available
- **WHEN** a report lacks current structured owner and finding identities
- **THEN** the agent may use the compact route table only to identify a
  candidate owner
- **AND** the missing structured handoff remains a visible gap and MUST NOT be
  converted into a fallback success or validation result

## REMOVED Requirements

### Requirement: AI guidance asks open-ended model-angle questions
**Reason**: Requiring open-ended angle deliberation duplicates exact typed coverage gaps and can expand the prompt without proving another behavior boundary.
**Migration**: Record concrete current-owner coverage items and send unresolved items directly to ModelMaturation.

### Requirement: Existing similarity route remains the owner
**Reason**: Standalone Model Similarity ownership duplicates the observed blueprint, behavior-commitment, topology, and downstream decision owners.
**Migration**: Preserve bounded CanonicalRelation provenance while the current specialist owns every reuse, reduction, structure, case, or alignment decision.
