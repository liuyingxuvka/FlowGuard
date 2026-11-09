# KWP technology-name copies (copy discovery on the code's own literals)

The two `normalize_technology_name` implementations of the owner's KWP project (HEAD `64479aa`), copied with
`sed` from a working-tree copy (no git command in the KWP repository), each with the alias table it reads.
The `.txt` suffix keeps them out of FlowGuard's own map; `tests/intent_engine/test_owner_copies.py` writes
them into an isolated project as `.py` files.

| Fixture | Source lines |
|---|---|
| `Step1/src/kwp_step1/utils.py.txt` | `_TECH_ALIASES` and `normalize_technology_name`, lines 166-181 (after `from typing import Any`) |
| `Step3/src/kwp_step3/technology.py.txt` | `_ALIAS`, lines 17-37, and `normalize_technology_name`, lines 67-70 |

The bodies are the same shape; the tables differ (Step1 also maps `oil`, `heizÃ¶l`, `Ã¶l`, `waermenetze`),
so the Step1 copy is a forked copy only when the alias keys are among the compared values.
