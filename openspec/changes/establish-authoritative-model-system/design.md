## Context

FlowGuard 0.60.0 already contains strong local owners: ModelMesh governs
hierarchy, Behavior Commitment Ledger governs externally promised behavior,
FieldLifecycleMesh governs field ownership, Model-Test Alignment and TestMesh
govern verification, task-local revisions preserve one base/candidate pair, and
DevelopmentProcessFlow governs staged work. The missing piece is a thin,
persisted project join across those owners.

Today the regression manifest is a runner registry. Most entries identify only
their model and runner source files, every instance id is expressed as a mutable
`:current` label, and evidence records glob expressions rather than the exact
resolved inputs. Existing Model Preflight can mark a discovered file or ledger
hit as current without proving that it belongs to the software revision being
discussed. None of those facts is sufficient to identify the whole current
software model.

This repository is also maintained by concurrent AI agents. The implementation
therefore uses an isolated worktree, preserves foreign changes, and activates
authority only through immutable artifacts and a compare-and-swap pointer.

## Goals / Non-Goals

**Goals:**

- Answer “what exact model system describes the software now?” with one
  verifiable observed-head snapshot.
- Keep observed, target, and experimental systems visibly separate.
- Define “full coverage” only against a declared finite and fingerprinted
  universe.
- Replace one or many affected models as a single transaction.
- Preserve a usable return path to the old observed system, with honest limits
  for irreversible implementation effects.
- Reuse and connect existing FlowGuard owners rather than create a parallel
  governance framework.
- Remove only duplication whose observable equivalence and ownership are
  proven.

**Non-Goals:**

- Claim that an unbounded or unknown software universe is completely modeled.
- Make a target model current merely because its checks pass.
- Let ModelMesh take over commitment, field, test, process, or source-control
  semantics.
- Promise byte-for-byte operational rollback when data or external effects are
  irreversible.
- Rewrite all large modules in one release without parity evidence.

## Decisions

### 1. One immutable snapshot format, three subject lanes

`ModelSystemSnapshot` is the thin persisted join. Every snapshot declares one
subject lane:

- `observed_implementation`: evidence-backed description of a concrete software
  revision;
- `normative_target`: a desired replacement that is not current;
- `counterfactual_experiment`: an isolated what-if model that is not current.

Lifecycle (`candidate`, `active`, `historical`, `retired`) is independent of
subject lane. Authority is derived from the project pointer and content
fingerprints, never from an editable boolean or a `:current` suffix.

Alternative rejected: adding only a role field to individual manifest entries.
That cannot express whole-system closure, multi-model atomicity, or one observed
head.

### 2. The project manifest owns the sole observed-head pointer

`.flowguard/project.toml` gains one `[model_authority]` pointer to an immutable,
content-addressed snapshot under
`.flowguard/model-mesh/snapshots/<fingerprint>.json`. There is no second
`CURRENT.json` file and no fallback discovery path.

Activation uses compare-and-swap:

1. validate the expected old head;
2. persist the candidate snapshot and decision evidence;
3. persist an activation receipt;
4. update the project pointer last.

Base drift blocks activation. A target snapshot is never relabelled as observed;
after implementation, a new observed snapshot is built and linked with
`realizes` and `supersedes`.

### 3. Exact model instance identity replaces mutable names

Each `ModelInstanceRef` binds:

- stable logical model id and model kind;
- model path and content hash;
- runner path and content hash;
- purpose-closure hash;
- subject source revision;
- exact resolved input inventory and inventory hash.

The regression registry keeps human-readable model ids, but execution receipts
refer to the immutable instance fingerprint. Glob patterns may select inputs;
the evidence must store the resolved paths and hashes.

### 4. Typed relations connect owners without merging them

The project snapshot supports only declared typed edges: `contains`, `refines`,
`depends_on`, `delegates_to`, `consumes`, `produces_for`, `realizes`,
`supersedes`, `validates`, and `shares_kernel_with`. An equivalence or shared
kernel relation does not itself authorize deletion or evidence reuse.

Snapshot members reference commitment ids, field/side-effect inventory ids,
code-contract ids, test/evidence ids, and parent closure ids. The original
owner still validates each referenced object.

### 5. Coverage is a finite set-equality proof

`CoverageUniverse` freezes independently enumerated required ids for:

- user-visible API, CLI, UI, schema/file, skill/agent, and documented surfaces;
- active behavior commitments;
- required model instances and system properties;
- behavior-bearing fields, state, and side effects;
- code contracts;
- tests and evidence obligations.

A snapshot can claim `complete_within_declared_boundary` only when required ids
equal covered ids in every dimension and all referenced evidence is fresh.
Unknown, excluded, stale, and not-run rows remain visible. “Full software
coverage” without this finite boundary is invalid.

### 6. Revision sets generalize the existing task-local lifecycle

`ModelRevisionSet` reuses the existing propose, validate, accept, reject, and
rollback state machine but owns one or more member changes. One-model work is a
one-member revision set. Members cannot be independently accepted.

