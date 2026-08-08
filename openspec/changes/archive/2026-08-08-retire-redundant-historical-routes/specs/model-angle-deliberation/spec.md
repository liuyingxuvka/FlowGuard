## REMOVED Requirements

### Requirement: Agents record open-ended model angle deliberation
**Reason**: Current TaskCoverageDemand and ModelMaturation derive concrete missing state, branch, child, same-class, and evidence obligations from the canonical DNA without a separate open-ended route.
**Migration**: Record each concrete gap on the affected blueprint owner and feed it to ModelMaturation.

### Requirement: Candidate model angles end in a disposition
**Reason**: The independent angle inventory duplicates current coverage and maturation dispositions.
**Migration**: Use typed coverage-demand and maturation findings with exact owner and evidence identities.

### Requirement: Model angle deliberation is not validation evidence
**Reason**: Removing the non-evidentiary route eliminates a redundant report rather than weakening validation.
**Migration**: Validation continues to use current model, code, test, known-bad, topology, and evidence-owner results.

### Requirement: Claimed angle resolution binds current owner evidence
**Reason**: Current maturation and authority owners already enforce this binding directly.
**Migration**: Bind the resolved gap to the affected model owner and current maturation evidence.

### Requirement: Model angles contribute gaps to maturation
**Reason**: Maturation now receives the typed gap directly and no longer needs a model-angle intermediary.
**Migration**: Emit missing-state, missing-branch, missing-child, same-class-missing, or missing-evidence signals directly to ModelMaturation.
