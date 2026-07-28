## Context

The current observed snapshot records exact model and runner paths and hashes,
but local authority audit reads those paths from the working tree. Because the
repository broadly ignores `.flowguard/`, 49 snapshot inputs were present and
valid locally while absent from the committed release tree. The parent
validation receipt and release-tree manifest only inventoried already tracked
files, so neither detected the omitted dependencies.

The same publication pass also exposed a Windows command-boundary issue:
querying an annotated remote tag with a literal `^{}` argument can be altered
by a `.CMD` wrapper even though direct `git.exe` execution is correct.

## Goals / Non-Goals

**Goals:**

- Make the exact observed-snapshot input closure a release-tree obligation.
- Report all missing tracked paths in one deterministic, fail-closed check.
- Cover both omitted model files and omitted runner files.
- Query remote annotated tags without a caret-bearing command argument.
- Prove the correction from a clean clone and preserve affected-only
  revalidation.

**Non-Goals:**

- Do not track runtime evidence, caches, temporary receipts, or every file
  beneath `.flowguard/`.
- Do not infer a replacement model authority from whatever happens to be
  committed.
- Do not move or rewrite the immutable `v0.64.0` tag.
- Do not add compatibility readers or automatic full-suite retries.

## Decisions

1. Release verification will read the snapshot selected by
   `.flowguard/project.toml`, collect the snapshot file plus every declared
   model input path, and ask Git for their exact tracked inventory. Missing,
   invalid, escaping, or untracked paths block the local candidate.

   This check belongs before tagging because Git reachability is a publication
   property. The ordinary model-authority audit remains usable outside Git
   repositories and continues to own live model currentness.

2. The 49 existing ignored inputs will be added explicitly to Git. The broad
   `.flowguard/` ignore remains in place so runtime evidence does not become
   source authority by accident.

3. The published tag query will use the exact tag prefix pattern
   `refs/tags/<tag>*`, then accept only the exact tag and exact peeled-tag rows
   during parsing. This avoids Windows caret interpretation without weakening
   the identity comparison.

4. Regression evidence will include the observed missing-model case, the
   same-class missing-runner case, and a clean-clone project audit. A stable
   validation plan must still reuse unaffected owners.

## Risks / Trade-offs

- [Risk] A malformed snapshot could prevent extracting its input closure. →
  Treat extraction failure as a visible release blocker with no fallback.
- [Risk] Prefix tag lookup can return similarly named tags. → Parse only the
  exact `refs/tags/<tag>` and `refs/tags/<tag>^{}` keys.
- [Risk] Future ignored authority inputs could again be invisible to ordinary
  `git status`. → Keep the release check independent of status output and test
  it with intentionally untracked files.
- [Risk] Correcting already published v0.64.0 requires a new immutable
  identity. → Publish a patch version and leave v0.64.0 unchanged.

## Migration Plan

1. Add the reachability and remote-query regressions.
2. Implement the fail-closed release check.
3. Add the exact 49 current authority inputs to Git.
4. Refresh observed model authority through one accepted revision.
5. Run focused checks, clean-clone audit, and one frozen full validation.
6. Publish and verify a patch release; retain v0.64.0 as historical.

## Open Questions

None. The observed failure and required committed input closure are exact.
