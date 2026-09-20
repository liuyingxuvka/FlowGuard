# FieldLifecycleMesh Protocol

FieldLifecycleMesh gives field-heavy changes exact coverage without bloating the
main behavior model or leaving details as informal notes.

## Trigger

Use it when a task touches:

- payload, schema, API, config, prompt, persisted, UI, or runtime-state fields;
- additions, removals, renames, migrations, aliases, defaults, fallbacks,
  wrappers, or compatibility fields;
- bug repair rooted in a missing, stale, mis-projected, or old-field branch;
- replacement without explicit compatibility intent.

Skip only when no field, schema key, config flag, prompt/config field, persisted
attribute, payload column, or public field-like surface is in scope.

## Inputs

Collect:

- field boundary, independently discovered ids, immutable inventory
  revision/fingerprint, and discovery evidence;
- parent groups such as entity, payload, schema, config, entrypoint, or prompt;
- leaf rows for every discovered field;
- one owner, exact locations, role, lifecycle, behavior impacts, readers,
  writers, default semantics, absence/null semantics, serialization semantics,
  privacy classification, and content fingerprint;
- exactly one `modeled`, `delegated`, or `scoped` coverage disposition;
- projection rows for behavior-bearing fields;
- each field/group whose reader reaches an ordinary UI adapter, view model,
  display, text, or output boundary;
- old-field disposition and evidence refs for old, replaced, deprecated,
  alias, fallback, or compatibility-like fields.

## Parent And Leaf Shape

The parent stays small; leaf rows carry the full inventory. Put only routing,
state, permission, effect, schema, replay, migration, or external-contract
fields in the behavior model. Presentation/metadata fields may stay out when
their leaf rows say why.

FieldLifecycleMesh accounts fields and finds UI candidates; it does not decide
UI admission. Hand each ordinary-UI-readable field, or justified source-id
group, to `ui_flow_structure` regardless of source role. Do not force other
fields into a UI plan or add audience/role taxonomy here.

## Default Replacement Policy

If compatibility is not explicitly requested, old fields should not survive by
default. Valid closing dispositions are deleted, blocked, migrated, delegated to
the replacement field, same-contract repaired, explicitly preserved, or
out-of-scope with reason. Unknown disposition blocks full confidence.

Preservation requires compatibility intent and current evidence such as public
API, old-data migration, or promised-schema support.

## Handoffs

FieldLifecycleMesh does not prove behavior alone. Send:

- projections to Model-Test Alignment as obligations and owner code contracts;
- all ordinary-UI-reader candidates to UI Flow Structure as field ids or grouped source ids for `UIContentVisibilityPlan`; UI Flow Structure alone selects `user_visible`, `user_on_demand`, or `internal` and proves ordinary-surface behavior;
- reader/writer/owner maps to Code Structure Recommendation;
- old field disposition to Legacy Path Disposition and Architecture Reduction;
- field root cause ids and same-class field ids to Model-Miss Review;
- lifecycle, projection, replacement, and bug-repair closure artifacts to
  DevelopmentProcessFlow;
- current field lifecycle evidence to Closure Contract for broad claims.

## Completion Standard

A field lifecycle review is complete when:

- the independently frozen expected field set exactly equals the leaf-row set;
- every leaf row has one owner/location and explicit default, absence,
  serialization, privacy, and content-fingerprint semantics;
- every field has exactly one modeled/delegated/scoped disposition, with
  specialist owner/current native evidence for delegation or a bounded reason
  for scope;
- every behavior-bearing field has a projection or a scoped-out reason;
- every field whose reader reaches an ordinary UI boundary is handed to UI Flow Structure, while fields with no ordinary-UI reader remain internally accounted without UI rows;
- old/replaced/deprecated/compatibility-like fields have a closing disposition;
- downstream handoffs are named;
- stale field rows are blocked or rerun;
- full confidence is not claimed from inventory alone.

## Model-system revision binding

The observed snapshot binds the current inventory owner artifact, not a
free-form hash. A target/experiment keeps added, removed, renamed, migrated,
replaced, externalized, state-bearing, and side-effect fields in its candidate
snapshot. Every field/effect diff enters the revision's affected closure with
one owner and old-field disposition. Unaccounted fields block activation;
rollback needs evidenced restore, compensation, or irreversible forward repair.

When triggered, emit a current-evidence maturation contribution for field
inventory, lifecycle, projections, dispositions, readers/writers, and gaps.
This route owns semantics; the compiler only unions coverage.
