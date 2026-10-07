## Purpose

Provide independently evidenced functional understanding and architecture direction inside a finite current software context.

## outcome:r8:related_overlap_and_gap_visible

The architecture comparison must expose related overlap, distinct context remainders and any unresolved hard semantic differences. Its obligation is `obligation:r8:compare_only_context_related_responsibilities`.

```flowguard-architecture-objectives
{
  "schema": "flowguard.architecture_objective_source.v1",
  "objectives": [
    {
      "objective_id": "objective:r8:architecture_comparison_uses_scoped_candidates",
      "required": true,
      "model_ids": [
        "model_maturation_loop"
      ],
      "responsibility_ids": [
        "responsibility:r8:contextual-architecture-comparison"
      ],
      "applicable_input_class_ids": [
        "comparison:distinct_context",
        "comparison:related_overlap"
      ],
      "constraint_kind": "functional_obligations",
      "constraint_values": {
        "required_obligation_ids": [
          "obligation:r8:compare_only_context_related_responsibilities"
        ],
        "required_code_contract_ids": [
          "code-contract:r8:contextual-architecture-comparison"
        ],
        "native_case_pairs": [
          {
            "owner_id": "model:model_maturation_loop",
            "source_case_id": "case:model_maturation_loop:r8_context_indexed_comparison",
            "satisfied_observed_status": "ok"
          }
        ]
      },
      "native_owner_id": "model:model_maturation_loop",
      "protected_failure_ids": [
        "failure:model_maturation_loop:context_remainder_erased"
      ]
    },
    {
      "objective_id": "objective:r9:normal_task_has_current_result_or_original_gap",
      "required": true,
      "model_ids": [
        "model_maturation_loop"
      ],
      "responsibility_ids": [
        "responsibility:r9:normal-task-context"
      ],
      "applicable_input_class_ids": [
        "normal:current_verified",
        "normal:original_diagnostic"
      ],
      "constraint_kind": "functional_obligations",
      "constraint_values": {
        "required_obligation_ids": [
          "obligation:r9:publish_current_task_or_original_gap"
        ],
        "required_code_contract_ids": [
          "code-contract:r9:normal-task-context"
        ],
        "native_case_pairs": [
          {
            "owner_id": "model:model_maturation_loop",
            "source_case_id": "case:model_maturation_loop:r9_normal_task_context",
            "satisfied_observed_status": "ok"
          }
        ]
      },
      "native_owner_id": "model:model_maturation_loop",
      "protected_failure_ids": [
        "r8-functional-actual-checks:r9_normal_task_context"
      ]
    }
  ]
}
```

```flowguard-r8-hard-semantics
{
  "responsibility:r8:contextual-architecture-comparison": {
    "accepted_inputs": {
      "contract": "Current independently admitted responsibility semantics and their actual input contexts are compared"
    },
    "rejected_inputs": {
      "contract": "Unverified responsibilities or caller handed-off equivalence cannot create a merge suggestion"
    },
    "outputs": {
      "contract": "Related overlapping contexts can expose duplicate boundaries without erasing distinct remainders"
    },
    "terminal_states": {
      "contract": "Unknown semantic evidence remains an observation gap"
    },
    "protected_errors": {
      "contract": "Unlicensed adapters and canonical handoffs are rejected explicitly"
    },
    "recovery": {
      "contract": "A rejected handoff leaves a subsequent bounded comparison available"
    },
    "progress": {
      "contract": "The actual overlapping and remaining context sets are preserved in the result"
    },
    "permissions": {
      "contract": "Only independently admitted implementation-boundary semantics authorize duplicate comparison"
    },
    "authority": {
      "contract": "Responsibility semantics are independently bound to current native input oracle evidence"
    },
    "parent_interfaces": {
      "contract": "The comparison receives declared responsibilities and admitted semantic reviews"
    },
    "child_interfaces": {
      "contract": "Relations, findings, bounded rewrites and observation gaps remain distinct outputs"
    },
    "intent": {
      "contract": "Compare the requested responsibility contexts without generalizing to unrelated whole software"
    },
    "behavior_commitments": {
      "contract": "Equivalent contexts preserve all unmatched contextual variants"
    },
    "evidence_obligations": {
      "contract": "Missing or stale input oracle evidence cannot be silently treated as verified"
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
  "responsibility:r9:normal-task-context": {
    "accepted_inputs": {
      "contract": "A normal task with exact current task facts and original finite native leaf evidence may publish verified maturation; a task with an original unmet outcome publishes a receipt-free diagnostic"
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
      "contract": "normal_task_current_or_gap_visible retains real task context and original verified result or original first-gap/report/terminal references"
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
      "claim": "The normal producer creates owned immutable task and maturation evidence; previously existing Source/native evidence and accepted head remain unchanged",
      "mode": "owned_evidence_publication"
    },
    "state_transitions": {
      "claim": "Accepted Source authority remains unchanged; only explicitly owned normal-task evidence publication may write",
      "mode": "bounded_observation"
    },
    "terminal_states": {
      "contract": "Verified task sufficiency remains independently verified; insufficient production remains blocked or needs_evidence with no maturation receipt"
    },
    "timeout": {
      "mode": "not_applicable",
      "reason": "No background validation owner is launched by this bounded call"
    }
  }
}
```

## Requirements

### Requirement: Context-indexed architecture direction
Architecture comparisons SHALL use authenticated related responsibility contexts and retain every relevant member, obligation and remainder.

#### Scenario: Unrelated responsibilities share an input label
- **WHEN** unrelated responsibilities share an input label
- **THEN** No comparison is invented solely from the shared input label.

### Requirement: Normal production exposes a current result or original gap
The normal task producer SHALL establish requested functional outcomes using current model responsibilities, contracts, required neighbor scope and original independent evidence, or preserve the original insufficient-result diagnostic. User execution choice SHALL NOT waive missing required evidence.

#### Scenario: A normal task has sufficient current evidence
- **WHEN** every requested outcome and required scope obligation has current independent evidence
- **THEN** the original verified functional result is readable with its task-bound proof references.

#### Scenario: A normal task lacks semantic coverage
- **WHEN** its actual implementation surface, neighbor, goal or required proof is missing
- **THEN** the current-or-gap result exposes that exact deficiency and next owner without silently excluding it.

### Requirement: Architecture judgment preserves task scope and limitations
Architecture direction SHALL preserve related responsibility contexts, distinct remainders, original goals and real evidence boundaries. It SHALL expose where the current structure fails a declared goal or remains unknown without prescribing one universal optimum or ending on an implicit cost budget.

#### Scenario: A finite comparison has an uncovered surface
- **WHEN** a genuinely observed required surface lacks current model binding
- **THEN** the model coverage gap and actual code location are visible, and a Source behavior defect is not inferred solely from missing modeling.

#### Scenario: Only finite functional closure is proven
- **WHEN** a task reaches its declared evidence boundary
- **THEN** it can finish within that scope while unobserved software and unsupported whole-architecture claims remain explicit.

## outcome:r9:normal_task_current_or_gap_visible

The normal task producer must publish either an independently verified current functional result or the original diagnostic with its exact first gap, input reference and next owner. Publishing a diagnostic does not create a successful maturation receipt or close the task. Owned task evidence publication does not change the accepted model head or replace native authority. Its obligation is `obligation:r9:publish_current_task_or_original_gap`.
