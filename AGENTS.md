<!-- BEGIN FLOWGUARD PROJECT RULES -->

<!-- flowguard-rule:project.scope -->

## FlowGuard Project Rules

This project uses FlowGuard for non-trivial maintenance, feature work, bug
fixes, refactors, tests, release work, direct current replacement, and evidence-sensitive
process changes.

<!-- flowguard-rule:project.repository -->

FlowGuard repository:
https://github.com/liuyingxuvka/FlowGuard

<!-- flowguard-rule:skill_suite.agent_surface -->

FlowGuard agent skill suite:
- Primary agent surface: `.agents/skills/`
- Default entry skill: `.agents/skills/model-first-function-flow/SKILL.md`
- Complete AI-agent setup means the agent can read `AGENTS.md` and all
  FlowGuard sibling `SKILL.md` files under `.agents/skills/`.
- The Python `flowguard` module/CLI is executable check support, not the
  AI-agent skill installation surface.

<!-- flowguard-rule:project.record_locations -->

Project FlowGuard record:
- Manifest: `.flowguard/project.toml`
- Machine log: `.flowguard/adoption_log.jsonl`
- Human log: `docs/flowguard_adoption_log.md`

<!-- flowguard-rule:project.rendered_versions -->

Current adoption record:
- FlowGuard check-engine version: `0.55.0`
- FlowGuard schema version: `1.0`

<!-- flowguard-rule:project.preflight_version_gate -->

Before non-trivial work:
1. Verify the real FlowGuard check engine:
   `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`
2. Check the installed check-engine version:
   `python -c "import importlib.metadata as m; print(m.version('flowguard'))"`
3. Audit the project record:
   `python -m flowguard project-audit --root .`
4. Compare the installed version with `.flowguard/project.toml`.
5. If the installed version is newer, run:
   `python -m flowguard project-adopt --root .`
   This directly replaces the managed project record with the one current
   FlowGuard shape. It does not read, convert, migrate, alias, or preserve an
   older FlowGuard skill/runtime shape. Then rerun only affected models/tests.
6. If the installed version is older than the project record, stop and connect
   a current FlowGuard check engine before claiming FlowGuard confidence.

<!-- flowguard-rule:runtime.current_authority_only -->

FlowGuard skill and runtime guidance has one current authority only.
Former FlowGuard skill, model, check, receipt, and project-control shapes are
blocked and may appear only as exact rejection fixtures. There is no normal
compatibility reader, migration command, upgrade route, converter, alias,
renewal route, or fallback success path. Ordinary software may read historical
documents, data, or interfaces only when an explicit requirement assigns a
bounded FlowGuard owner, accepted and rejected cases, and a claim boundary.

<!-- flowguard-rule:lifecycle.default_replacement -->

Default replacement means dispose the old path, old field, alias, wrapper, or
alternate success path. Delete, block, delegate, repair, replace, or
scope it out with a concrete reason; do not leave it as a second successful
route.

<!-- flowguard-rule:behavior.commitment_ledger -->

Broad behavior work should use or update BehaviorCommitmentLedger before
claiming full coverage: register external behavior promises, map source
surfaces to commitments, assign exactly one primary owner model per
commitment, classify plane and actor kind, record typed relations/evidence,
and hand `path_sensitive=true`
commitments to Primary Path Authority. Do not treat every helper function,
file, field, or model as a behavior commitment.

<!-- flowguard-rule:behavior.plane_partitioning -->

Keep product runtime behavior, AI-agent operations, and development lifecycle
behavior in one BehaviorCommitmentLedger structure but classify every
production commitment as exactly one of `product_runtime`, `agent_operation`,
or `development_process`. `commitment_kind` describes form, not plane.
Before non-trivial work, use the lightweight existing-model/commitment lookup
to select one same-plane primary context; keep other planes separated or
connected only by typed, reasoned relations. A related product commitment is
target context for an AI/process step, not an instruction that the step owns.
Model Miss backfeed searches the affected plane first and creates a gap row
only when no matching promise exists. This is recall guidance, not a universal
requirement to execute a model for every trivial action.

<!-- flowguard-rule:behavior.commitment_ledger_modes -->

Before changing or claiming behavior coverage, classify the behavior-ledger
mode: `bootstrap_ledger`, `add_behavior`, `change_behavior`,
`remove_or_replace_behavior`, `coverage_gap_backfill`, or `model_miss_check`.
Only bootstrap and gap backfill require broad historical source discovery.
Ordinary add/change/remove work updates affected commitments, owner models,
DCAR cases, and TestMesh evidence. Model-miss checks first map the failure to
an existing same-plane commitment and owner model; keep typed related-plane
context separate, and create/backfill a commitment only when the observed
external behavior was not registered in that plane.

