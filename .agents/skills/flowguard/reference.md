# FlowGuard reference

Start with `new-task`, run ordinary tests and inspect a finding with `show "what it decides"`. `show Model.field`, `show CONSTANT`, `show EnumName` or `show LABELS_TABLE`, after the known.toml entries, rules and agreements that concern it, says how the schemas, SQL files and source declare it, before every other line (a zod line matches an object key by its name, names its schema object and is given only to a key whose own chain is a `z.number(` or `z.coerce.number(` schema, also inside `z.optional(`, `z.nullable(`, `z.nullish(`, `z.preprocess(` or a pipe; every check of its constant's chain and its own counts, the stricter of two comparable bounds of a side and both when one is a name; a refine on it, or on its object naming the key, is named, not read; a field the known model lacks gets a `not on the map` line instead; a const line comes from a JS/TS module constant only; an enum name lists each Prisma schema's members with that schema's state; a label table lists its keys and labels and its family's `structure:` finding; what only test files declare is left out: a file in a `tests`, `test` or `__tests__` folder, or named `test_*` in any language, `*_test.py`, `*.test.*` or `*.spec.*`; a CHECK that code builds as a string is not read); trust that over a document's table. `show MODEL` or `show table` gives a line per schema with its `@@map` table and field count and the count of writes and reads, `show field` the Prisma models that declare it, and a function's or `object.method`'s name its signature, the fields it writes and its callers through resolved calls; a misspelt field names the model's nearest field, a name the map does not know says so, and what only shares a word with the query follows a line that says so, after `--full` when the map knows the name. The view of a together agreement marks each write that misses a partner (`missing PARTNER: ...`) and prints its fix only then. Register necessary agreements as the code grows. Do not model the development task.

## Executable two-copy example

In this throwaway example, put this in `policy.txt`:

```text
At most three days.
```

```toml
[tool.flowguard]
authority_docs = ["policy.txt"]
```

In `orders.py`:

```python
# flowguard: same ACCEPT ref(days: day) -> allowed: bool
def accept(days: int) -> bool:
    return days <= 3

# flowguard: same ACCEPT(days: day) -> allowed: bool
def preview_accept(days: int) -> bool:
    return days <= 3
```

In `tests/intent/window.py`:

```python
from flowguard.intent import rule, row

@rule("WINDOW", decides="acceptance window", fields={"days": int},
      source='doc policy.txt "At most three days."', anchor="ACCEPT")
def WINDOW(days):
    return days <= 3

WINDOW.rows(row(days=4, expect=False, why="the fourth day was incorrectly accepted"))
```

Run `python -m flowguard init`, then `python -m pytest`. Change only the preview to allow four days: with a test that calls both functions, its real answer disagrees with the independent rule and the other registered copy, and the run ends with:

```text
FlowGuard 4.3 (since 6765008): 2 red; 0.4 s
red: rule WINDOW: days=4: rule False, code True at orders.py:preview_accept (1 of 6 cells disagree) (+1 more) -> change the code so orders.py:preview_accept follows rule WINDOW
red: same ACCEPT: on days=4: the reference orders.py:accept returns False, orders.py:preview_accept returns True -> make orders.py:preview_accept agree with the reference
```

A newly written document is provisional evidence, not independent confirmation. A rule runs only Python functions: bound to a TS/JS function it is red, and TS/JS copies are compared by `same` alone. The shortest comment is `# flowguard: same ACCEPT`; input and context roles are then read from the parameters.

The rule's `fields` dictionary is the supported API's explicit input schema. It is separate from the `fields name=expression` annotation described below. Keep the predicate independent of the implementation and preserve meaningful regression rows.

## Agreement comments

Use `#` in Python and `//` in TS/JS. These comments normalize to the existing registration; they do not add runtime dependencies to application code.

| Comment | Meaning |
| --- | --- |
| `flowguard: same NAME` | A copy of the named judgment. |
| `flowguard: same NAME ref` | The chosen reference copy; only one per name. |
| `flowguard: together A B,C` | An operation writing A must also write B and C. |
| `flowguard: together A B on=update` | Limit the agreement to update; create is the other supported value. |
| `flowguard: together A B=value` | The partner must be written with that value. |
| `flowguard: together A B except=path:function(reason)` | A documented exception requiring the owner's agreement. |
| `flowguard: writers A f,g` | Only these functions may write A. |

