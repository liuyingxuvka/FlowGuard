# Round-20 fixed samples 1, 2, 3, 4, 5, 7, 9 and 19

A copy of the round-19 acceptance project `p4base` (the coordinator's demo and prototype 2 in one
project, every anchor in the shortest 4.0 form, one rule quoting the owner's words R1), with two
changes taken from prototype 2:

- `shop/policy.py`: `STANDING` reads `GRACE_DAYS` through the helper `within_grace` (sample 3);
- `tests/test_store.py`: `test_hire_count` can write the final row count of `hires` to the file named
  by `HIRES_ROWS`, so a run with and a run without the plugin can be compared (sample 2).

Files end in `.txt` so that neither pytest nor FlowGuard's own map reads them as this repository's
code; `tests/intent_engine/test_round20_samples.py` copies them without the suffix, commits the
baseline, stores `R1_owner.txt` with `req add --id R1` and adds the unparsable `_tmp_x.py` (sample 19).
Each test applies one sample's edit, the edits of `tools/edit_s*.py` in the acceptance:

| sample | edit |
|---|---|
| 1 | `shop/store.py`: `stock > reserved` → `stock >= reserved` |
| 2 | `shop/store.py`: `return count + stock - reserved` → `return max(0, count + stock - reserved)` |
| 3 | `shop/policy.py`: `GRACE_DAYS = 3` → `GRACE_DAYS = 7` |
| 4 | `shop/fees.py`: `fee // 2` → `fee * 2 // 3` for members |
| 5 | `shop/publish.py`: `needs_save` also returns False for ids starting with `a` |
| 7 | `shop/deposit.py`: members are exempted from the approval, against R1 |
| 9 | `shop/members.py`: the grace for members with a debt 3 → 7 days |