<!-- flowguard-rule:lifecycle.field_mesh -->

Field-bearing work should use or update FieldLifecycleMesh: high-level behavior
models include behavior-bearing fields, while child/leaf field rows account all
discovered fields and record owner, readers, writers, projection, lifecycle,
and old-field disposition.

<!-- flowguard-rule:evidence.ui_and_payload -->

UI runnable claims and file/work-package claims need current UI click-through
or artifact-payload evidence gates before broad done/release confidence.

<!-- flowguard-rule:behavior.primary_path_authority -->

Path-sensitive behavior commitments need Primary Path Authority evidence before
broad confidence: one primary runtime authority per business intent, visible
primary failure, no automatic alternate success, ContractExhaustionMesh
coverage, TestMesh shards, and Risk Evidence Ledger gates.

<!-- flowguard-rule:behavior.exact_intent_reuse -->

Treat one exact external user purpose as one stable `business_intent_id`, one
active Behavior Commitment, and one singular `primary_path_id`. UI, API, CLI,
aliases, adapters, wrappers, helpers, and compatibility surfaces for that same
purpose delegate to the selected commitment and path; they do not become
independent successful implementations.

<!-- flowguard-rule:ui.product_language -->

Use the existing UI Flow Structure route to review one product-wide design
language across declared surfaces: typography hierarchy, components,
navigation, interaction, feedback, recovery, and transition semantics. Equal
semantic roles reuse the same rule or token; any exception is bounded,
presentation-only, and cannot change the business intent, commitment, path,
visibility class, or user-visible result.

<!-- flowguard-rule:ui.content_admission -->

Classify UI content exactly once as `user_visible`, `user_on_demand`, or
`internal`. Ordinary UI renders only admitted user content; on-demand content
needs an explicit reveal and return path, while internal identities, audit
fields, evidence metadata, diagnostics, and routing state stay internal by
default.

<!-- flowguard-rule:process.development_process_flow -->

Non-trivial rough-plan discussion, multi-skill/tool workflow setup, staged
execution, install/sync, release/archive/publish, post-change owner scans, and
final process claims enter `flowguard-development-process-flow` first as the
development-process simulator. Record `plan_detailing`, `agent_workflow`, and
`execution_freshness` modes; delegate to PlanDetailing or
AgentWorkflowRehearsal only when explicit or simulator-selected.
DevelopmentProcessFlow owns lifecycle order/freshness; AgentWorkflowRehearsal
owns AI-operation planning. Both may reference product commitments and their
evidence without copying product behavior into their own steps.

<!-- flowguard-rule:process.spec_work_package_reconciliation -->

When OpenSpec, Spec Kit, or another supported specification provider is in
scope, keep provider tasks native and reconcile them bidirectionally with
FlowGuard obligations/checks through one development-process Spec Work
Package. Begin and close one immutable input session, reuse only exact terminal
receipts within an explicit boundary, and block archive when mappings,
post-snapshot evidence, provider verification, or receipt freshness is
missing. Internal work-package fields never become product UI content.

<!-- flowguard-rule:process.post_change_scan -->

After non-trivial FlowGuard-managed work, let DevelopmentProcessFlow consume
post-change scan signals for changed artifacts, skipped routes, stale evidence,
open obligations, or split/reduction pressure. The scan output routes each gap
to the owning specialist, such as Model-Test Alignment, Architecture
Reduction, StructureMesh, ModelMesh, TestMesh, or AgentWorkflowRehearsal.

<!-- flowguard-rule:validation.native_owner_receipts -->

Keep every native test with exactly one existing owner. Before validation,
list the affected native checks, owner, exact functional input components, and
receipt order. SkillGuard/TestMesh may request a missing owner receipt and
aggregate current receipts, but a consumer must not copy, wrap, or carry the
owner command. Only a declared functional input change invalidates that owner;
reports, receipts, logs, timestamps, task checkmarks, and install bookkeeping
are outputs and must not trigger native retesting. Run one final full gate only
after source and tool identities freeze, under one explicit owner, never through
`--resume`, a scheduled task, a background retry, or an unattended helper. If
a launcher times out or is interrupted, confirm the whole descendant process
tree is absent before accepting evidence or starting another validation.

<!-- flowguard-rule:claim.no_fake_adoption -->

