# Current functional source contracts

These independently authored normative promises state what current FlowGuard behavior must do and name its single primary native model. Registration is separate from observed implementation execution, accepted model authority, release and publication.

The canonical ledger defaults to `claim_scope="registration"` and `require_current_evidence=false`. This registers the normative promises and keeps pending implementation/model evidence visible. A structurally valid registration means that the promises and owners are accounted for; it does not turn missing evidence into a pass. The newly declared responsibilities remain `missing`, not current, and unverified until their independently owned checks provide actual evidence.

A caller asking for full, done, release or another broad behavior claim must use the existing broad-claim review with current evidence required, such as `replace(ledger, claim_scope="full", require_current_evidence=True)`. That review of this same Source ledger rejects every pending responsibility and its stale owner/TestMesh state. Actual owner receipts and release evidence are verified independently; neither this normative document nor its own successful registration is runtime proof. No separate ledger or alternate authority is introduced.

A task closes when its required declared behavior and failure boundaries have current independently owned evidence and its exact requested outcome is satisfied. Necessary responsibilities, dependencies and unresolved uncertainty determine scope. A cost/token cap, model count or summary count does not determine sufficiency. Current-map fidelity, desired improvement, selected model-policy proof, actual implementation execution and whole-software confidence remain separate.

## Contract: python-function-state-verification-current

**Primary native model:** `python_function_state_verification`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Declared Python blocks, initial states, finite external inputs, invariants, contracts, replay observations and exploration settings.

**State:** Typed workflow state, retained nondeterministic branches, traces, exception/dead-end status and explicit completeness limits.

**Required behavior:** Preserve Input x State -> Set(Output x State), expose invocation/coercion/contract/invariant/replay/loop failures and retain incomplete exploration.

**Effects:** execute only declared fixture blocks; return typed reports and traces.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Dropped branch, hidden exception/dead end, malformed result, missed failure or incomplete search cannot become complete pass.

**Native candidate and claim boundary:** Exact current finite native Python engine fixtures; neither portable interpreter substitution nor arbitrary production conformance. Candidate source: `.flowguard/models/owners/python_function_state_verification/model.py`; runner: `.flowguard/verification/owners/python_function_state_verification/run_checks.py`. Current Source identity is not native PASS.

## Contract: problem-corpus-coverage-current

**Primary native model:** `problem_corpus_coverage`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Original finite checked-in corpus denominator, case kinds, bug classes and variant requirements.

**State:** Actual per-case terminal outcomes and original denominator membership.

**Required behavior:** Execute the checked-in corpus once, preserve failed/unknown results and reject missing case-kind/bug-class coverage, insufficient variants or reduced denominator.

**Effects:** execute declared corpus once; return exact coverage report.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Hidden failure/unknown, removed denominator member or insufficient declared coverage blocks completion.

**Native candidate and claim boundary:** Finite real corpus aggregation and independently checked mutations; no arbitrary software correctness, production workload or optimum architecture. Candidate source: `.flowguard/models/owners/problem_corpus_coverage/model.py`; runner: `.flowguard/verification/owners/problem_corpus_coverage/run_checks.py`. Current Source identity is not native PASS.

## Contract: evidence-storage-lifecycle-current

**Primary native model:** `evidence_storage_lifecycle`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Exact contained evidence root, object identities, retained heads/pins, owner/resource/episode lease and explicit finite collection plan.

**State:** Content-addressed objects, active reachability, exclusive lease token and reversible quarantine manifest.

**Required behavior:** Preserve exact object identity and active/pinned reachability; apply only a current explicit plan atomically, restore its quarantine and purge only an explicitly authorized quarantine.

**Effects:** persist exact objects/pointers; acquire/settle exact owned lease; explicitly quarantine/restore/purge contained plan members.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Content conflict, active/pinned removal, stale plan, partial move without rollback, foreign token/episode or live producer settlement blocks operation.

**Native candidate and claim boundary:** Dedicated finite storage identity/lease/GC/restore/purge cases. Validation kernel handoff permission does not prove actual storage mechanics. Candidate source: `.flowguard/models/owners/evidence_storage_lifecycle/model.py`; runner: `.flowguard/verification/owners/evidence_storage_lifecycle/run_checks.py`. Current Source identity is not native PASS.

## Contract: producer-execution-current

**Primary native model:** `development_process_flow`.

**Actor and trigger:** FlowGuard maintainer. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Frozen work/epoch, exact owner DAG/resources/commands and source/toolchain/environment/contained episode identities.

**State:** Durable one-full reservation, dependency order, owned PID with birth, retained descendants and actual terminal record.

