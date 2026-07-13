## Context

FlowGuard currently has strong local controls: model ownership, field
lifecycle, runtime-path evidence, ContractExhaustionMesh, TestMesh,
RiskEvidenceLedger, and the Primary Path Authority change. These controls can
still miss a broader problem: no single artifact says which external behaviors
the project promises to cover, which model owns each promise, and whether the
set is complete.

The user goal is not to add another old-path layer. The goal is to make AI
agents register the full behavior inventory first, then force each behavior
through one owner and one path when path-sensitive. This reduces hidden
alternate success paths, duplicate helpers, and unowned “small patches”.

## Goals / Non-Goals

**Goals:**

- Add a first-class Behavior Commitment Ledger API and skill.
- Define “behavior commitment” as an external, verifiable promise: a UI,
  CLI/API, skill, workflow, documentation, release, or process behavior that a
  user or downstream agent can rely on.
- Check ledger completeness from both directions: every source surface maps to
  commitments, and every commitment traces back to source evidence.
- Enforce one primary owner model per commitment, with supporting and child
  models clearly subordinate.
- Preserve explicit dependencies between commitments.
- Route `path_sensitive=true` commitments into Primary Path Authority and
  block ledger confidence when PPA blocks.
- Emit stable ids for RiskEvidenceLedger, ContractExhaustionMesh, TestMesh,
  and Model-Test Alignment.
- Provide enough docs and prompts that new FlowGuard use defaults to ledger
  registration.

**Non-Goals:**

- Do not treat every helper function, file, class, field, button, or model as a
  behavior commitment.
- Do not duplicate Primary Path Authority logic inside the ledger.
- Do not preserve legacy aliases, backup reads, or alternate runtime paths by
  default.
- Do not make task checkboxes count as validation evidence.

## Decisions

### 1. Ledger is upstream of PPA

The ledger owns the semantic question: “What behavior are we promising, and
which model owns it?” PPA owns the runtime path question: “For this
path-sensitive behavior, is there exactly one primary authority and no
alternate success?”

Alternative considered: put behavior registration inside PPA. That would make
non-path-sensitive behavior invisible and overload PPA with product-inventory
work. The ledger therefore records path sensitivity and consumes PPA evidence
rather than duplicating PPA checks.

### 2. Commitment is external behavior, not internal structure

A commitment is defined by observable actor, trigger, expected result, failure
boundary, source refs, and validation boundary. Internal helpers remain
implementation details unless they expose an external promise.

Alternative considered: make each model a feature. That collapses ownership
and behavior into one thing. It works for simple leaf models but fails for
larger workflows where one behavior is proven by multiple child models or
where one model supports several commitments.

### 3. Bidirectional coverage is mandatory

The review checks both “source surface without commitment” and “commitment
without source surface”. This is the practical way to catch missing behavior
and extra invented behavior.

Alternative considered: require only a list of commitments. That does not
prove the list covers the actual public surfaces.

### 4. One primary owner model

Each in-scope commitment has exactly one primary owner model. Other models can
be child or supporting models only. If ownership is unclear, the ledger blocks
broad confidence instead of allowing two models to overlap.

Alternative considered: allow several primary owners with shared
responsibility. That is exactly the ambiguity that tends to create hidden
alternate success paths and maintenance debt.

### 5. Scoped-out behavior must still be accountable

Old, removed, deferred, migration-only, and out-of-scope
behavior must record owner, reason, validation boundary, and rationale. This
prevents “not in this change” from becoming untracked behavior.

### 6. Coverage cases are generated from ledger axes

The ledger exposes canonical axes for commitment kind, surface kind, owner
state, source mapping, evidence state, path sensitivity, PPA result,
dependency state, and release gate state. ContractExhaustionMesh can use these
axes to generate finite cases; TestMesh can shard them.

## Risks / Trade-offs

- [Risk] Agents over-register tiny implementation details as commitments →
  Mitigation: skill and docs define commitments as external promises and
  explicitly exclude helper-level internals.
- [Risk] Ledger becomes stale after a change → Mitigation: DevelopmentProcess
  and RiskEvidenceLedger consume ledger freshness as a broad-claim gate.
- [Risk] PPA and ledger disagree about path-sensitive behavior → Mitigation:
  ledger stores PPA report ids/decisions and treats blocked PPA as blocked
  ledger coverage.
- [Risk] Existing projects lack a full baseline ledger → Mitigation: provide a
  template and skill for baseline creation, plus scoped-out rows with explicit
  reasons while adoption is incremental.
- [Risk] Full Cartesian coverage gets too large → Mitigation: expose axes and
  interaction groups so ContractExhaustionMesh/TestMesh can shard finite
  groups without letting progress-only evidence pass.

## Migration Plan

1. Add OpenSpec artifacts for the new capability and integrations.
2. Implement the ledger data model, review helper, text formatting, PPA bridge,
   and ContractExhaustionMesh projection.
3. Export the API and add a public template.
4. Add the FlowGuard skill and update existing skills to route broad behavior
   claims through it.
5. Add docs and tests for complete, missing, extra, overlap, scoped-out,
   dependency, path-sensitive, PPA-blocked, and release-gate cases.
6. Run focused tests, project audit, OpenSpec validation, and installation
   sync.

## Open Questions

- None blocking. The first implementation will support in-code ledger objects
  and template-based project files; future work can add a dedicated CLI loader
  if project teams want a persisted ledger format.
