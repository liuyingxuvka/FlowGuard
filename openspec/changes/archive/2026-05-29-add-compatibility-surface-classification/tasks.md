## 1. OpenSpec And FlowGuard Grounding

- [x] 1.1 Verify real FlowGuard importability, installed/package version, project audit, OpenSpec status, and local git status.
- [x] 1.2 Add the OpenSpec proposal, design, spec deltas, and task plan for compatibility-surface classification.
- [x] 1.3 Validate the OpenSpec change before production implementation.

## 2. Architecture Reduction API

- [x] 2.1 Add `CompatibilitySurfaceClassification` and classification/recommended-action constants to `flowguard/architecture_reduction.py`.
- [x] 2.2 Extend `ArchitectureReductionPlan` and `ArchitectureReductionReport` to carry compatibility-surface classifications without breaking existing callers.
- [x] 2.3 Add review findings for current contracts, public entrypoint surfaces, negative legacy tests, archive-only runtime authority, prune candidates, and evidence-needed surfaces.
- [x] 2.4 Export the new helper type and constants from `flowguard/__init__.py` and the modeling helper API list.

## 3. Tests And Documentation

- [x] 3.1 Add focused architecture-reduction tests for every compatibility-surface classification branch.
- [x] 3.2 Update API surface tests for the new exports.
- [x] 3.3 Update `docs/api_surface.md` and add a focused compatibility-surface guide.
- [x] 3.4 Update skill-facing architecture-reduction guidance if installed skill docs are generated from the repository; otherwise record it as an external follow-up.

## 4. Validation And Local Sync

- [x] 4.1 Run focused tests for architecture reduction and API exports.
- [x] 4.2 Run OpenSpec strict validation for the change and all specs.
- [x] 4.3 Run the full practical test suite, using background execution only for long-running checks.
- [x] 4.4 Run project audit and synchronize the editable local install.
- [x] 4.5 Verify import path, package metadata version, schema version, and the new API from the local installed package.
- [x] 4.6 Record FlowGuard adoption evidence for the change.
- [x] 4.7 Review git status, avoid unrelated peer changes, and commit only the intended FlowGuard changes locally.