Bare writer names identify functions in the comment's file. A function in another file uses its repository-relative position, such as `src/store.py:reserve` or `backend/src/store.ts:service.reserve`. The source map resolves that file's actual identity. Do not change an agreement to silence a finding without the owner's agreement.

A Python reference can retain its parameter declaration, as in `same ACCEPT ref(days: day)`. TS/JS uses `same ACCEPT ref` above the actual function. Missing targets, mismatched signatures or units, and multiple references remain errors. Different policies should use different agreement names; do not force them to agree.

Python copies with different parameter names make the correspondence explicit: `same ACCEPT(days=overdue_days)`. Nothing is matched by position or type. A return projection is written without a colon, such as `-> result[0]` or `-> result.ok`; `-> allowed: bool` remains an output declaration.

FlowGuard 5.0 removed the 4.2 spellings (`sensor`, `owner`): each is red at its line, and its step is the 4.3 comment to write. Written as that step says, it loosens nothing; deleting the line or writing a looser agreement than its step is `loosened`.

## Intent rules and real context

Rules have an ID, decision key, typed fields, source and independent predicate. Literal rows provide inputs, `expect` and `why`; `retired` explains an inapplicable old case. Returning `None` means no opinion. `total=True` makes an uncovered decision an error. `Refused(ValueError, contains="...")` expects a real program exception; a tool error is not that exception.

Boolean and closed-enum domains can be enumerated. Supported numeric, date and duration domains use the current partition reader. Unknown domains remain unverified; a supported result type does not make that type an enumerable input domain.

A Python `same` comment can keep `calibrated_by=tests/test_store.py::test_available`, including a parameter ID, to name the ordinary test that supplies its real context: the call that test made in its ordinary run is the context, and the test never runs a second time. An explicit `fields name=expression` annotation can expose rule inputs missing from the function's parameters. Neither annotation supplies an invented result or proves contexts the test did not reach. Keep real assertions, fixtures and cleanup in ordinary tests.

For an existing scenario binding, the test supplies actual case inputs and production calls; readings must come from the declared source and invocation. Missing or ambiguous evidence stays unverified. A passing setup test does not establish every possible filesystem, database or concurrent state.

## Owner rules and open items

`.flowguard/rules.toml` lists the owner's current rules. Each entry has two keys: one line of `text` and a `source` that quotes stored words or an `authority_docs` sentence exactly.

```toml
[rule.late-fee]
text = "Each late day after the third costs 2."
source = 'R1 "Late days after the third cost 2 each."'
```

An intent rule can then cite `source = 'rule.late-fee'`. When newer owner words replace a rule, delete its entry; Git keeps the history. Two rules that conflict, or a question for the owner, belong in `.flowguard/known.toml`:

```toml
[known.fee-copies]
sites   = ["fees.py:late_fee", "fees.py:preview_fee"]
why     = "The preview charges 3 per late day, the invoice 2"
act     = "ask"
ask     = "Which daily late fee is right, 2 or 3?"
finding = "same:FEE"
```