**Required behavior:** Reserve one producer per frozen epoch, run only ordered owners, retain unresolved cleanup ownership and publish/reuse only authentic exact current non-cancelled terminal proof with known zero descendants.

**Effects:** reserve exact epoch once; start declared contained commands; retain residual leases/incidents; persist current owner proof only after terminal reconciliation.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Duplicate reservation, cyclic/unknown dependency, unordered resource, caller-green result, reused foreign PID, live/unknown descendants or cancelled/interrupted receipt blocks current pass.

**Native candidate and claim boundary:** Declared producer model cases plus separately observed exact implementation oracles; original release-identity freshness cases alone do not establish new producer protections. Candidate source: `.flowguard/models/owners/development_process_flow/model.py`; runner: `.flowguard/verification/owners/development_process_flow/run_checks.py`. Current Source identity is not native PASS.

## Contract: primary-path-authority-current

**Primary native model:** `primary_path_authority`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Path-sensitive contract, one primary authority, explicit alternate/manual candidates and independently required finite coverage.

**State:** Primary outcome, candidate dispositions and exact authority/coverage identities.

**Required behavior:** Keep one primary runtime authority, expose primary failure and allow manual recovery only within an explicit authored boundary.

**Effects:** return path authority decision; do not execute alternate recovery.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Automatic fallback, alternate facade/cache/old field masking primary failure or missing declared coverage blocks broad confidence.

**Native candidate and claim boundary:** Exact finite declared path counterexamples; no target runtime proof, automatic recovery or global optimum. Candidate source: `.flowguard/models/owners/primary_path_authority/model.py`; runner: `.flowguard/verification/owners/primary_path_authority/run_checks.py`. Current Source identity is not native PASS.

## Contract: model-code-test-alignment-current

**Primary native model:** `model_test_code_alignment`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Model obligations, external owner code contracts, exact tests/coverage edges, source audit, closure target and supplied execution leaves.

**State:** Bidirectional bindings, block-local failures, helper graph, sibling mechanism/provenance coverage and planned versus executed status.

**Required behavior:** Require exact obligation/code/test alignment, source assertions and current owner leaves while preserving sibling failure/provenance and incomplete design/execution boundaries.

**Effects:** read declared source/test contracts; return exact alignment findings; do not execute target checks.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Missing/extra behavior, internal-only assertion, path-only traceability, stale/foreign/sibling leaf, aggregate substitution, invalid provenance or cyclic/nonterminal helper blocks the relevant claim.

**Native candidate and claim boundary:** Checked-in MTA cases and explicitly executed ordinary tests. Whole-file inputs and unexecuted standalone family cases do not establish complete helper coverage. Candidate source: `.flowguard/models/owners/model_test_code_alignment/model.py`; runner: `.flowguard/verification/owners/model_test_code_alignment/run_checks.py`. Current Source identity is not native PASS.

## Contract: provider-neutral-blueprint-current

**Primary native model:** `implementation_blueprint`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Independent source inventory, accepted intent, authored semantics, exact code/test interfaces, initialized resources and frozen provider evidence.

**State:** Exact source/intent/provider identities, owner partitions, target snapshot and design/execution/admission axes.

**Required behavior:** Build and qualify a finite provider-neutral blueprint using independent bidirectional semantics and accepted intent; retain current provider lineage and separate design readiness from execution/observed-head confidence.

**Effects:** read exact source/intent/provider evidence; materialize only explicitly requested blueprint artifacts.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Omitted source, hidden writer, dynamic uncertainty, self-authorized/path-only semantics, unaccepted intent or stale/missing test/resource/provider lineage blocks understanding.

**Native candidate and claim boundary:** Finite manifest, target composition and native counterexamples; candidate structure alone does not prove target execution, whole-target sufficiency, implementation admission or release. Candidate source: `.flowguard/models/owners/implementation_blueprint/model.py`; runner: `.flowguard/verification/owners/implementation_blueprint/run_checks.py`. Current Source identity is not native PASS.

## Contract: native-hierarchical-composition-current

**Primary native model:** `hierarchical_model_mesh`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Finite declared parent/child topology, structural root, typed handoffs, child evidence and explicit feedback/retry/repair progress contracts.

**State:** Exact member coverage, unique structural parents, cross-boundary relation classes and current child/progress identities.

**Required behavior:** Conserve parent obligations and exact child identities through finite native recursive composition; expose sibling overlap and require independently verified current relation/progress evidence.

**Effects:** return hierarchy/composition/relation findings; do not launch child checks.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Missing/duplicate root, multiple parents, support promoted to parent, copied/stale/foreign/missing child receipt, hidden sibling conflict or unsupported progress blocks closure.

