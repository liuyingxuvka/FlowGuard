## 1. Exact owner binding

- [x] 1.1 Bind `affected_authority_inventory` and its `authoritative_model_system` inventory-root route to the existing `authoritative_model_system` semantic model.
- [x] 1.2 Preserve exact missing/duplicate/foreign mapping rejection with no inferred or generic fallback.
- [x] 1.3 Replace unknown affected-id fallback with explicit ModelMesh-owned revision-accounting categories and fail closed for every unclassified category.

## 2. Executable FlowGuard self-model

- [x] 2.1 Add an explicit owner-map completeness condition to the authoritative model-system state and revision-generation invariant.
- [x] 2.2 Add a known-bad scenario proving that a green full parent cannot compensate for a missing affected inventory owner binding.

## 3. Regression coverage

- [x] 3.1 Add a production-shaped test that derives the current candidate route universe and verifies both inventory routes have unique authoritative model-system bindings.
- [x] 3.2 Retain negative tests for missing, duplicate, foreign, stale, and incomplete mapped model evidence.
- [x] 3.3 Run the focused owner-evidence, revision-builder, intent, and authoritative model-system checks.
- [x] 3.4 Prove known revision-accounting ids retain explicit ModelMesh ownership while a synthetic unknown affected-id category is rejected.

## 4. Specification and intent closure

- [x] 4.1 Synchronize both delta requirements into the main OpenSpec specifications and validate the change plus all specs strictly.
- [x] 4.2 Produce one current combined intent inventory that preserves the prior accepted contribution and adds this model-miss repair contribution against the final semantic diff.
- [x] 4.3 Prepare this completed change for archive without modifying the prior archived change.

## Release handoff after OpenSpec completion

After this change is archived, the release workflow re-runs the full model
parent from frozen source and archived intent, then builds distinct native-owner
evidence, accepts and activates one atomic v0.68.7 revision, and audits the
observed head as current. These are post-archive authority operations rather
than product-change completion checkboxes, so the OpenSpec archive cannot make
its own model input perpetually stale.