`sites` are repository-relative `path:symbol` places (a function, `object.method`, a constant or `Model.field`). `act` is `leave` (left as it is on purpose), `ask` (a question only the owner can answer, not fixed in passing; add `asked = "YYYY-MM-DD"` once asked), `fix` (a plain error: fix it when you change a site and say so) or `ignore` (a false finding of an automatic structure check, only counted). `sites`, `why` and `act` are required; an optional `fix` key holds the intended correction, which only `show` prints, and `source` quotes where the question comes from, as a rule's does. `finding` names a finding FlowGuard can judge, such as `same:FEE`; with it the run can say `known fixed?`. An invalid entry is red and counts for nothing. A new `act = "ask"` entry is quiet; changing or removing an entry, or adding one with another `act`, is a `loosened` line. Once the owner decides, store the answer with `req add`, write it into `rules.toml` and delete the entry. `python -m flowguard known add FINDING --act leave --why TEXT` (any `act`; `--ask`, `--id`, `--site path:symbol`) appends an entry, its sites the places of the last run's lines of that finding; `show --last` names each line's finding. `python -m flowguard show rules` lists both files with each source's state. `show NAME`, `show PATH` and `show RULE_ID` (with its anchors) begin with the entries whose sites or finding name it (a site's symbol, the model or object holding it or a Prisma field's `table.column`, in any letter case; a site's last dotted part, and then the line names that site; for a path, a site in that file or folder or a `source` quoting a document there; also an entry whose why or ask holds, as the code spells it, an exact `Model.field`, a constant a non-test file declares or the path), in the brief's words with `(python -m flowguard show known.<id>)`, then the intent rules anchored there, the `rules.toml` rules they cite, the flowguard comment agreements that name the function or field (`Model.*` its table's columns too), sit right above the function or are written in that file (one found through a last dotted part names that function), and the last run's lines at that function or file (`before (last run): ...`, five without `--full`). A site copied from `show known.<id>` (`path:symbol`) prints that symbol's facts; a bare id (`show percent-scale`) prints the entry; words (`show "percent scale"`) also list the entries whose why or ask shares one. A Markdown file's view is headed `document`; a file the map does not read, or a folder without one, says so in one line.

## Sources and fallback reasons

The owner is the person who sets the requirement. `source='owner R1: ...'` cites that person's archived words; `req add` stores their exact bytes. Never archive this guide or an AI plan as the owner's words. Document sources require quoted text and an `authority_docs` entry. An archive proves bytes, not an interpretation; provisional or assumed sources do not create owner authority.

`.flowguard/ledger.toml` lists handlers that can end without raising, with their counts, reasons and supporting written rules. `python -m flowguard ledger init` records existing handlers as legacy; `python -m flowguard ledger check` checks the record. Legacy entries may only shrink. The finding explains a form that cannot be listed or a source sentence that no longer matches. Keep errors visible rather than adding an unexplained fallback.

## Existing frozen capabilities

Existing finite flows and their node/read/relation bindings remain supported; their state transitions (`Transition`, `flow(..., transitions=)`) were removed in 5.0. Their path and source identities matter: an attempted call is not a completed effect, an unobserved edge is not a successful path, and separate invocations cannot be joined into one witness. These capabilities are frozen; ordinary setup does not require a new flow model. Existing deep checks are also frozen.

The base installation reads Python. The `languages` extra adds TS/JS, Prisma, SQL and frozen C/C++/C# readers. Vitest with ESM has an execution adapter; Jest has static checks. Unsupported readers and observations remain explicit. Keep each project's ordinary tests as the primary execution path.

## Inspecting a result

Read the FlowGuard block after the tests. Its first line counts each kind and FlowGuard's own time, and names what the run compared with. Each further line is `kind: what -> step`:

| Kind | Meaning |
| --- | --- |
| `red` | This change broke an agreement, an intent rule, a quoted source, the ledger or an entry of the two files. The only kind that fails the run. |
| `before` | Something this change touches was already broken at the task start. |
| `known` | This change edits the text of a `known.toml` entry's site, comments and spacing included; the line names the sites it touches (`(1 of 12 sites)`) and an `ask` entry's question. |
| `known fixed?` | A `known.toml` finding is gone. |
| `changed` | A function this change edited, or one importing a constant it altered, returns something else for an input a test used; plain `check` runs no ordinary tests, so this comes from a test run or `check --all`. |
| `impact` | A changed function writes another set of fields, or an automatic structure check found something new. |
| `loosened` | An `except=`, a removed or narrowed agreement, a changed or removed `known.toml` entry or a removed rule. |
| `not compared` | A comparison was due but could not run in the closed environment; unverified, not success. |

The step after `->` says what is known and who decides; you choose when to raise an open question with the owner. `python -m flowguard show --last` prints every line of the last run with its details. Use `python -m flowguard show "what it decides"` for registered functions, fields, copies and rules; use `python -m flowguard check --static --all` for a deliberate structure review.

The CLI prepares the project's import context. Direct Model/Engine instances remain fixed snapshots.
