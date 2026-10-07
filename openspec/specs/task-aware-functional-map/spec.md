## Purpose

Provide independently evidenced functional understanding and architecture direction inside a finite current software context.

## outcome:r8:task_functional_state_visible

The public functional read must expose the current task, actual satisfied and missing outcomes, original evidence pointers, and the next responsible owner. Its obligation is `obligation:r8:public_read_consumes_verified_task_context`.

## outcome:r8:only_affected_native_execution_required

The affected owner planner must require new native execution for changed owners and preserve exact current reuse for the unaffected owners. Its obligation is `obligation:r8:preserve_unaffected_owner_reuse`.

```flowguard-architecture-objectives
{
  "schema": "flowguard.architecture_objective_source.v1",
  "objectives": [
    {
      "objective_id": "objective:r8:public_task_context_is_readable",
      "required": true,
      "model_ids": [
        "authoritative_model_system"
      ],
      "responsibility_ids": [
        "responsibility:r8:public-functional-read"
      ],
      "applicable_input_class_ids": [
        "task:selected_current"
      ],
      "constraint_kind": "functional_obligations",
      "constraint_values": {
        "required_obligation_ids": [
          "obligation:r8:public_read_consumes_verified_task_context"
        ],
        "required_code_contract_ids": [
          "code-contract:r8:public-functional-read"
        ],
        "native_case_pairs": [
          {
            "owner_id": "model:authoritative_model_system",
            "source_case_id": "native-scenario:authoritative_model_system:r8_public_task_context_read",
            "satisfied_observed_status": "ok"
          }
        ]
      },
      "native_owner_id": "model:authoritative_model_system",
      "protected_failure_ids": [
        "failure:authoritative_model_system:frozen_scope_not_authenticated"
      ]
    },
    {
      "objective_id": "objective:r8:unaffected_native_owners_are_reused",
      "required": true,
      "model_ids": [
        "authoritative_model_system"
      ],
      "responsibility_ids": [
        "responsibility:r8:affected-native-selection"
      ],
      "applicable_input_class_ids": [
        "planner:one_changed_owner"
      ],
      "constraint_kind": "functional_obligations",
      "constraint_values": {
        "required_obligation_ids": [
          "obligation:r8:preserve_unaffected_owner_reuse"
        ],
        "required_code_contract_ids": [
          "code-contract:r8:affected-native-selection"
        ],
        "native_case_pairs": [
          {
            "owner_id": "model:authoritative_model_system",
            "source_case_id": "native-scenario:authoritative_model_system:r8_affected_owner_selection",
            "satisfied_observed_status": "ok"
          }
        ]
      },
      "native_owner_id": "model:authoritative_model_system",
      "protected_failure_ids": [
        "failure:authoritative_model_system:frozen_scope_not_authenticated"
      ]
    },
    {
      "objective_id": "objective:r9:action_location_is_current_and_resolvable",
      "required": true,
      "model_ids": [
        "authoritative_model_system"
      ],
      "responsibility_ids": [
        "responsibility:r9:pointer-detail-navigation"
      ],
      "applicable_input_class_ids": [
        "pointer:accepted_current",
        "pointer:wrong_hash_or_head"
      ],
      "constraint_kind": "functional_obligations",
      "constraint_values": {
        "required_obligation_ids": [
          "obligation:r9:resolve_current_action_location"
        ],
        "required_code_contract_ids": [
          "code-contract:r9:pointer-detail-navigation"
        ],
        "native_case_pairs": [
          {
            "owner_id": "model:authoritative_model_system",
            "source_case_id": "native-scenario:authoritative_model_system:r9_pointer_detail_navigation",
            "satisfied_observed_status": "ok"
          }
        ]
      },
      "native_owner_id": "model:authoritative_model_system",
      "protected_failure_ids": [
        "r8-functional-actual-checks:r9_pointer_detail_navigation"
      ]
    },
    {
      "objective_id": "objective:r9:finite_growth_is_original_and_visible",
      "required": true,
      "model_ids": [
        "authoritative_model_system"
      ],
      "responsibility_ids": [
        "responsibility:r9:finite-growth-observation"
      ],
      "applicable_input_class_ids": [
        "growth:finite_present_and_missing",
        "growth:unknown_admission"
      ],
      "constraint_kind": "functional_obligations",
      "constraint_values": {
        "required_obligation_ids": [
          "obligation:r9:preserve_finite_growth_and_unknowns"
        ],
        "required_code_contract_ids": [
          "code-contract:r9:finite-growth-observation"
        ],
        "native_case_pairs": [
          {
            "owner_id": "model:authoritative_model_system",
            "source_case_id": "native-scenario:authoritative_model_system:r9_finite_growth_observation",
            "satisfied_observed_status": "ok"
          }
        ]
      },
      "native_owner_id": "model:authoritative_model_system",
      "protected_failure_ids": [
        "r8-functional-actual-checks:r9_finite_growth_observation"
      ]
    }
  ]
}
```

