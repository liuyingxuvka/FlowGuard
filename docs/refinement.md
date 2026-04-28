# Refinement

Production state does not need to be identical to abstract model state.
Conformance and refinement use projection:

```text
pi(RealState) = AbstractState
```

The projected real behavior must still be allowed by the abstract model. A
projection must not hide raw production bugs. For example, a projection that
deduplicates duplicate records before comparison is not a valid safety check
unless the raw duplicate is also reported.

`check_refinement_projection()` provides a small helper for simple one-step
checks. It compares an expected abstract state with a projected real state and
reports `refinement_projection_mismatch` if they differ.

This is not a full simulation proof. It is a practical bridge between:

```text
abstract trace -> real implementation replay -> projected observation
```

and the model-first rule that production behavior should not silently diverge
from the executable abstract model.
