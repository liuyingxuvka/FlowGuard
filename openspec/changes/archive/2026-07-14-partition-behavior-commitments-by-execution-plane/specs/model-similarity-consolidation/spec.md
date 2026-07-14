## ADDED Requirements

### Requirement: Model signatures include behavior plane
Comparable model signatures SHALL declare the behavior plane owned by the model or an explicit multi-plane scoped reason when the signature is an orchestration parent rather than a leaf owner.

#### Scenario: Same-plane models remain comparable
- **WHEN** two signatures own the same behavior plane and share workflow/state/side-effect responsibility
- **THEN** existing similarity relation rules MAY classify same-workflow, variant, duplicate, adapter, or shared-kernel relations

### Requirement: Cross-plane language is false-friend evidence
Shared names, task terms, or public words across different behavior planes SHALL NOT by themselves support model merge, shared-kernel, duplicate-boundary, or same-workflow recommendations.

#### Scenario: Product download and agent download share label
- **WHEN** two signatures share the word `download` but one is `product_runtime` and the other is `agent_operation`
- **THEN** the pair SHALL be classified as false friend, unrelated, or manual review unless a typed BCL relation provides explicit context

#### Scenario: Typed relation preserves separate owners
- **WHEN** an agent-operation model invokes a product-runtime commitment
- **THEN** similarity output MAY preserve the relation as context
- **AND** SHALL keep the two owner boundaries separate

### Requirement: Similarity handoff preserves plane evidence
Similarity relation, maintenance-group, and downstream handoff output SHALL expose the compared planes and any typed commitment relation that influenced classification.

#### Scenario: Cross-plane merge is rejected
- **WHEN** a proposed consolidation crosses planes without an allowed ownership rationale
- **THEN** the report SHALL include a plane-conflict finding and SHALL NOT recommend consolidation
