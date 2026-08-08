## REMOVED Requirements

### Requirement: Summary reports produce maintenance scan inputs
**Reason**: Current owners consume their typed findings directly; an extra scan-plan conversion is redundant.
**Migration**: Route current findings to DevelopmentProcessFlow, ModelMaturation, ArchitectureReduction, StructureMesh, or the owning specialist.

### Requirement: Maintenance actions expose AI next-route metadata
**Reason**: Canonical findings and maintenance obligations already name their owning next route.
**Migration**: Preserve next-owner identity on the typed finding or maintenance obligation.

### Requirement: Maintenance scan remains a thin router
**Reason**: A router used only to repeat another owner's routing decision adds no independent value.
**Migration**: Invoke the exact owner selected by the canonical DNA/affected topology.

### Requirement: Maintenance scan routes model-angle gaps
**Reason**: The model-angle route is retired and concrete gaps go directly to ModelMaturation.
**Migration**: Use typed maturation signals.

### Requirement: Maintenance scan reopens touched obligations
**Reason**: Maintenance-obligation currentness belongs to the obligation and DevelopmentProcessFlow owners.
**Migration**: Reopen the exact typed obligation when its governed inputs change.

### Requirement: Maintenance scan does not validate obligations
**Reason**: Removing the non-validating intermediary leaves validation with the native owner.
**Migration**: Consume owner-route evidence directly.

### Requirement: Maintenance scan routes topology hazard gaps
**Reason**: Topology gaps are owned by canonical topology, ModelMesh, ContractExhaustion, BCL, or ArchitectureReduction.
**Migration**: Route each typed topology relation or hazard to its exact current owner.

### Requirement: Maintenance scan routes state closure gaps to model maturation
**Reason**: State closure can feed ModelMaturation directly.
**Migration**: Emit the exact state-closure gap as a maturation contribution.

### Requirement: Maintenance scan routes change signals to existing FlowGuard maintenance routes
**Reason**: DevelopmentProcessFlow and affected-blueprint propagation already perform this responsibility.
**Migration**: Use the current affected owner set and staged process plan.

### Requirement: Maintenance scan covers structure and reduction debt without replacing owning routes
**Reason**: Direct StructureMesh and ArchitectureReduction handoffs are clearer and shorter.
**Migration**: Create typed obligations owned by those routes.

### Requirement: Maintenance scan preserves scoped claims and non-goals
**Reason**: Scope and non-goals belong to the source finding and final evidence ledger.
**Migration**: Preserve them on the typed obligation and owner receipt.

### Requirement: Maintenance scan is available through API and template surfaces
**Reason**: The independent public route and template increase choice without adding authority.
**Migration**: Use the current owner route's API or template.

### Requirement: Business path hazards route through existing maintenance owners
**Reason**: Canonical BCL and affected topology route these hazards directly.
**Migration**: Resolve the business-path commitment and invoke its current owner.

### Requirement: Business path scan output preserves skipped evidence
**Reason**: Skipped/not-run evidence is already preserved by DevelopmentProcessFlow and validation receipts.
**Migration**: Record skipped evidence on the owning process or validation result.
