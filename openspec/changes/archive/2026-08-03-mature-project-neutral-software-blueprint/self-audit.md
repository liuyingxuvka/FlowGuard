# Pre-release self-audit

## Claim boundary

This audit asks whether the current FlowGuard source can produce a project-neutral, inspectable static software blueprint and whether its own blueprint exposes safe architecture contractions. It does not claim that FlowGuard, or any target software, was reconstructed in isolation. Empirical reconstruction remains `not_run` unless a user separately requests it and supplies or authorizes its execution evidence.

## Circular-proof finding and correction

The first generic builder version accepted exact test-evidence fingerprints from the same project blueprint declaration that asserted the binding. That was structurally circular: the declaration could agree with itself while the target test source had changed.

The corrected project document embeds the complete strict-current `ProjectTestInventory`. Every audit independently re-discovers the current test files, executable nodes, assertions, adapter identity, and structure. Model-to-test bindings are compared with that audited inventory, and the model-test alignment identity is derived from the newly reviewed binding report. A tampered test source now blocks the project audit.

## Completed contraction inventory

The finite ArchitectureReduction review `flowguard-blueprint-pre-release-reduction` completed with no findings and no remaining ready action:

| Candidate | Proof | Result |
|---|---|---|
| `remove-broad-owner-inference` | `safe_by_equivalence` | Removed the broad self-owner fallback and repeated model-id guessing; unknown ownership now blocks. |
| `collapse-self-binding-compiler` | `safe_by_equivalence` | Replaced the separate self-only binding compiler with the project-neutral builder. |
| `merge-surface-dimension-policy` | `safe_by_equivalence` | Moved lifecycle-dimension closure into one shared project policy. |

Public CLI entry points and output claims remain unchanged in authority: audit/check are read-only, explicit export is separate, and no entry starts reconstruction.

## Deliberately retained boundaries

- Python is the only deep-discovery adapter in this release. Unsupported languages block visibly rather than receiving a shallow success label.
- A full embedded test inventory is larger than a compact affected-neighborhood identity, so ordinary maintenance loads only affected owners. Whole-software inventory is reserved for an explicit blueprint, export, self-audit, or release scope.
- Static blueprint completeness proves inventory, traceability, independent semantics, model-code-test binding, and resource/oracle closure. It does not prove runtime equivalence or clean-room reconstruction.

## Final evidence

The exact final self-blueprint counts, full regression receipt, install identity, Git commit, tag, and published release are recorded only after the source and toolchain are frozen. Until then, prior successful runs are focused feedback rather than release authority.