Do not create a fake local FlowGuard replacement. Do not claim full FlowGuard
completion from an AGENTS/manifest/log update alone; executable model checks,
tests, replay, and closure evidence still need to be current for the claim.

<!-- END FLOWGUARD PROJECT RULES -->

<!-- BEGIN MANAGED SKILLGUARD PROJECT RULES -->
## SkillGuard project maintenance

This repository contains skills maintained with SkillGuard. For non-trivial skill maintenance, validation, installation, synchronization, or release work, use SkillGuard by default.

Canonical SkillGuard repository: https://github.com/liuyingxuvka/SkillGuard

Managed skills:
- `.agents/skills/flowguard-agent-workflow-rehearsal` — integration=`native-integrated`, native owner=`development_process_flow`, route evidence=`.agents/skills/flowguard-agent-workflow-rehearsal/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-architecture-reduction` — integration=`native-integrated`, native owner=`architecture_reduction`, route evidence=`.agents/skills/flowguard-architecture-reduction/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-behavior-commitment-ledger` — integration=`native-integrated`, native owner=`behavior_commitment_ledger`, route evidence=`.agents/skills/flowguard-behavior-commitment-ledger/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-code-structure-recommendation` — integration=`native-integrated`, native owner=`code_structure_recommendation`, route evidence=`.agents/skills/flowguard-code-structure-recommendation/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-contract-exhaustion-mesh` — integration=`native-integrated`, native owner=`contract_exhaustion_mesh`, route evidence=`.agents/skills/flowguard-contract-exhaustion-mesh/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-development-process-flow` — integration=`native-integrated`, native owner=`development_process_flow`, route evidence=`.agents/skills/flowguard-development-process-flow/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-existing-model-preflight` — integration=`native-integrated`, native owner=`existing_model_preflight`, route evidence=`.agents/skills/flowguard-existing-model-preflight/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-field-lifecycle-mesh` — integration=`native-integrated`, native owner=`field_lifecycle_mesh`, route evidence=`.agents/skills/flowguard-field-lifecycle-mesh/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-model-mesh` — integration=`native-integrated`, native owner=`model_mesh_maintenance`, route evidence=`.agents/skills/flowguard-model-mesh/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-model-miss-review` — integration=`native-integrated`, native owner=`model_miss_review`, route evidence=`.agents/skills/flowguard-model-miss-review/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-model-test-alignment` — integration=`native-integrated`, native owner=`model_test_alignment`, route evidence=`.agents/skills/flowguard-model-test-alignment/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-model-topology-hazard-review` — integration=`native-integrated`, native owner=`model_topology_hazard_review`, route evidence=`.agents/skills/flowguard-model-topology-hazard-review/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-plan-detailing-compiler` — integration=`native-integrated`, native owner=`development_process_flow`, route evidence=`.agents/skills/flowguard-plan-detailing-compiler/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-structure-mesh` — integration=`native-integrated`, native owner=`structure_mesh_maintenance`, route evidence=`.agents/skills/flowguard-structure-mesh/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-test-mesh` — integration=`native-integrated`, native owner=`test_mesh_maintenance`, route evidence=`.agents/skills/flowguard-test-mesh/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/flowguard-ui-flow-structure` — integration=`native-integrated`, native owner=`ui_flow_structure`, route evidence=`.agents/skills/flowguard-ui-flow-structure/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.
- `.agents/skills/model-first-function-flow` — integration=`native-integrated`, native owner=`model_first_function_flow`, route evidence=`.agents/skills/model-first-function-flow/SKILL.md`; the target skill keeps domain-route, judgment, action, and native-check authority.

Required maintenance handoff:

1. Read the target skill's `SKILL.md` and its native route/check contracts before editing.
2. Use SkillGuard to inventory, validate, calibrate, and close non-trivial skill changes.
3. If the target already has a complete native route, upgrade that route (`native-integrated`).
4. If the target route is partial, preserve it and fill only missing gates (`hybrid-extension`).
5. Add a SkillGuard runtime route only after reviewed evidence proves no native runtime route exists.
6. Never let SkillGuard replace target-owned domain judgment, simulation, search, modeling, actions, or checks.
7. Do not claim deep use from contract presence alone; require a current target execution-depth receipt.
8. If SkillGuard is unavailable or this block/manifest is missing, stale, duplicated, or invalid, report the maintenance result as blocked instead of silently bypassing it.

Portable audit command: `python <installed-skillguard>/scripts/skillguard.py project-audit --root .`

This managed block is a routing and maintenance contract. It is not runtime, test, release, or future-behavior proof.
<!-- END MANAGED SKILLGUARD PROJECT RULES -->
