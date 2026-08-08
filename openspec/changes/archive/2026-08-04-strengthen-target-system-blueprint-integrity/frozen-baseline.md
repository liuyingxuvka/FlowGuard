## Frozen implementation baseline

Captured for change `strengthen-target-system-blueprint-integrity` before production implementation.

### Authority identities

- Authoritative repository: `<REPOSITORY_ROOT>`
- Branch and base commit: `main` at `fa8a9a4d9280cea6128e9d23517fe67533424e5e`
- Remote base: `origin/main` and tag `v0.68.6` at the same commit
- Package source resolved by the active Python: `<REPOSITORY_ROOT>/flowguard/__init__.py`
- Package candidate version: `0.68.6`; schema: `1.0`
- Project audit: passing at the frozen base
- Observed model snapshot: `sha256:20f38ee77086878e8d5724422a6e6c05b0ba40aa1054bccc7c8570d3e4fd87a9`
- Observed model head: `sha256:3d113f24be1695c6b9766f31ec1f54acc7a194528dcb54882645628fc7609bad`
- OpenSpec change: active, repo-local, strict-valid before implementation
- SkillGuard maintenance unit: `unit:flowguard-suite`; 15 registered FlowGuard source members
- Consumer-suite authority: check passed for the exact 15-member inventory
- Installed consumer root: `<LOCAL_CODEX_HOME>/skills`; current pre-change check passed with no conflicts
- Patch target: `0.68.7`, subject to re-reading the current version immediately before the version edit

### Peer boundaries

The main worktree is authoritative. The following pre-existing worktrees/branches are peer-owned and SHALL NOT be reset, cleaned, merged, rebased, synchronized into, or overwritten by this change:

- `<PEER_WORKTREE:flowguard-understanding-readiness-v0684>` / `agent/flowguard-understanding-readiness-v0684`
- `<PEER_WORKTREE:flowguard-currentness>` / `agent/harden-currentness-validation`
- `<PEER_WORKTREE:flowguard-model-miss-diagnostics>` / `agent/flowguard-model-miss-diagnostics`

The OpenSpec directory for this change is task-owned. Any later file outside the frozen owner plan is treated as a peer write until deliberately reconciled.

## Refreshed final affected-owner plan

This plan was refreshed after implementation discovery on 2026-08-04. It
supersedes the coarse pre-implementation partition below the authority and peer
boundaries above. Each governed source path belongs to one row only; evidence
outputs remain outside the source-freshness inventory.