The revision set freezes:

- task/change id and expected observed-head fingerprint;
- base and candidate snapshot fingerprints;
- add/replace/remove members with exact base/candidate identities;
- changed relation, commitment, field, side-effect, system-property, contract,
  and test ids;
- affected closure hash;
- required prediction, replay, and evidence refs;
- implementation bundle and rollback contract refs;
- aggregate status and reason.

### 7. Three different return operations remain distinct

- Before code change: reject/discard an experiment.
- Before code change after target acceptance: withdraw or supersede the target.
- After implementation/deployment: restore code/config/data/external effects or
  execute declared compensation, rerun conformance for the old observed
  snapshot, then move the pointer.

If the observed head has advanced, the operation becomes a new forward revision.
If an irreversible effect lacks a validated compensation contract, exact
rollback is blocked and the claim must say so.

### 8. Existing Model Preflight resolves authority before relevance

Preflight first loads and validates the observed-head snapshot, then selects
same-plane owners from its active members. Replaced/retired commitments and
non-member discovered files cannot be primary current evidence. Lexical scan
remains a candidate discovery aid and is labelled non-authoritative.

### 9. Architecture reduction is evidence-led and incremental

This release removes the manifest-era compatibility runner discovery and
centralizes duplicated package-owned suite/version vocabulary where parity is
straightforward. Oversized public modules are registered as StructureMesh split
targets, but a split occurs only when facade, dependency, and parity evidence
is complete. Distinct semantic owners are not collapsed merely because helpers
look similar.

### 10. Installation and release identities stay separate

The release gate records and compares:

- source commit and package version;
- project adoption record;
- observed model-system snapshot;
- author skill source;
- SkillGuard maintenance receipt;
- installed consumer skill projection;
- installed Python distribution;
- Git tag and GitHub Release.

A clean project audit proves adoption/version reconciliation only. Model,
test, installation, and release evidence remain separate required gates.

## Architecture Contraction Disposition

This release performs only contractions whose ownership and observable parity
can be proved now:

- split the authority schema, revision-set state machine, durable store, and
  project-manifest persistence into separate owners;
- centralize package-owned suite/version vocabulary;
- remove obsolete compatibility runner discovery and the unowned
  `lightweight_model_miss_review` registration.

The following remain visible StructureMesh review targets rather than being
silently folded into this change:

- `hierarchy.py`, with a possible later evidence/closure split behind its
  existing facade;
- `existing_model_preflight.py`, with a possible later discovery adapter split;
- the `model_test_alignment` source-cycle candidate;
- the `self_maintenance`/`route_topology` cycle candidate;
- `__init__.py`, which is intentionally retained as a public facade and is not
  considered defective from line count alone.

No deferred target is release work until a model-derived partition, single
owner per partition, dependency/config safety, and public parity evidence are
current. This keeps contraction from becoming unrelated architectural churn.

## Risks / Trade-offs

- **Initial coverage inventory exposes many gaps** → ship an honest bounded
  baseline and block broad completeness language until every dimension closes.
- **Snapshot files can become large** → use canonical JSON and
  content-addressing; keep owner details in their native artifacts and store
  references rather than copies.
- **Concurrent source changes can stale a candidate** → compare-and-swap the
  observed head and hash resolved inputs; rebuild instead of silently merging.
- **Operational rollback may be impossible** → require explicit
  restore/compensate/irreversible dispositions and never claim exact rollback
  without executed evidence.
- **Removing compatibility discovery can reveal undeclared local runners** →
  require explicit manifest registration and fail visibly.
- **Broad module splitting could destabilize the public API** → separate
  proof-ready contraction from registered future StructureMesh targets and
  preserve one facade.

## Migration Plan

1. Add strict snapshot, coverage, relation, revision-set, and activation receipt
   schemas plus canonical fingerprints.
2. Add one project model-authority section and bootstrap the release's observed
   v0.61 snapshot from the registered model inventory, claiming completeness
   only inside its explicit fingerprinted coverage boundary.
3. Update regression evidence to bind exact resolved inputs and immutable model
   instance fingerprints.
4. Update preflight and owner lookups to resolve observed authority first.
5. Add atomic candidate validation, activation, target withdrawal, and
   operational rollback gates.
6. Connect existing owner artifacts through typed refs and add their focused
   model/test evidence.
7. Remove proof-ready duplicate/compatibility control surfaces; register larger
   split targets for later parity-governed contraction.
8. Freeze the source snapshot, run one all-model owner and one full-test owner,
   then use the latest available SkillGuard to maintain and install the skill
   projection.
9. Install the Python package and skills, verify source/install/project/snapshot
   parity, then tag and publish the release.

If deployment validation fails, restore the previously installed package and
consumer skill projection. The source branch and immutable candidate artifacts
remain available for diagnosis; the observed-head pointer does not move unless
its activation gates pass.
