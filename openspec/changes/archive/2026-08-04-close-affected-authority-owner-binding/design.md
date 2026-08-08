## Context

See `proposal.md` for motivation. The current revision-owner evidence assembler
already blocks missing mappings and independently verifies exact model-child
receipts. Its frozen mapping covers five routes, while the current real affected
closure contains a sixth route, `affected_authority_inventory`. A route-universe
audit also exposes the inventory root's latent `authoritative_model_system`
route. These routes are emitted by the model-system inventory builder for the
inventory root and the source, runtime, and test endpoints that it governs.

## Goals / Non-Goals

**Goals:**

- Close the real sixth route with one explicit existing semantic owner.
- Turn the production miss into a repeatable exact-coverage regression.
- Keep the model, OpenSpec requirement, native evidence mapping, and test oracle
  aligned.

**Non-Goals:**

- Add a new model, product mode, reconstruction path, language adapter, or
  compatibility reader.
- Replace affected-only evidence with a global run-all shortcut.
- Edit the already archived parent change.

## Decisions

### Bind both inventory routes to `authoritative_model_system`

The inventory is loaded inside the model-system snapshot compiler and owns both
its root identity and the source, runtime, and test endpoints it contributes.
The existing `authoritative_model_system` model is therefore the semantic owner
of both routes. Binding them to every component's target model would blur the
distinction between the inventory's integrity and the behavior models it
references; creating a new model would duplicate authority.

### Keep the mapping exact and fail closed

The existing explicit tuple remains the sole owner-to-model plan. Generation
derives both the complete candidate route universe and the actual affected
routes independently. Unknown routes continue to block. The repair adds two
rows and a production-shaped route-universe test; it does not add inference by
name, a default mapping, or wildcard coverage.

The affected-closure builder also replaces its former unknown-id-to-ModelMesh
fallback with a finite classification. Model relations, model roots, coverage
rows, unresolved gaps, and system properties are explicitly ModelMesh-owned;
typed endpoints use the route stored in the candidate snapshot. Any other
affected identity is an unclassified contract change and blocks by exact id.

The production-shaped owner-binding test is also a declared input of the
existing `model_maturation_loop` model. Changing that shared test therefore
re-fingerprints the model-maturation relations in the final candidate even
though this repair does not change maturation behavior. The combined intent
inventory records those exact downstream effects under this repair, names the
existing maturation model as a consumer, and does not create another intent
owner or another maturation requirement.

### Model the miss in FlowGuard itself

The authoritative model-system state gains one condition stating that every
affected native-owner route has an explicit semantic model binding. A known-bad
scenario turns that condition off and must violate the revision-generation
invariant. This makes the repair part of FlowGuard's own living model rather
than only an implementation table.

## Risks / Trade-offs

- **A later snapshot producer introduces another owner route** → The exact-set
  regression and generation-time mapping check block and name that route; a new
  semantic decision is required instead of fallback.
- **A later diff producer introduces an entirely new affected-id category** →
  The closure builder blocks before owner planning until that category receives
  an explicit native route.
- **The route is bound to too broad a model** → Exact referenced changed-model
  closure remains additive, while the base semantic owner is limited to the
  existing authoritative model-system model.
- **Post-archive work loses intent lineage** → This change receives its own
  OpenSpec artifacts and intent contribution; the prior archive remains
  immutable and both contributions are reviewed against the final candidate.

## Migration Plan

Add the two direct-current mappings, tests, and model scenario; synchronize the
two delta requirements; generate a current combined intent inventory; validate
and archive this small change. The release workflow then rebuilds the model
parent, native-owner evidence, revision set, and observed authority from the
archived intent artifact. There is no persisted legacy format or compatibility
migration.
