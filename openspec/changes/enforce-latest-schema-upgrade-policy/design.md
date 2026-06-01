## Context

FlowGuard already records package and schema versions in target repositories,
and Architecture Reduction already classifies compatibility-like surfaces before
contraction. The missing default is a single entry policy for older adopted
repositories: project upgrade currently refreshes version records, while old
models, reports, tests, and guidance can still remain in historical shapes or
encourage agents to preserve backward-compatible runtime branches.

This change treats compatibility as an entry-boundary concern. FlowGuard may
recognize older artifacts long enough to upgrade them, but normal route logic,
runtime reviews, and AI guidance should use the current schema and route-first
surface only.

## Goals / Non-Goals

**Goals:**

- Make latest-schema-first the default FlowGuard maintenance direction.
- Add deterministic artifact/project upgrade reporting with dry-run and apply
  modes.
- Extend project upgrade so older adopted repositories scan known FlowGuard
  artifacts, reports, docs, tests, and guidance for old shapes.
- Preserve safety classifiers that prevent unsafe deletion of current
  contracts, public facades, negative legacy tests, runtime-authoritative
  archives, and unknown surfaces.
- Synchronize source, editable install, installed Codex skills, shadow
  workspace, version files, changelog, and adoption evidence.

**Non-Goals:**

- Do not support indefinite backward compatibility inside normal runtime route
  logic.
- Do not guess semantic rewrites for Python model or test scripts when a
  deterministic mapping is unavailable.
- Do not delete safety classifiers merely because their names include legacy or
  compatibility.
- Do not replace route-owner validation with an upgrade report.

## Decisions

1. **Create an upgrade report helper instead of hiding migration inside every
   route.**

   Rationale: upgrades should happen before current runtime logic runs. A
   separate helper can report upgraded, unchanged, skipped, and blocked items
   without teaching each route to accept historical input shapes.

   Alternative considered: add `if old_field` compatibility branches to route
   reviewers. Rejected because it expands long-lived maintenance surface and
   makes old evidence look current.

2. **Keep migration deterministic and conservative.**

   Rationale: JSON/TOML records and known alias names can be upgraded
   mechanically. Python model/test behavior is code, so FlowGuard should only
   auto-rewrite known safe API names; otherwise it should produce a blocked
   report with the affected path and reason.

   Alternative considered: AI-assisted script rewriting during project upgrade.
   Rejected for the core tool because project upgrade must be repeatable,
   auditable, and dependency-free.

3. **Make `project-upgrade` call the scan by default.**

   Rationale: when FlowGuard enters an older adopted repository, updating only
   `.flowguard/project.toml` and `AGENTS.md` leaves old models/tests/evidence in
   place. The default upgrade path should scan and upgrade what it can, while a
   records-only option can preserve the previous narrow behavior if needed.

   Alternative considered: require users to run a separate command every time.
   Rejected because the user intent is to make old repositories move to the
   current shape by default.

4. **Use Architecture Reduction to classify cleanup candidates.**

   Rationale: old compatibility paths are often removable, but some
   compatibility-looking code is safety machinery. The existing classifier is
   the right gate for active cleanup.

   Alternative considered: broad text cleanup based on `legacy` or `compat`.
   Rejected because it can delete evidence gates and negative legacy tests.

5. **Keep schema version stable unless artifact envelope semantics change.**

   Rationale: this change adds upgrade policy and helper behavior, but the
   current artifact envelope remains schema `1.0`. Package version should
   change; schema version should only change when the envelope contract changes.

## Risks / Trade-offs

- [Risk] Agents may treat upgrade reports as validation proof. -> Mitigation:
  reports state that route-owner model/test/replay evidence is still required
  after upgrades.
- [Risk] Automatic apply mode could overwrite a user's old files. ->
  Mitigation: default dry-run for the new CLI scan, explicit apply for writes,
  backup/receipt metadata for changed files, and deterministic file selection.
- [Risk] Project upgrade becomes too broad. -> Mitigation: records-only option
  remains available, and blocked unknown scripts are reported rather than
  rewritten.
- [Risk] Parallel agents have active edits. -> Mitigation: implementation only
  edits owned files for this change, avoids peer-modified paths unless a
  narrow patch is necessary, and does not revert peer work.

## Migration Plan

1. Add OpenSpec requirements and FlowGuard self-model for the upgrade policy.
2. Add `artifact_upgrade.py` with report objects and deterministic scanners.
3. Add CLI commands for dry-run/apply upgrade reports.
4. Extend `project-upgrade` to run the artifact upgrade scan by default and add
   `--records-only` for old record-only behavior.
5. Update docs, public templates, AGENTS snippets, and owned skill guidance.
6. Run focused tests, OpenSpec validation, FlowGuard model checks, editable
   install sync, installed skill parity checks, shadow workspace verification,
   and full practical regression.

## Open Questions

- None for this implementation. Unknown future old model shapes should be
  represented as blocked upgrade findings, not answered by guesswork here.
