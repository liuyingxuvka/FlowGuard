# Frozen Implementation Baseline

Recorded for the isolated implementation lane before production edits.

## Coordination boundary

- Implementation worktree: `C:\Users\liu_y\Documents\FlowGuard_currentness_20260728`
- Implementation branch: `agent/harden-currentness-validation`
- Base commit: `1556e93ec471e268829d88b9d12a864d08f33c88`
- Authoritative repository: `https://github.com/liuyingxuvka/FlowGuard.git`
- Original main worktree: `C:\Users\liu_y\Documents\FlowGuard_20260427`
- Original main remains at the same base commit and owns the pre-existing
  `0.64.2` version, documentation, consumer-authority, OpenSpec, and
  generation-6 model-authority edits recorded below. The isolated lane MUST
  integrate their intent and MUST NOT reset, overwrite, clean, or commit them
  in place.

Original main owned paths at freeze:

- `.flowguard/model-mesh/activations/bfcaf419e2b528c51e654c37fbd127e3264bb2228a94073beb44bdee13408eef.json`
- `.flowguard/model-mesh/revisions/79cf8faf0fe3a3a4afef58d2fe636c884f4281e9257038312874e457532ae00b.json`
- `.flowguard/model-mesh/snapshots/ccb14b31375b9499e2221c1af928f518c303d371fe019514320e5f895ba3e0a2.json`
- `.flowguard/project.toml`
- `AGENTS.md`
- `CHANGELOG.md`
- `README.md`
- `docs/github_release_checklist.md`
- `docs/validation_and_distribution.md`
- `flowguard/consumer-suite-authority.json`
- `openspec/changes/ensure-model-authority-git-reachability/specs/authoritative-model-system/spec.md`
- `openspec/specs/field-lifecycle-mesh/spec.md`
- `openspec/specs/long-check-observability/spec.md`
- `pyproject.toml`

## Separate baseline identities

- Source tree: Git commit `1556e93ec471e268829d88b9d12a864d08f33c88`
  plus this change's untracked OpenSpec artifacts.
- Source package version: `0.64.1`.
- Imported module: this isolated checkout's `flowguard/__init__.py`, schema
  `1.0`.
- Installed distribution metadata: `0.64.2`; this intentionally differs from
  the isolated source baseline and blocks project confidence until integration.
- Project adoption manifest: package `0.64.1`, schema `1.0`.
- OpenSpec provider: `1.6.0`; change
  `harden-currentness-validation-execution` passed strict validation with 20
  delta specifications and 86 tasks.
- Observed-model head: generation `5`, snapshot
  `sha256:8dd5efe6f085370984c954b59cba6f8856309c763ec7b4d9e24552666a48a7ca`,
  revision
  `sha256:ae9bbcf157b311b81edadc998227b0ad6930d4dfa9ce7a87e11f30ddea4fdc25`,
  activation
  `sha256:fa08fa02078d9d7563737ed5a4e1d1842f557428aa34bf4e0917b8549160a861`,
  head
  `sha256:73a5305060e5a70e0734ce3d689d950df4fc386d13a98e915b314abaf1a7b665`.
- Package consumer authority: 15 members, version `0.64.1`, authority hash
  `sha256:6a9686579915d21931e6d40de978bcd1ea3e8c90b43111dd5d29175b35d9e994`,
  file SHA-256
  `46D4A04FC454E14788362356B5C651B81F25CD0FFFC4AE8C731B4943BA9EF596`.
- Author kernel skill SHA-256:
  `49FBBF5E5A869CD634E3FF47BC7CF9BE05C7CA433348858232C61664106B62EF`.
- Installed kernel skill SHA-256:
  `49FBBF5E5A869CD634E3FF47BC7CF9BE05C7CA433348858232C61664106B62EF`.
- Shadow candidates are preserved separately; no shadow is selected as current
  before the installation phase.
- Remote main: `1556e93ec471e268829d88b9d12a864d08f33c88`.
- Existing annotated tag `v0.64.1` peels to
  `4d257db292b51fe410f680d7b4e7df0bb622298d`.
- GitHub repository: `liuyingxuvka/FlowGuard`, default branch `main`.

## Frozen failure set and ownership closure

The implementation is bounded to these independently observed failures:

1. OpenSpec history/current semantic drift and duplicate suite authority.
2. Declared observed models missing materialized model/runner content.
3. Model revision diff, closure, evidence, activation, and rollback authority
   that is incomplete or caller-declared.
4. Child receipt identity/supersession and planning-created proof.
5. Validation owner inventory frozen after execution begins, coarse freshness,
   and unverified WorkContext content.
6. Execution-key leases, incomplete descendant cleanup, and non-terminal model
   runner evidence.
7. More than one possible broad completion signal instead of one verified
   `validation-parent:full`.
8. Optional UI completeness inputs, shallow shadow parity, and callable
   fingerprints that ignore implementation.
9. Prompt duplication and oversized implementation surfaces whose public
   facades must remain stable.

Primary owner closure:

- OpenSpec semantic sync and current spec authority.
- Authoritative model system and project-adoption model.
- Evidence receipt, PlanDetail, TestMesh, and Model-Test Alignment.
- Validation ownership, evidence lifecycle, WorkContext, process supervision,
  model regressions, suite command, and DevelopmentProcessFlow.
- UI implementation evidence, distribution/shadow verification, and budgeted
  graph identity.
- The single SkillGuard maintenance unit `unit:flowguard-suite`.

Affected siblings that require review but do not inherit authority:

- model-impact freshness, long-check observability, package API registry,
  project audit/upgrade, release verification, installed-layout validation,
  and StructureMesh/TestMesh parent checks.

Frozen public facades:

- Existing `flowguard` imports and CLI command names.
- `scripts/check_flowguard_skill_suite.py` command surface.
- `scripts/run_flowguard_model_regressions.py` command surface.
- Current 15 public consumer skill ids.
- Current UI, receipt, WorkContext, validation ownership, model authority, and
  budgeted public data types unless the accepted breaking specification
  explicitly replaces a caller-authoritative field.

This baseline is planning and coordination evidence. It is not validation,
model, installation, Git, or release proof.
