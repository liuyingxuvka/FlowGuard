# KWP rounding copies (owner, copy discovery, changed alone)

The seven Python implementations of MATLAB `round` listed in table 1-C of the round-20 evidence
(`真实项目问题实例.md`), copied from a working-tree copy of the owner's KWP project (HEAD `64479aa`;
read with `cp`/`sed` only, no git command in the KWP repository). The `.txt` suffix keeps them out of
FlowGuard's own map; `tests/intent_engine/test_owner_copies.py` writes them into an isolated project
as `.py` files at the same relative paths.

| Fixture | Source lines | Copy |
|---|---|---|
| `Step1/src/kwp_step1/matlab_fallbacks.py.txt` | 1-28 (`matlab_round` at line 15) | the owner in fixed example 10 |
| `Step3/src/kwp_step3/technology.py.txt` | 1-64 (`matlab_round` at line 53) | same as the owner |
| `Step10/step10_baublock_progress_maps.py.txt` | 2174-2180 (`_matlab_round_scalar`) | same as the owner |
| `Step2/src/kwp_step2/try_data.py.txt` | 1-21 (`_matlab_round` at line 15) | same as the owner |
| `Step2/src/kwp_step2/simulation_preparation.py.txt` | 1-35 (`_matlab_round_nonnegative` at line 25) | `int(value + 0.5)`: −2.5 → −2 |
| `Step6a/kwp_step6a/config.py.txt` | 321-324 (`_matlab_positive_round`) | `floor(x + 0.5)`: −2.5 → −2 |
| `Step2/step2_demand_library.py.txt` | 6192-6195 (`_matlab_round_positive`, old reference file) | non-finite → 0 |

Line ranges starting at line 1 keep the original line numbers. In them, imports the copied function
does not use and the fixture cannot provide (`from .utils import ...`, `import numpy as np`, two
relative imports in `simulation_preparation.py`) are replaced by one comment line each. The other
three files hold only the function, after a one-line provenance docstring and `import math`; their
original lines are in the docstring. Every copied function body is verbatim. `__init__.py.txt` files
are empty package markers.

Fixed example 11 needs the code before commit `1da8721` ("fix(parity): align MATLAB rounding across
step1 step3 step10"). The evidence names that commit but not its diff, and the KWP repository may not
be queried, so the test reconstructs the three pre-fix bodies with the unchanged copies' form
`int(floor(float(value) + 0.5))`; that reconstruction is not copied source.