**Native candidate and claim boundary:** Declared finite native topology and recursive composition only; model_mesh_closure_model and mesh_target_split_derivation provide their own exact supporting contexts, never substitute for unexecuted children or external service facts. Candidate source: `.flowguard/models/owners/hierarchical_model_mesh/model.py`; runner: `.flowguard/verification/owners/hierarchical_model_mesh/run_checks.py`. Current Source identity is not native PASS.

## Contract: project-adoption-current

**Primary native model:** `project_adoption_version_gate`.

**Actor and trigger:** FlowGuard maintainer. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Exact target repository, current installed consumer/project identities, managed block and explicit adoption request.

**State:** Project version/currentness and registered FlowGuard versus target-owned artifact identity.

**Required behavior:** Inspect currentness without validation launch; write only explicitly requested direct-current registered adoption artifacts and require affected checks before claiming adoption completion.

**Effects:** read project currentness; write explicit registered adoption artifacts only on adoption request.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Missing package, bypassed managed block, unvalidated replacement, target-owned/lookalike rewrite, author dependency or validation launched from a read blocks the claim.

**Native candidate and claim boundary:** Finite current adoption/ownership cases. Ordinary consumer use needs no SkillGuard imports or author receipts; logs do not prove target execution, migrations or publication. Candidate source: `.flowguard/models/owners/project_adoption_version_gate/model.py`; runner: `.flowguard/verification/owners/project_adoption_version_gate/run_checks.py`. Current Source identity is not native PASS.

## Contract: runtime-writer-gateway-current

**Primary native model:** `runtime_gateway_adoption`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Critical state surfaces, exact writer inventory, declared gateway level and structured current proof.

**State:** Required/discovered writers, justified exclusions and exact proof/status identities.

**Required behavior:** Require current structured inventory and explicit gateway/proof binding for every declared critical writer; retain unresolved writers.

**Effects:** return inventory/gateway findings; do not execute writes.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Opaque inventory-only claims, stale/nonpassing/missing proof, uncovered critical surface or unjustified exclusion blocks gateway confidence.

**Native candidate and claim boundary:** Declared finite writer/adoption cases. Registration alone neither proves all real writers use the gateway nor protects unobserved target state. Candidate source: `.flowguard/models/owners/runtime_gateway_adoption/model.py`; runner: `.flowguard/verification/owners/runtime_gateway_adoption/run_checks.py`. Current Source identity is not native PASS.

## Contract: unknown-state-closure-current

**Primary native model:** `state_closure_gate`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Explicit function/state model, finite declared cases, representative unknown/other state and authored closure policy.

**State:** Known/unknown classification, safe resolution, effect admission and explicit/inferred policy distinction.

**Required behavior:** Keep unknown state visible until explicit safe resolution, block early effects and prevent completeness while closure policy remains inferred.

**Effects:** return state-closure findings; do not authorize target effects from enumeration alone.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Absent unknown case, unknown treated as normal, early effect or inferred policy promoted to full confidence blocks completion.

**Native candidate and claim boundary:** Finite declared closure cases, not unbounded state-space completeness or arbitrary software safety. Candidate source: `.flowguard/models/owners/state_closure_gate/model.py`; runner: `.flowguard/verification/owners/state_closure_gate/run_checks.py`. Current Source identity is not native PASS.

## Contract: plan-detailing-current

**Primary native model:** `plan_detailing_compiler`.

**Actor and trigger:** FlowGuard maintainer. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Scoped plan, requirement, behavior plane, exact owners/dependencies, effects and required evidence.

**State:** Action/gate order, failure/rework branches and visible incomplete planning fields.

**Required behavior:** Compile explicit actions with validation/failure/rework/effect/final-evidence gates and preserve typed scope boundaries.

**Effects:** return plan candidate and gaps; do not execute steps.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Vague prose, omitted gate/owner/failure/rework/effect or scoped evidence promoted to whole-task confidence blocks plan completion.

**Native candidate and claim boundary:** Declared plan-detailing cases; a plan proves neither execution/native pass nor release/future-agent compliance. Candidate source: `.flowguard/models/owners/plan_detailing_compiler/model.py`; runner: `.flowguard/verification/owners/plan_detailing_compiler/run_checks.py`. Current Source identity is not native PASS.

## Contract: runtime-path-evidence-current

**Primary native model:** `runtime_path_evidence`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Structured runtime leaf node observations, exact source/model/owner/path obligation and parent handoff.

**State:** Leaf execution status, path alignment, child currentness and scoped/full confidence distinction.

