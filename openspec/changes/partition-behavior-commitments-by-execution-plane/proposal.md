## Why

FlowGuard can already register behavior commitments, find existing models, rehearse AI workflows, review development-process freshness, and backfeed model misses, but those owners do not record whether a promise belongs to the product runtime, the acting AI, or the development process. As a result, identical words such as "download", "publish", or "connect the UI port" can be retrieved from the wrong responsibility plane, while a post-failure Model Miss still cannot make the correct operational model reliably discoverable on the next similar task.

## What Changes

- Extend the existing Behavior Commitment Ledger with a required behavior plane, structured actor kind, typed commitment relations, and lightweight lookup bindings while keeping exactly one primary owner model per commitment.
- Define the three authoritative planes `product_runtime`, `agent_operation`, and `development_process`; keep `commitment_kind` as the orthogonal interface/form classification.
- Replace untyped commitment dependencies with typed same-plane and cross-plane relations, with deterministic validation of permitted directions and mandatory rationale for cross-plane links.
- Add one canonical machine-readable project ledger and directly replace the former Python-authored template shape; former shapes are rejection fixtures, never a readable runtime authority.
- Add a deterministic, plane-first commitment lookup helper and a read-only CLI query surface; Existing Model Preflight uses the same helper before path-based model discovery and separates primary hits from typed related context.
- Extend model similarity so shared words across different planes are false-friend/manual-review evidence rather than automatic merge evidence.
- Extend Model Miss records and backfeed so a real failure first identifies whose promise failed, then updates or creates a commitment in that same plane and preserves typed related-plane links.
- Reuse existing AgentWorkflowRehearsal evidence/continue/rework gates for AI operations and existing DevelopmentProcessFlow freshness gates for lifecycle work; do not create a new route, runtime supervisor, action gateway, or universal forced-execution policy.
- Update current project rules, FlowGuard skills, prompt metadata, templates, self-models, field lifecycle, contract-exhaustion cases, model-test bindings, tests, installation parity, and direct-adoption evidence.
- **BREAKING**: current commitment rows use typed `relations` instead of `dependency_commitment_ids`; the former field and former ledger shapes fail closed and must be rewritten at their source.

## Capabilities

### New Capabilities

- `behavior-commitment-lookup`: Deterministic plane-first lookup, explainable primary/related hits, ledger freshness identity, and a read-only query command over the existing BCL authority.

### Modified Capabilities

- `behavior-commitment-ledger`: Add behavior-plane, actor-kind, typed-relation, lookup-binding, canonical-ledger, and former-shape rejection requirements.
- `existing-model-preflight`: Query registered commitments before path scanning and keep primary-plane model ownership distinct from typed related-plane context.
- `model-similarity-consolidation`: Make behavior plane part of signatures and block unsafe cross-plane consolidation.
- `model-miss-review`: Bind miss classification and same-class repair to the affected plane, commitment, and owner model.
- `post-runtime-model-miss-review`: Preserve plane/commitment identity in concrete runtime and UI miss records.
- `field-lifecycle-mesh`: Account new persisted, prompt, lookup, relation, replacement, and preflight fields plus deletion of the old dependency field.
- `contract-exhaustion-mesh`: Generate finite plane/actor/relation/lookup/former-shape known-bad cases and stable downstream case ids.
- `model-test-alignment`: Bind plane-aware model obligations to the owner public code contracts and current tests.
- `test-evidence-mesh`: Keep focused owner receipts, install-parity, model-regression, and the one frozen full-suite receipt visible and precisely freshness-bound.
- `development-process-flow`: Preserve ordering and freshness across OpenSpec, model, schema, direct replacement, code, prompt-contract compilation, installation, and validation without absorbing product or AI-operation ownership.
- `flowguard-api-registry`: Export the new BCL lookup types and helpers inside the existing behavior/preflight API groups and add the read-only CLI without adding a route id.
- `flowguard-codex-skill-satellites`: Teach existing skills to classify behavior ownership, query same-plane commitments first, and preserve route-native authority and installation parity.

## Impact

- Core modules: `behavior_commitment.py`, a new `behavior_commitment_lookup.py`, `existing_model_preflight.py`, `model_similarity.py`, `recurring_model_miss.py`, `templates.py`, `__init__.py`, and `__main__.py`.
- Project artifacts: a canonical `.flowguard/behavior_commitment_ledger/ledger.json` plus updated existing BCL, preflight, similarity, model-miss, development-process, and self-maintenance models.
- Guidance and installation: the managed project-rule generator, agent snippet, affected `.agents/skills` sources, prompt metadata, SkillGuard V2 contract sources/generated contracts, shadow installation, and installed parity.
- Evidence: focused unit tests, former-shape rejection tests, ContractExhaustion cases, Model-Test Alignment bindings, affected model receipts, one frozen-snapshot full suite, project audits, OpenSpec receipt consumption, and local release-readiness evidence. No external publication or Git operation is implied by this change.