```flowguard-r8-hard-semantics
{
  "responsibility:r8:public-functional-read": {
    "accepted_inputs": {
      "contract": "A current independently verified task_context_ref is readable for its selected accepted models"
    },
    "rejected_inputs": {
      "contract": "An unknown request key or an unauthenticated task context is rejected"
    },
    "outputs": {
      "contract": "The public result contains task sufficient understanding and required improvement gaps"
    },
    "terminal_states": {
      "contract": "Only independently verified current functional evidence can permit stopping"
    },
    "protected_errors": {
      "contract": "Malformed requests and stale or missing evidence remain explicit errors or gaps"
    },
    "recovery": {
      "contract": "A rejected request does not prevent a subsequent valid bounded read"
    },
    "progress": {
      "contract": "Task requested outcomes and unresolved required improvements remain visible"
    },
    "permissions": {
      "contract": "Caller constructed verification cannot authorize a task completion claim"
    },
    "authority": {
      "contract": "The result is bound to independently accepted head and selected model Source inputs"
    },
    "parent_interfaces": {
      "contract": "The public read consumes an exact current task context reference"
    },
    "child_interfaces": {
      "contract": "The result preserves the producer report and independent verification references"
    },
    "intent": {
      "contract": "Only the requested task outcomes and bounded architecture objectives are evaluated"
    },
    "behavior_commitments": {
      "contract": "Understanding and required improvement gaps remain separate from observation acceptance"
    },
    "evidence_obligations": {
      "contract": "Current task context proof is required for the selected task functional claim"
    },
    "state_transitions": {
      "mode": "read_only",
      "claim": "no authority transition"
    },
    "field_transitions": {
      "mode": "inputs_preserved",
      "claim": "observations do not mutate caller arguments"
    },
    "side_effects": {
      "mode": "read_only",
      "claim": "no authority or Source writes"
    },
    "order": {
      "mode": "single_pass",
      "claim": "validate inputs before deriving the result"
    },
    "retry": {
      "mode": "not_applicable",
      "reason": "this synchronous finite function does not retry producers"
    },
    "timeout": {
      "mode": "not_applicable",
      "reason": "this function does not launch an execution owner"
    },
    "cancellation": {
      "mode": "not_applicable",
      "reason": "no background owner is launched by this bounded call"
    },
    "fairness": {
      "mode": "not_applicable",
      "reason": "the bounded call does not schedule competing execution owners"
    },
    "oracles": {
      "mode": "executed",
      "claim": "positive and rejected-input observations are preserved separately"
    }
  },
  "responsibility:r8:affected-native-selection": {
    "accepted_inputs": {
      "contract": "A complete current native manifest and independently current finite owner receipts are planned"
    },
    "rejected_inputs": {
      "contract": "Missing manifest or unregistered source inventory cannot produce a reusable plan"
    },
    "outputs": {
      "contract": "Only owners whose declared inputs changed execute while unaffected exact current owners are reused"
    },
    "terminal_states": {
      "contract": "The planner returns a frozen complete owner denominator without executing owners"
    },
    "protected_errors": {
      "contract": "Invalid manifest and stale native evidence block reuse"
    },
    "recovery": {
      "contract": "A rejected invalid root does not invalidate a subsequent correct finite plan"
    },
    "progress": {
      "contract": "The plan identifies each actual execute or reuse disposition"
    },
    "permissions": {
      "contract": "An affected caller scope cannot narrow the complete native owner denominator"
    },
    "authority": {
      "contract": "Reuse requires current input, native result and receipt identities"
    },
    "parent_interfaces": {
      "contract": "The planner consumes manifest, affected IDs and the exact private receipt root"
    },
    "child_interfaces": {
      "contract": "The frozen plan preserves dependencies, denominator and reusable receipt bindings"
    },
    "intent": {
      "contract": "Preserve unaffected owner reuse while retaining the complete safety obligations"
    },
    "behavior_commitments": {
      "contract": "Changing one independent owner does not force unrelated current owners to execute"
    },
    "evidence_obligations": {
      "contract": "A reusable row must retain its own exact current native producer receipt"
    },
    "state_transitions": {
      "mode": "read_only",
      "claim": "no authority transition"
    },
    "field_transitions": {
      "mode": "inputs_preserved",
      "claim": "observations do not mutate caller arguments"
    },
    "side_effects": {
      "mode": "read_only",
      "claim": "no authority or Source writes"
    },
    "order": {
      "mode": "single_pass",
      "claim": "validate inputs before deriving the result"
    },
    "retry": {
      "mode": "not_applicable",
      "reason": "this synchronous finite function does not retry producers"
    },
    "timeout": {
      "mode": "not_applicable",
      "reason": "this function does not launch an execution owner"
    },
    "cancellation": {
      "mode": "not_applicable",
      "reason": "no background owner is launched by this bounded call"
    },
    "fairness": {
      "mode": "not_applicable",
      "reason": "the bounded call does not schedule competing execution owners"
    },
    "oracles": {
      "mode": "executed",
      "claim": "positive and rejected-input observations are preserved separately"
    }
  },
  "responsibility:r9:finite-growth-observation": {
    "accepted_inputs": {
      "contract": "Only explicitly declared finite present/missing paths and exact old/new rename unions are observed; required neighbor inventory remains bounded"
    },
    "authority": {
      "contract": "Accepted model identity and independent original evidence authenticate only the declared finite claim"
    },
    "behavior_commitments": {
      "contract": "Empty or missing evidence never proves task closure or whole-software optimality"
    },
    "cancellation": {
      "mode": "not_applicable",
      "reason": "The bounded interface does not create a background execution owner"
    },
    "child_interfaces": {
      "contract": "Preserve strict original artifacts and actual finite observation identities"
    },
    "evidence_obligations": {
      "contract": "Actual native input-oracle observations remain bound to Source, CodeContract, declared contexts and original owner evidence"
    },
    "fairness": {
      "mode": "not_applicable",
      "reason": "The finite synchronous call does not schedule competing execution owners"
    },
    "field_transitions": {
      "claim": "Caller request fields and protected Source/current identities are unchanged",
      "mode": "inputs_preserved"
    },
    "intent": {
      "contract": "Expose current understanding or its precise original insufficiency within the declared scope"
    },
    "oracles": {
      "claim": "Actual positive and negative calls remain separate raw observations",
      "mode": "executed"
    },
    "order": {
      "claim": "Authenticate current inputs before deriving or publishing their result",
      "mode": "single_pass"
    },
    "outputs": {
      "contract": "finite_growth_gap_visible preserves actual existing or missing states, original observation fingerprints and exact unknown boundary-admission gaps"
    },
    "parent_interfaces": {
      "contract": "Consume exact admitted task, scope and original current references"
    },
    "permissions": {
      "contract": "Request scope cannot waive exact required functional evidence or grant another authority"
    },
    "progress": {
      "contract": "The original current-or-gap or pointer availability disposition is visible"
    },
    "protected_errors": {
      "contract": "Invalid references and unknown required scope preserve original rejection or needs_evidence"
    },
    "recovery": {
      "contract": "A rejected or insufficient call does not authorize success and a later valid independent call remains usable"
    },
    "rejected_inputs": {
      "contract": "Malformed, foreign, stale or absent required evidence cannot create successful task closure"
    },
    "retry": {
      "mode": "not_applicable",
      "reason": "This finite synchronous call does not schedule or retry native execution owners"
    },
    "side_effects": {
      "claim": "The growth observer reads actual declared finite paths without Source, authority or evidence publication",
      "mode": "read_only"
    },
    "state_transitions": {
      "claim": "Accepted Source authority remains unchanged; only explicitly owned normal-task evidence publication may write",
      "mode": "bounded_observation"
    },
    "terminal_states": {
      "contract": "Unknown admission remains needs_evidence and absent observation remains NOT_OBSERVED; finite observations never establish whole-tree completeness"
    },
    "timeout": {
      "mode": "not_applicable",
      "reason": "No background validation owner is launched by this bounded call"
    }
  },
  "responsibility:r9:pointer-detail-navigation": {
    "accepted_inputs": {
      "contract": "A compact pointer from this finite fixture own accepted current detail, actual native material and original receipt resolves exactly"
    },
    "authority": {
      "contract": "Accepted model identity and independent original evidence authenticate only the declared finite claim"
    },
    "behavior_commitments": {
      "contract": "Empty or missing evidence never proves task closure or whole-software optimality"
    },
    "cancellation": {
      "mode": "not_applicable",
      "reason": "The bounded interface does not create a background execution owner"
    },
    "child_interfaces": {
      "contract": "Preserve strict original artifacts and actual finite observation identities"
    },
    "evidence_obligations": {
      "contract": "Actual native input-oracle observations remain bound to Source, CodeContract, declared contexts and original owner evidence"
    },
    "fairness": {
      "mode": "not_applicable",
      "reason": "The finite synchronous call does not schedule competing execution owners"
    },
    "field_transitions": {
      "claim": "Caller request fields and protected Source/current identities are unchanged",
      "mode": "inputs_preserved"
    },
    "intent": {
      "contract": "Expose current understanding or its precise original insufficiency within the declared scope"
    },
    "oracles": {
      "claim": "Actual positive and negative calls remain separate raw observations",
      "mode": "executed"
    },
    "order": {
      "claim": "Authenticate current inputs before deriving or publishing their result",
      "mode": "single_pass"
    },
    "outputs": {
      "contract": "current_pointer_resolution_state_visible returns actual current action targets when a pointer exists; authenticated absence supplies no invented location or task closure"
    },
    "parent_interfaces": {
      "contract": "Consume exact admitted task, scope and original current references"
    },
    "permissions": {
      "contract": "Request scope cannot waive exact required functional evidence or grant another authority"
    },
    "progress": {
      "contract": "The original current-or-gap or pointer availability disposition is visible"
    },
    "protected_errors": {
      "contract": "Invalid references and unknown required scope preserve original rejection or needs_evidence"
    },
    "recovery": {
      "contract": "A rejected or insufficient call does not authorize success and a later valid independent call remains usable"
    },
    "rejected_inputs": {
      "contract": "Wrong detail raw hash, foreign head, missing original detail and stale Source targets cannot resolve as current action locations"
    },
    "retry": {
      "mode": "not_applicable",
      "reason": "This finite synchronous call does not schedule or retry native execution owners"
    },
    "side_effects": {
      "claim": "Pointer resolution reads existing accepted detail and current finite Source references with zero producers and writes",
      "mode": "read_only"
    },
    "state_transitions": {
      "claim": "Accepted Source authority remains unchanged; only explicitly owned normal-task evidence publication may write",
      "mode": "bounded_observation"
    },
    "terminal_states": {
      "contract": "A pointer location resolves only from accepted detail; absence is a bounded availability state and missing evidence remains rejected"
    },
    "timeout": {
      "mode": "not_applicable",
      "reason": "No background validation owner is launched by this bounded call"
    }
  }
}
```

