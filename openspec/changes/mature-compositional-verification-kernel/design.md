## Context

FlowGuard's executable core is deliberately Pythonic: a `FunctionBlock` implements `Input x State -> Set(Output x State)`, and the explorer, scenario, loop, progress, hierarchy, and conformance modules inspect the resulting state graph. This is effective for authoring but it leaves no canonical, code-independent representation that another process can validate and execute. Existing mesh records describe ownership and closure, while existing progress checks consume Python callables; neither is a portable semantic artifact.

The implementation must remain finite, dependency-light, deterministic, latest-schema-first, and compatible with the existing Python authoring API. It must not become an application data model, a visual editor backend, a generalized theorem prover, or a compatibility framework for arbitrary historical schemas.

## Goals / Non-Goals

**Goals:**

- Give finite FlowGuard behavior one canonical JSON semantic form with stable content identity.
- Execute that form through a small reference interpreter without importing project code.
- Check safety, eventuality, bounded eventuality, weak-fairness declarations, and parent/child refinement with actionable traces.
- Make assume/guarantee compatibility explicit and machine-checkable.
- Expose one narrow public Python/CLI surface and align the affected skills with it.

**Non-Goals:**

- Serialize arbitrary Python objects, predicates, or side effects.
- Replace the existing `FunctionBlock`, scenario, formal-runner, or project-specific model authoring APIs.
- Prove infinite-state programs, recover production truth, or infer abstraction mappings automatically.
- Add product UI, persistence, deletion, relationship management, or future-application workflow responsibilities.
- Read older or alternate portable schemas in normal runtime.

## Decisions

### 1. Use an explicit finite transition-system IR

`PortableModel` contains stable state ids with JSON payloads, input symbols, output symbols, explicit transitions, initial/terminal states, invariants, temporal obligations, and contract tokens. Transitions directly encode the set-valued function-block relation by grouping on `(source_state, input_symbol)`.

This is preferred over serializing Python callables because it is portable, reviewable, and deterministic. It is preferred over a general expression language because a new evaluator would increase security and semantic ambiguity. Projection from arbitrary Python models remains explicit: callers enumerate the finite graph they intend to publish.

### 2. Canonical JSON is the sole portable authority

The schema id is `flowguard.portable_model.v1`. Canonical serialization uses UTF-8 JSON with sorted keys and stable compact separators; SHA-256 over those bytes is the portable identity. Unknown fields, duplicate ids, non-JSON values, dangling references, and a non-current schema fail closed. There is no alias, dual reader, or silent downgrade.

### 3. Separate structural validation, execution, and verification

- `validate_portable_model` checks schema, ids, references, JSON payloads, and obligation shape.
- `execute_portable_model` explores all nondeterministic results for an explicit input sequence and returns bounded typed traces.
- `check_portable_model` builds the reachable graph and checks invariants, terminals, temporal obligations, and fairness declarations.

Each report distinguishes `pass`, `fail`, `blocked`, and `invalid`; trace truncation is a visible blocker, never a pass.

### 4. Give temporal obligations finite graph semantics

Safety invariants name forbidden states. `eventually` requires every path from each reachable trigger state to reach a target; a reachable non-target dead end or closed non-target SCC is a counterexample. `bounded_eventually` additionally rejects any target-avoiding path of more than the declared bound. `weak_fairness` names transitions that must be considered fair when continuously enabled; malformed or never-enabled declarations are rejected, and fairness-aware eventuality may exclude only SCC traces that demonstrably starve a continuously enabled declared transition. Reports retain the excluded and remaining SCC evidence.

### 5. Make refinement mappings explicit

`RefinementBinding` maps every reachable child state to a parent state and every child transition either to one parent transition or to an explicitly allowed stutter. Initial and terminal states must map, each concrete step must preserve mapped source/target plus input/output symbols, child assumptions must be no stronger than parent assumptions, and child guarantees must cover parent guarantees. Missing mappings and strengthened assumptions fail with the smallest available counterexample.

Automatic abstraction inference was rejected because it can hide modeling mistakes and create a second source of truth.

### 6. Keep composition token-based and bounded

`check_composition` verifies that each component assumption is supplied by the environment or another component guarantee, all explicitly declared conflicts are absent, and every child model independently passes. Tokens carry declared contract meaning; FlowGuard does not infer domain semantics from token text.

### 7. Register one public API and three top-level CLI commands

The package exports the schema objects and checker functions from `flowguard.__init__`. The CLI adds `portable-model-validate`, `portable-model-check`, and `portable-model-refinement`. All use the same report objects and canonical JSON; human output is a projection only.

### 8. Update only the skills that own this semantic boundary

`model-first-function-flow` owns selection/creation of the smallest faithful portable model, `flowguard-model-mesh` owns parent/child partition and mapping completeness, and `flowguard-model-topology-hazard-review` owns temporal/fairness hazard review. Existing preflight/API/validation skills receive boundary references only where needed; no new public skill is introduced until the API proves stable.

## Risks / Trade-offs

- **[Risk] Explicit transition tables can grow quickly.** → Enforce size bounds, stable identities, and model partitioning; retain Python-native models for authoring and use the IR only at interchange/check boundaries.
- **[Risk] Universal eventuality is stricter than the existing existential reachability helper.** → Keep the APIs distinct and document the different claim boundary; do not silently reinterpret old reports.
- **[Risk] Weak fairness can be overclaimed.** → Require named, continuously enabled transitions and preserve both fairness-excluded and still-valid counterexamples.
- **[Risk] Token contracts appear meaningful without domain proof.** → Treat tokens as declared interfaces only and report that semantic truth remains model-owner evidence.
- **[Risk] Public exports enlarge the compatibility surface.** → Export only versioned dataclasses and narrow functions; reject alternate schemas instead of accumulating readers.

## Migration Plan

1. Add the OpenSpec and FlowGuard model contracts with known-good and one bad case per protected failure.
2. Implement and test schema/canonical identity.
3. Implement interpreter, safety, temporal, and fairness checks.
4. Implement refinement and composition checks.
5. Register the Python/CLI surface and update affected skill prompts/contracts.
6. Run focused checks, affected model regression, full local validation, installation parity, and local package activation.

Rollback before local activation removes the new modules, commands, exports, prompts, and schema. After local activation, incompatible corrections use a new version and current schema. This change does not create or move a remote tag.

## Open Questions

- A future change may define a compiler from bounded Python `FunctionBlock` graphs into the IR. This change deliberately requires callers to supply the finite projection and does not claim automatic compilation.