| Owner | Exact implementation scope | Exact validation scope |
|---|---|---|
| `owner:target-core` | `flowguard/target_system_blueprint.py`, `flowguard/target_native_qualification.py`, `flowguard/implementation_inventory.py`, `flowguard/implementation_inventory_python.py`, `flowguard/blueprint_topology.py`, `flowguard/canonical_blueprint_projection.py` | `tests/test_target_system_blueprint.py`, `tests/test_target_neutral_blueprint_acceptance.py`, `tests/test_implementation_inventory.py`, `tests/test_blueprint_topology.py` |
| `owner:evidence-core` | `flowguard/software_blueprint_readiness.py`, `flowguard/model_revision_set.py`, `flowguard/model_revision_builder.py`, `flowguard/model_revision_owner_evidence.py`, `flowguard/model_authority_store.py`, `flowguard/validation_ownership.py`, `flowguard/validation_owner_execution.py`, `flowguard/evidence_receipts.py`, `flowguard/process_supervision.py` | `tests/test_software_blueprint_readiness.py`, `tests/test_model_authority.py`, `tests/test_model_authority_store.py`, `tests/test_model_revision_builder.py`, `tests/test_model_revision_owner_evidence.py`, `tests/test_validation_execution_ownership.py`, `tests/test_validation_owner_execution.py`, `tests/test_evidence_receipts.py`, `tests/test_process_supervision.py` |
| `owner:compact-reduction` | `flowguard/affected_blueprint_reader.py`, `flowguard/blueprint_compact_projection.py`, `flowguard/architecture_reduction.py`, `flowguard/self_reduction_inventory.py`, `flowguard/self_architecture_reduction.py` | `tests/test_affected_blueprint_reader.py`, `tests/test_blueprint_compact_projection.py`, `tests/test_self_reduction_inventory.py`, `tests/test_self_architecture_reduction.py` |
| `owner:public-integration` | `flowguard/implementation_blueprint.py`, `flowguard/project_blueprint.py`, `flowguard/self_blueprint.py`, `flowguard/understanding_readiness.py`, `flowguard/__main__.py`, `flowguard/__init__.py`, `docs/api_surface.md`, `docs/implementation_blueprint.md`, `README.md` | `tests/test_implementation_blueprint.py`, `tests/test_blueprint_aggregate_integrity.py`, `tests/test_implementation_blueprint_cli.py`, `tests/test_blueprint_cli_routes.py`, `tests/test_project_blueprint.py`, `tests/test_self_blueprint.py`, `tests/test_understanding_readiness.py`, `tests/test_api_surface.py`, `tests/test_implementation_blueprint_docs.py` |
| `owner:skill-prompts` | exactly `.agents/skills/flowguard`, `.agents/skills/flowguard-existing-model-preflight`, `.agents/skills/flowguard-model-test-alignment`, `.agents/skills/flowguard-architecture-reduction`, `.agents/skills/flowguard-structure-mesh`, and `.agents/skills/flowguard-development-process-flow`, including each changed `SKILL.md`, `agents/openai.yaml`, named protocol, `contract-source.json`, `compiled-contract.json`, and `check-manifest.json` | the six target-native command sets; prompt-budget, route-parity/topology, direct-current/no-fallback, contract compile/check, static SkillGuard, native-owner, and parent self-governance checks; `tests/test_skill_docs.py` |
| `owner:model-authority` | `.flowguard/architecture_reduction/model.py`, `.flowguard/authoritative_model_system/model.py`, `.flowguard/authoritative_model_system/software_blueprint_definition.json`, `.flowguard/development_process_flow/model.py`, `.flowguard/development_process_flow/run_checks.py`, `.flowguard/existing_model_preflight/model.py`, `.flowguard/existing_model_preflight/run_checks.py`, `.flowguard/implementation_blueprint/model.py`, `.flowguard/implementation_blueprint/run_checks.py`, `.flowguard/model_test_code_alignment/model.py`, `.flowguard/model_test_code_alignment/run_checks.py`, `.flowguard/structure_refactor_mesh/model.py`, `.flowguard/model-regression-manifest.json`, `flowguard/model_regressions.py`, and the canonical observed-model revision/store artifacts created after the source freeze | each affected model's native runner and purpose closure; `tests/test_model_regression_manifest.py`; one full model-regression parent; distinct native-owner leaf receipts; one atomic ModelRevisionSet build, activation, and exact-current authority audit |
| `owner:openspec` | this change's proposal, design, tasks, baseline, intent inventory, all sixteen delta specs, and their sixteen main-spec targets; `openspec/specs/model-maturation-iterative/spec.md` is retained as an explicitly reviewed adjacent current-authority edit | completeness/correctness/coherence comparison; change strict validation; all-spec strict validation; archive-time main-spec synchronization; immutable archive identity |
| `owner:distribution` | `flowguard/consumer-suite-authority.json`, `scripts/check_flowguard_skill_suite.py`, approved shadow workspace `<APPROVED_SHADOW_WORKSPACE>`, formal source projection, installed consumer root `<LOCAL_CODEX_HOME>/skills`, and the editable package projection | consumer authority compile/check; affected SkillGuard recompile/check; `tests/test_full_validation_composition.py`; shadow sync/verify; skill dry-run/install/check/parity; package import/version/schema/CLI verification; private global-router refresh/check |
| `owner:release` | `pyproject.toml`, `.flowguard/project.toml`, `CHANGELOG.md`, `docs/github_release_checklist.md`, `docs/validation_and_distribution.md`, `AGENTS.md`, the frozen validation request, Git commit, tag, and GitHub Release | focused version/currentness tests; `tests/test_release_verification.py`; one foreground full-suite owner and immutable parent receipt; local-candidate verifier; remote-main drift check; commit/tag/release/published-identity verification; KB postflight and goal closure |

The twelve affected observed model owners are `architecture_reduction`,
`authoritative_model_system`, `development_process_flow`,
`existing_model_preflight`, `guidance_compression`,
`harden_ui_content_visibility_validation`, `implementation_blueprint`,
`model_miss_review`, `model_test_code_alignment`, `structure_refactor_mesh`,
`test_evidence_mesh`, and `work_context`. The intent inventory and revision
evidence must cover this exact set; the former nine-owner projection is stale.

Every changed governed component must map to exactly one row before validation.
Unknown or duplicate ownership blocks planning; it never expands to an
automatic run-all. Runtime outputs, logs, receipts, and generated evidence
directories are evidence outputs, not source-freshness inputs.