## Requirements

### Requirement: Task-aware functional map
A verified task context SHALL expose current functional outcomes and precise missing evidence pointers without executing a producer during public read.

#### Scenario: A verified task context is read
- **WHEN** a verified task context is read
- **THEN** The reader returns actual task sufficiency, required outcome gaps and the next responsible owner.

### Requirement: Finite growth enters normal task understanding
Normal task production SHALL preserve explicitly declared finite software path changes and independently observed current path states through original references. Public read SHALL consume those references without executing a producer, scanning a repository or mutating authority. Unobserved scope SHALL remain explicit.

#### Scenario: A path is added, deleted or renamed
- **WHEN** a task declares a finite path change
- **THEN** its original request and real present, missing or unavailable observations remain bound to the task and current accepted identity, with any missing model binding and next owner visible.

#### Scenario: No change was observed
- **WHEN** a task has no declared observed changes
- **THEN** the result retains NOT_OBSERVED rather than inferring growth coverage from selected model paths.

#### Scenario: Growth evidence is stale or foreign
- **WHEN** the task, head, source, path scope or original evidence hash does not match
- **THEN** the read rejects the evidence and cannot close the task from it.

### Requirement: Insufficient tasks publish authentic diagnostics
A task with insufficient functional evidence SHALL expose its original terminal reason, first missing input and next responsible owner through independently authenticated receipt-free diagnostic references. Such a diagnostic SHALL remain needs_evidence and SHALL NOT grant verified task closure.