**Required behavior:** Bind only current structured leaf observations to exact runtime obligations and retain stale/missing child evidence and scoped remainders.

**Effects:** return path/alignment projections; do not launch replay or native owners.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Ad hoc logs, missing leaf, stale child/source or scoped/missing evidence promoted to full parent confidence blocks the claim.

**Native candidate and claim boundary:** Declared finite path native cases and exact supplied observations, not new target execution or whole-software confidence. Candidate source: `.flowguard/models/owners/runtime_path_evidence/model.py`; runner: `.flowguard/verification/owners/runtime_path_evidence/run_checks.py`. Current Source identity is not native PASS.

## Contract: architecture-reduction-current

**Primary native model:** `architecture_reduction`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Explicit current architecture responsibilities, independent accepted semantics, required target goals and necessity/preservation/retirement proof.

**State:** Current versus desired structure, alternative ownership, preserved variants and unresolved required improvement.

**Required behavior:** Review authored reduce/retain/retire decisions using current independent necessity and semantics evidence, preserve legitimate variants and keep required improvement unfinished until its real outcome closes.

**Effects:** return architecture finding/candidate decisions; never rewrite target source automatically.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Self-declared semantic hash, hidden necessary responsibility, proof-free merge/retirement or optional estimate replacing required target outcome blocks closure.

**Native candidate and claim boundary:** Exact native reduction candidates and independent evidence; no universally best architecture, target auto-edit or optimum/cost-cap proof. Candidate source: `.flowguard/models/owners/architecture_reduction/model.py`; runner: `.flowguard/verification/owners/architecture_reduction/run_checks.py`. Current Source identity is not native PASS.

## Contract: code-structure-partition-current

**Primary native model:** `structure_refactor_mesh`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Declared target code responsibilities, public facade, dependency/configuration/effect boundaries and owned partition proposal.

**State:** Exact owner/member coverage, sibling overlap, facade/delegation and retained side-effect contracts.

**Required behavior:** Review explicit code partitions that conserve responsibilities and exact public/dependency/config/effect interfaces; expose overlap/unowned or foreign effects.

**Effects:** return partition/refactor findings; no target refactor executes.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Missing owner/member, hidden facade/dependency/config/effect, ownership collision or source-shaped partition without semantic preservation blocks closure.

**Native candidate and claim boundary:** Finite checked-in partition model and declared contexts. An abstract model-only pass is not proof that arbitrary target code was partitioned correctly. Candidate source: `.flowguard/models/owners/structure_refactor_mesh/model.py`; runner: `.flowguard/verification/owners/structure_refactor_mesh/run_checks.py`. Current Source identity is not native PASS.

## Contract: model-impact-freshness-current

**Primary native model:** `model_impact_freshness_gate`.

**Actor and trigger:** FlowGuard maintainer. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Exact upgrade/source change, original model dependency scope, previous receipt and explicit impact/same-output evidence.

**State:** Affected/unaffected classification, input identity and required update/revalidation dispositions.

**Required behavior:** Classify impact before reusing model confidence; preserve affected model/test updates and demand current affected rerun or exact independently verified same-output proof.

**Effects:** return impact/revalidation demand; do not launch owners from freshness reading.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Prior green without impact review, changed dependency with no same-output proof or affected model without current updated evidence blocks reuse.

**Native candidate and claim boundary:** Finite impact classification native model; declared source edges alone are freshness inputs and do not establish implementation behavior. Candidate source: `.flowguard/models/owners/model_impact_freshness_gate/model.py`; runner: `.flowguard/verification/owners/model_impact_freshness_gate/run_checks.py`. Current Source identity is not native PASS.

## Contract: existing-model-preflight-current

**Primary native model:** `existing_model_preflight`.

**Actor and trigger:** FlowGuard maintainer. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Existing current model inventory, task intent, candidate scope, required confidence and exact current evidence.

**State:** Existing ownership, live model gaps, task sufficiency and selected/full scope distinctions.

**Required behavior:** Reuse/extend the actual existing owner before duplicate modeling, preserve unresolved task/full-understanding gaps and require current evidence for the exact admitted scope.

**Effects:** read model inventory and return preflight/admission findings; do not execute checks.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Stale/foreign/vacuous model, unsupported narrowed scope or task-local slice promoted to whole-target sufficiency blocks admission.

**Native candidate and claim boundary:** Finite existing-model preflight cases and supplied current task evidence; no unconditional all-software understanding or automatic implementation authority. Candidate source: `.flowguard/models/owners/existing_model_preflight/model.py`; runner: `.flowguard/verification/owners/existing_model_preflight/run_checks.py`. Current Source identity is not native PASS.

