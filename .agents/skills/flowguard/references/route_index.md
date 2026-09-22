# FlowGuard subject index

This is the only pre-selection material for the public skill. It identifies a
subject and lifecycle operation; it does not execute a check or create
evidence. The public operations are exactly `read`, `change`, and `release`.

## Decision rule

Extract structured task facts from the explicit request. Select one subject
from the rows below and one lifecycle operation. Zero matches are
`no_match`; contradictory or multiple subject matches are `conflict`. Keyword
similarity, declaration order, caller assertion, and an implicit “run
everything” request cannot resolve the decision.

## Domain subjects

| Subject | Reference directory | Use when |
| --- | --- | --- |
| existing-model | `references/domains/existing-model-preflight/protocol.md` | an existing model needs current ownership lookup |
| behavior-commitment | `references/domains/behavior-commitment-ledger/protocol.md` | external promises need source coverage and one owner |
| architecture-reduction | `references/domains/architecture-reduction/protocol.md` | modeled implementation may shrink without behavior change |
| code-structure | `references/domains/code-structure-recommendation/protocol.md` | a model must drive pre-code ownership |
| contract-exhaustion | `references/domains/contract-exhaustion-mesh/protocol.md` | a finite universe needs canonical bad cases or combinations |
| development-process | `references/domains/development-process-flow/protocol.md` | staged work, freshness, sync, or release matters |
| field-lifecycle | `references/domains/field-lifecycle-mesh/protocol.md` | fields, schemas, defaults, aliases, or replacements change |
| model-mesh | `references/domains/model-mesh/protocol.md` | topology crosses model boundaries or evidence is stale |
| model-miss | `references/domains/model-miss-review/protocol.md` | runtime or test evidence fails after a green model |
| model-test | `references/domains/model-test-alignment/protocol.md` | obligations, code contracts, and tests need comparison |
| topology-hazard | `references/domains/model-topology-hazard-review/protocol.md` | green topology needs anchored future-use hazard review |
| structure-mesh | `references/domains/structure-mesh/protocol.md` | an existing public surface needs parity-aware partitioning |
| test-mesh | `references/domains/test-mesh/protocol.md` | validation is large, stale, layered, or release-only |
| ui-flow | `references/domains/ui-flow-structure/protocol.md` | UI states, journeys, controls, or operability are in scope |

If no domain subject is clear, keep the subject as `model-first` and use the
core references for ordinary behavior/state modeling or cross-subject work.

## Loading boundary

Read only this index first. After one subject is selected, read its domain
`protocol.md` and the one detailed protocol named there. Load deeper references only when
that protocol names a concrete trigger. Domain files are reference material
inside the single public skill; they are not discoverable skills, aliases, or
forwarding entrypoints.