#### Scenario: Preflight or maturation is insufficient
- **WHEN** production cannot establish current functional sufficiency
- **THEN** public read preserves the original failure or gap and next action without fabricating a successful receipt.

#### Scenario: A caller forges a completed diagnostic
- **WHEN** diagnostic fields, raw reports, current identities or a claimed next owner do not match original evidence
- **THEN** the reader rejects that claim.

### Requirement: Current action detail and unknown coverage are readable
A compact understanding result SHALL expose proven current state, required targets, precise gaps, compromises, unknown scope and original action detail references. An action location SHALL be bound to actual current code, contract, scope and retained obligations. Empty evidence SHALL NOT imply whole-software optimality.

#### Scenario: An authentic action target is available
- **WHEN** current accepted detail contains a real action target
- **THEN** strict resolution returns its actual path and symbol and rejects wrong-hash, foreign or stale references.

#### Scenario: No current action pointer exists
- **WHEN** an independently authenticated current projection contains zero selected pointers
- **THEN** the availability result is not_applicable, actual task closure is not claimed, and a request for a missing location remains needs_evidence.

### Requirement: Bounded reads share current evidence without weakening checks
One ordinary read invocation SHALL share authenticated original inputs and complete typed current state, consume required selected native proof and perform a fresh end guard. Separate invocations SHALL independently establish currentness. Bounded pages SHALL retain exact size limits and lossless reassembly.

#### Scenario: A selected task reads a shared input repeatedly
- **WHEN** multiple validators need the same input inside one invocation
- **THEN** they use the same verified initial bytes while a separate ending read still detects drift.

#### Scenario: An unselected native leaf is stale
- **WHEN** an ordinary task has sufficient current selected leaves but an unrelated leaf is stale
- **THEN** selected sufficiency does not become a global currentness claim, and complete validation still rejects the stale complete-set claim.

## outcome:r9:current_pointer_resolution_state_visible

Resolve a pointer only from the current accepted detail and independently current Source, CodeContract, native and receipt identities. Expose its actual location and retained obligations. A wrong hash or head remains rejected. An accepted map with zero pointers reports `not_applicable`; it does not claim that a location was resolved or that an improvement task closed. Its obligation is `obligation:r9:resolve_current_action_location`.

## outcome:r9:finite_growth_gap_visible

Observe only the explicitly declared finite present and missing paths, including both sides of a rename. Preserve original growth gaps, checked paths and input references. Unknown ownership requires boundary admission. With no declared observation report `NOT_OBSERVED`; it does not imply complete live discovery. Its obligation is `obligation:r9:preserve_finite_growth_and_unknowns`.
