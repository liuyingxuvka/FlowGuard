# FlowGuard author-repository rules

This repository is the public FlowGuard source and an explicit SkillGuard
author-maintenance workspace. Keep changes scoped, evidence-backed, portable,
and safe for dirty or parallel work. Never reset, delete, overwrite, install,
or publish outside the exact authorized boundary.

## Identity and source of truth

- Repository: https://github.com/liuyingxuvka/FlowGuard
- Consumer entrypoint: the clean projection at `$CODEX_HOME/skills/flowguard/SKILL.md`.
  The Python package and CLI are not the consumer skill installation surface.
- Project record: `.flowguard/project.toml`; adoption logs are
  `.flowguard/adoption_log.jsonl` and `docs/flowguard_adoption_log.md`.
- Current model authority is the sole content-addressed
  `observed_implementation` head. Change it only through an accepted
  `ModelRevisionSet`; persist evidence before pointer updates.
- Use latest-schema-first direct replacement. Replaced fields, wrappers,
  aliases, and alternate success paths need an explicit disposition; no normal
  fallback or parallel authority is allowed.

## FlowGuard routing

For non-trivial work use the single public `flowguard` skill. Read its entry
skill, then the route index and the one selected domain protocol. Domain
directories are reference material, not independent public skills. Select one
of the three lifecycle operations directly:

```powershell
python -m flowguard read --root . --request <request.json> --json
python -m flowguard change --root . --request <request.json> --json
python -m flowguard release --root . --request <request.json> --json
```

`use_flowguard`, `skip_with_reason`, and `needs_human_review` remain separate
from the lifecycle operation. A clean static or normative artifact is not
runtime, UI, external-service, release, or future-behavior proof. Do not create
a fake local FlowGuard replacement.

## Execution phase boundary

- Read/diagnose is strictly read-only: no compile, lease, run directory,
  owner execution, current pointer, installation, Portfolio/router refresh, or
  release write.
- Source-change freezes the affected owner closure and runs only declared
  FlowGuard/model/test checks. It does not install a consumer or self-optimize.
- Installation, global-router currentness, and GitHub publication are separate
  explicit claims. Broad source evidence does not imply any of them.

## Model and evidence gates

Preserve unknown, contradictory, unmapped, stale, skipped, blocked, and
out-of-scope states. Ordinary changes bind protected failures to the real
native checks, oracle, current implementation, owner, test, and receipt
evidence. Per-element good/bad/draft evidence is required only for an explicit
architecture reduction or candidate comparison; read creates no new evidence.
Broad
behavior claims require the BehaviorCommitmentLedger; path-sensitive claims
require one Primary Path Authority; field changes require FieldLifecycleMesh;
large or stale validation requires TestMesh. DevelopmentProcessFlow owns staged
order, freshness, peer writes, installation sync, release, and publish claims.

## Author-only maintenance

The managed SkillGuard block below admits source maintenance only. For the full
author handoff, validation-ownership rules, explicit install/release branch,
and private evidence boundary, read `.skillguard/author-maintenance.md` and
the selected SkillGuard reference. Do not copy author contracts, receipts,
router/Portfolio state, or author-only fixtures into the consumer projection.

## Short command index

```powershell
python -m flowguard read --root . --request <request.json> --json
python -m flowguard change --root . --request <request.json> --json
python -m flowguard release --root . --request <request.json> --json
```

The commands above are entrypoints, not proof of completion. Report the exact
checks, receipts, skipped/not-run obligations, blockers, residual risk, and
claim boundary that were actually current.

<!-- BEGIN MANAGED SKILLGUARD AUTHOR RULES -->
## SkillGuard author maintenance

This is an explicit SkillGuard author repository. This block is only a short admission pointer; the target skill keeps its domain route, judgment, actions, and native-check authority.

Canonical SkillGuard repository: https://github.com/liuyingxuvka/SkillGuard

Managed skills:
- `.skillguard/author-project.json` is the exact managed inventory (1 member(s)); each row binds one native owner, maintenance unit, and route-evidence path.
- The target skills keep domain-route, judgment, action, and native-check authority.

Before a source edit or validation, read the target `SKILL.md`, its native route/check contracts, and `references/skillguard-supervisor.md`.
Use one frozen maintenance unit, exact owner/check identities, private evidence roots, and current terminal receipts; missing, duplicate, foreign, stale, or cleanup-unconfirmed evidence blocks.

Validation policy: `skillguard.validation_execution_ownership.current`. It is direct-current only: no fallback, migration, alias, dual authority, or cross-unit receipt reuse.
Consumer projections contain no author contracts, receipts, router, Portfolio, or author-only runtime. Installation, global-router currentness, and release are separate explicit claims; read `references/skillguard-target-installation.md` and `references/skillguard-self-host.md` only for those routes.

Author currentness command: `python <installed-skillguard>/scripts/skillguard.py read --root . --request read.json --json`

This managed block is a routing and maintenance contract. It is not runtime, test, release, or future-behavior proof.
<!-- END MANAGED SKILLGUARD AUTHOR RULES -->
