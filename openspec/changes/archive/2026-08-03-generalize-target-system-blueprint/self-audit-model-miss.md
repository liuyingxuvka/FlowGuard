# Self-audit model-miss closure

The first generalized target-system self-blueprint audit reached the implementation-inventory layer but did not reach static blueprint readiness. It reported one avoidable dynamic `getattr` operation in `TargetSystemSnapshot.__post_init__` and treated standard `unittest.mock` terminal assertion methods plus an imported production assertion helper as unregistered assertion helpers.

The closure is intentionally narrow:

- replace the unnecessary dynamic field-normalization loop with explicit field normalization;
- classify known `unittest.mock` assertion methods as terminal native assertions rather than delegated helpers;
- discover imported production assertion helpers from the governed source tree and require an acyclic call path to a terminal assertion;
- keep exact source fingerprints, implementation-inventory admission, helper registration, and model-test-code alignment strict;
- do not widen into unrelated implementation or migration work, and do not weaken any readiness invariant.

The affected model consumers are the implementation blueprint, model-test-code alignment, and architecture-reduction views. Other model-purpose relations remain outside this correction.
