# Round-20 fixed samples 13 and 14 (rule fields read on each call)

A small library project for phase 4. Files end in `.txt` so that neither pytest nor FlowGuard's own
map reads them as this repository's code; `tests/intent_engine/test_round20_fields.py` copies them
without the suffix, commits the baseline and stores `R1_owner.txt` with `req add --id R1`.

| file | what it is for |
|---|---|
| `shop/hires.py` | sample 13: `may_borrow(db, hire, today)` decides on days overdue and membership, neither a parameter; the anchor reads them with `fields days=(today - hire.due).days member=is_member(db, hire.customer)` from the sqlite3 connection and the hire record |
| `tests/intent/borrow.py` | rule `BORROW` quoting R1, bound to `MAY_BORROW`, without a scenario test |
| `shop/policy.py`, `tests/intent/grace.py` | sample 14: `GRACE_DAYS = 14`, read by `STANDING` through a helper; rule `GRACE` repeats 14 in its predicate and rows |
| `shop/notices.py`, `tests/test_notices.py`, `tests/intent/notices.py` | the third route kept: a function that writes a file, its rule through the event anchor `NOTICE_CASE calibrated_by=...` and a flow relation |

The edits each test applies:

| sample | edit | expected |
|---|---|---|
| 13 | `shop/hires.py`: `<= 10:` → `<= 9:` | red `BORROW: days=10 member=F -> rule T, code False` with the owner sentence |
| 13 | the anchor's `hire.customer` → `hire.customer_id` | grey, the reason names the field `member` and its error |
| 14 | `shop/policy.py`: `GRACE_DAYS = 14` → `21` | leads "rule GRACE still holds the old value 14" and "STANDING's copy changed, rule GRACE did not" |
| route 3 | `shop/notices.py`: `days <= 3` → `days <= 4` | the scenario rows of `NOTICE` are red |