## Contract: topology-hazard-current

**Primary native model:** `model_topology_hazard_review`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Declared workflow/model topology, loop/feedback/retry/repair relations and explicit progress/termination criteria.

**State:** Exact relations, structural/cyclic hazards and current progress evidence.

**Required behavior:** Expose hazards and demand an explicit safe progress/termination boundary for declared recursive or iterative relations.

**Effects:** return topology hazard findings; no topology rewrite or owner execution.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Hidden cycle, unclassified relation or assumed progress without declared evidence blocks safe topology confidence.

**Native candidate and claim boundary:** Finite checked-in topology hazard model; runtime conformance and arbitrary target termination remain independently unproved. Candidate source: `.flowguard/models/owners/model_topology_hazard_review/model.py`; runner: `.flowguard/verification/owners/model_topology_hazard_review/run_checks.py`. Current Source identity is not native PASS.

## Contract: contract-exhaustion-current

**Primary native model:** `contract_source_audit`.

**Actor and trigger:** FlowGuard application caller. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Explicit external contracts, finite axes/cells/interactions, required outcome oracles and exact code/test assertions.

**State:** Original declared cell denominator, normative obligation-to-code/test bindings and current covered/missing outcome identity.

**Required behavior:** Preserve finite required contract cells and independently inspect code/test support; expose missing/extraneous behavior and uncovered interactions instead of using green row counts as exhaustion.

**Effects:** return source-audit/finite coverage plans and gaps; do not execute target test matrix.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Reduced denominator, missing oracle/cell, source symbol mismatch, incorrect input/output/write/effect or tests lacking target external assertion blocks the relevant claim.

**Native candidate and claim boundary:** Existing contract_source_audit native scope proves declared Python code/test source counterexamples. Complete Cartesian exhaustion requires its own actual current cell/oracle evidence; abstract owner policy or source inputs cannot substitute. Candidate source: `.flowguard/models/owners/contract_source_audit/model.py`; runner: `.flowguard/verification/owners/contract_source_audit/run_checks.py`. Current Source identity is not native PASS.

## Contract: risk-minimum-model-entry-current

**Primary native model:** `minimum_valuable_model_entry`.

**Actor and trigger:** FlowGuard maintainer. A caller requests this declared behavior or relies on its exact functional result.

**Input:** Bounded task/model purpose, protected failure, state, effects, completion evidence, executable known-bad and exact model/code/test bindings.

**State:** Declared risk boundary, current binding completeness and optional reuse versus required minimum distinction.

**Required behavior:** Admit a bounded useful model only when purpose/error/state/effects/completion and executable counterexample/current bindings are explicit; keep optional template work outside required ordinary entry.

**Effects:** return minimum-entry/risk findings; no target execution or template work is forced.

**Completion:** The exact requested report or authorized operation satisfies its declared terminal behavior with current independently owned native and implementation evidence. Missing, stale, scoped, UNKNOWN and NOT_RUN remain explicit.

**Failure boundary:** Description-only purpose, missing error/state/effect/completion, nonexecutable bad case or incomplete binding blocks entry.

**Native candidate and claim boundary:** Finite minimum-entry native cases. Entry adequacy is functional and task scoped; it is not global optimality or a numerical token/cost cap. Candidate source: `.flowguard/models/owners/minimum_valuable_model_entry/model.py`; runner: `.flowguard/verification/owners/minimum_valuable_model_entry/run_checks.py`. Current Source identity is not native PASS.


## Contract: flowguard-example-demonstration-current

**Primary native model:** `template_public_release`.

**Actor and trigger:** FlowGuard example reader or caller. Inspect, publish or execute a selected checked-in example as a reusable demonstration.

**Input:** Selected example source and its explicit fixture inputs, local workflow/state, contracts, invariants and failure oracle.

**State:** Only the selected example fixture and its observed finite result; unrelated applications and examples remain unproved.

**Required behavior:** Expose each example as a declared demonstration with an explicit input/state/effect/terminal/failure boundary; preserve its actual distinct workflow and never promote a sample or core-engine result to production or unrelated-example proof.

**Effects:** Only effects declared by the selected example contract, after explicit execution.

**Completion:** The selected example has a complete declared fixture/failure boundary; execution confidence additionally requires its own actual current independently observed result.

**Failure boundary:** Missing example contract, unknown fixture/provider, absent oracle, an unexecuted example or a failing selected run cannot become a successful execution claim.

**Native candidate and claim boundary:** Template/example retention and declared completeness governance; actual selected-example behavior requires its own execution. Engine and corpus support applies only to their explicit real finite fixtures. Current Source identity is not native PASS.
