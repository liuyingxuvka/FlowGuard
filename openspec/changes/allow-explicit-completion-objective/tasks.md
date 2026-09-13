## 1. Objective identity resolver

- [x] 1.1 Add the read-only completion-objective resolver with safe
  `openspec/changes/<name>` containment, reparse-point rejection, exact
  artifact enumeration, deterministic ordering, and content fingerprints for
  `.openspec.yaml`, `proposal.md`, `design.md`, and `specs/**/*.md`.
- [x] 1.2 Define typed resolver errors and bounded terminal projections for
  unknown, archived-only, unsafe, symlinked, unreadable, and incomplete
  objective artifacts; do not write receipts or run directories on failure.
- [x] 1.3 Add the explicit `--completion-objective-change` option to the full
  suite parser, canonical readiness parser, and `python -m flowguard` finite
  forwarding table while preserving the existing repair-scope option.
- [x] 1.4 Pass the resolved objective fingerprint through the shared planner
  into `CompletionEpochPlan.freeze`; preserve the legacy default when the
  explicit option is omitted.

## 2. Contract and integration tests

- [x] 2.1 Test deterministic objective fingerprints, artifact ordering,
  excluded `tasks.md` checkbox progress, and changed proposal/spec content.
- [x] 2.2 Test rejection of unknown names, path traversal, symlinks/reparse
  points, missing required artifacts, extra unregistered files, and unreadable
  objective inputs without any producer-side write.
- [x] 2.3 Test that same-objective terminal reuse and third-attempt blocking
  remain unchanged, while a distinct objective receives a new cycle and leaves
  the old ledger/reservation bytes untouched.
- [x] 2.4 Test readiness/full objective forwarding and mismatch admission,
  including the strict `--require-executed-evidence` mode and output-path
  normalization.

## 3. Verification and bounded rollout

- [x] 3.1 Run focused objective, completion-epoch, readiness, and validation
  command tests; then run strict OpenSpec validation for all changes.
- [x] 3.2 Generate one readiness receipt for this named change with the same
  explicit objective and strict-evidence flag that the formal full command
  will use; stop on any identity mismatch or external gate blocker.
- [ ] 3.3 On a symlink-capable runner only, reserve and execute at most one
  full producer for this objective, then run exactly one same-parent
  `--reuse-only` check. Preserve typed `blocked`/`not_run` evidence for any
  external CI, provider, UI, installation, or release owner.
  Current runner is not symlink-capable: the direct capability probe returned
  `WinError 1314` (required privilege unavailable). No producer or reuse-only
  run was started under this gate.
- [x] 3.4 Mark this change's tasks complete only from current terminal
  evidence; never delete or rewrite the historical exhausted-cycle ledger,
  and do not commit, tag, push, or release without separate authorization.
