# Moving from FlowGuard 4.2 to 4.3

4.3 is a feature release. Source comments, intent rules, literal rows, sources, flows, ledger entries, owner-word records and `[structure]` decisions keep their meaning and bytes; nothing needs rewriting. The comments gain shorter spellings, two optional files hold the owner's current rules and the open questions, and every run ends with one English block whose first line counts what it found. FlowGuard no longer runs a function, or a test, a second time inside the test session: it records the real calls and compares them after the tests in a closed environment. This page lists what you will notice and what to do.

## Upgrade steps

1. Install 4.3 from this repository's tag; the similarly named PyPI project is different: `python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@v4.3.0"`.
2. Run `python -m flowguard init` again. It replaces the FlowGuard block of `AGENTS.md` with the seven rules below and, in a vitest project, rewrites `flowguard.vitest.mjs` so that only a vitest run loads FlowGuard (see [Builds and the dev server](#builds-and-the-dev-server)). The project's own text stays as it is.
3. Start the next task with `python -m flowguard new-task` and read its brief.
4. Reinstall the skill with `scripts/install_skill.py --target <skills folder>`. The installer replaces the whole folder; `references/rules.md` is now `reference.md`.

The block `init` writes:

```text
## FlowGuard rules for the project agent
1. Start each task with `python -m flowguard new-task`; read its brief (owner rules, open items) before you change code.
2. Run the project's tests. FlowGuard prints last; its first line counts each kind. `python -m flowguard show NAME` explains any name.
3. `red` means your change broke a recorded agreement: fix the code. Never add `except=`, remove a flowguard comment or edit `.flowguard/known.toml` to clear it without the owner's yes.
4. `known` and `before` were there before your task: do what the line says after `->`. Tell the owner only when it says `ask owner`.
5. `changed` means a function returns something else for the input shown: if you meant it, say so in your report; if not, fix it. `impact` and `not compared` are not failures.
6. When you find two places that must agree, mark each with `flowguard: same NAME` in the same change; when you find a problem only the owner can decide, add it to `.flowguard/known.toml` with `act = "ask"`.
7. Store the owner's own words once with `python -m flowguard req add - --id R<n>`, never your own text, and keep `.flowguard/rules.toml` current, each rule's source quoting those words.
```

## What changes in a run

| 4.2 | 4.3 |
| --- | --- |
| The closing block was titled `FlowGuard（相对任务开始 8d062cc）` and listed `红`, `变`, `线索` and `未验证` lines in Chinese. A run without a source change printed nothing. | Every run ends with one block after the runner's summary. Its first line counts each kind and FlowGuard's own seconds, `FlowGuard 4.3 (since 8d062cc): 1 red; 0.1 s`, also when there is nothing to say (`0 red`), when vitest observed nothing, and outside Git (`no baseline: nothing compared`). When a JSON, junit or TAP reporter writes to stdout, the block goes to stderr. Each further line starts with one of the nine kinds below. `python -m flowguard show --last` prints every line of the last run with its details. |
| A pair red ended with how to silence it: `…有意只写一边，把函数加进 owner 行的 alone=函数名(理由)`. | `red: together Booking.employee_id: booking.py:transfer writes Booking.employee_id without Booking.unit_id -> also write Booking.unit_id in transfer`. A red line never names `except=`; an `except=` this change adds is a `loosened` line. |
| Before/after comparison replayed each real call's function at representative values (its constants, their neighbours, a grid of classes) inside the test, under an audit hook, sqlite savepoints and deep copies of the arguments. `calibrated_by=` ran the named test again, up to a dozen times in one run; an event anchor ran its test again with the old code. | During the tests FlowGuard only records the JSON arguments and result of real calls: of each function marked `same` and each function this change edited, the first 20 distinct calls per process. After the tests it runs the function's old and new source in a closed environment (below) on those inputs: `changed: label (fees.py:15): (days=3) was 'on time', now 'late'; 1/2 inputs differ -> if you meant it, say so`. Nothing runs twice inside a test, so the tests' results, test doubles and coverage are what they are without FlowGuard. `calibrated_by=` reads the call the named test made in its ordinary run. Event anchors still record the real path. |
| Same-name copies were imported and run inside the test, so a frontend test could load the backend's modules. | The copies run in the closed environment, never imported, on the recorded inputs, the numbers the copies use and the ±1 neighbours of both (at most 64 inputs per name). Their versions at the task start run on the same inputs: copies that agreed on an input and differ now are `red` on that input; copies that already differed are `before`, or `known` when a `known.toml` entry names them. |
| A new agreement registered over code that already broke it was red. | The current registration is also applied to the task-start code: an old violation is `before`; only what this change broke is `red`. |
| A new automatic structure problem (a delete that leaves restricting children, a missing column, onDelete rules that differ, label tables, never-filled tables, look-alike copies, declarations that differ) was red. | Automatic structure checks are never red: a new problem is `impact`, an old one this change touches is `before`, and `check --all` lists them all. |
| A changed function whose new code could no longer be replayed (a new write, a result that is not simple data, a generator) was a lost observation and failed the run. | It is `not compared` with its reason and fails nothing. |
| Old-value, label-spelling and similar-implementation leads and copy discovery were `线索` lines. | They are deprecated and print neither a line nor a notice; `show --last` lists them under `deprecated leads (5.0)`. |
| The brief fitted ten lines. | The `new-task` brief has at most eight: the baseline, the first rules of `rules.toml`, the open `known.toml` entries (questions not yet asked first) and what the last task left, such as `1 red from the previous task are now before`. |
| vitest's failed case "FlowGuard execution side" carried the findings in its message. | It fails with one line, `FlowGuard: 1 red, see the FlowGuard block at the end`; vitest's JSON `failureMessages` hold just that line, and the block follows vitest's summary. |
| `status` and `where`, commands of FlowGuard 0.7x, were a usage error. | They print one line: `this is a FlowGuard 0.7x command; here run python -m flowguard new-task`. |

## The nine kinds

| Line | When | Fails the run |
| --- | --- | --- |
| `red` | This change broke a recorded agreement (`same`, `together`, `writers`, a declared value set), an intent rule, a quoted source, the ledger, or an entry of `rules.toml` or `known.toml` is invalid. Listed in full. | yes |
| `before` | Something this change touches was already broken at the task start and no `known.toml` entry names it: `before: same FEE disagreed at task start on days=5: fees.py:late_fee returns 4, fees.py:preview_fee returns 6 -> leave it unless your task is about it`. | no |
| `known` | This change edits the text of a `known.toml` entry's site (comments and spacing included; a line beside it does not count). The step follows its `act`: `known: known.fee-copies at fees.py:late_fee, fees.py:preview_fee -> ask owner (not asked yet)`. | no |
| `known fixed?` | An entry with `finding` whose check ran and no longer finds it: `known fixed?: known.fee-copies: copies of FEE now agree -> the owner has not decided: revert, or say why in your report`. Listed in full. | no |
| `changed` | A function this change edited, or one that imports a constant this change altered, returns something else for an input a test used. Plain `check` runs no ordinary tests, so `changed` comes from a test run or `check --all`. | no |
| `impact` | A function this change edited now writes another set of fields, or a new automatic structure problem: `impact: close_day now writes booking.unit_id; 2 other writers, 1 reader of booking -> check them for this change only (python -m flowguard show booking.unit_id)`. | no |
| `loosened` | This change added `except=`, removed or narrowed an agreement, changed or removed a `known.toml` entry (other than its `asked` date), added one whose `act` is not `ask`, or removed a rule: `loosened: except=transfer added to together Booking.employee_id -> name it in your report; needs the owner's yes`. Listed in full. | no |
| `not compared` | A comparison was due but could not run in the closed environment; one line sums them up. | no |
| `deprecated` | A feature or spelling of the project that goes in 5.0; printed on stderr once per process, after the block in pytest and vitest. | no |

Of `before`, `known`, `changed`, `impact` and `not compared` at most ten lines are shown: three changed, two known or before lines and one line counting the rest, two impact, one not compared; the rest is one line, `+N more: python -m flowguard show --last`. Paths are shortened to their file name unless another file of the repository has that name.

## Exit status

FlowGuard fails a run only for a `red` line. Most differences from 4.2 go from 1 to 0:

- an old violation under an agreement registered during the task is `before`;
- copies that already disagreed at the task start are `before` or `known`;
- automatic structure problems are `impact` or `before`;
- lost observations are `not compared`;
- failures that came from FlowGuard running a calibrated test, an event test or a function a second time (a test double reached by the replay, a test that changes shared state) cannot happen.

A few corrections go from 0 to 1, where 4.2 reported nothing although an agreement was broken:

- Pairs (`together`): a helper file that stops writing the partner makes its unchanged caller red; a partner written for another record (another `where`), only in one branch or in a conditional spread no longer holds the pair; a sibling route handler's write no longer holds a handler's pair, while what the handler calls does.
- A request stored during the task that supersedes or retires the words a rule cites (`req add --supersedes R3`) makes that rule's source red.
- A vitest run reports an intent file that does not load as red, as pytest does.
- A vitest run outside Git, before the first commit or with a recorded task start the repository lacks compares its same-name copies as pytest does, so copies that disagree are red there; 4.2 compared nothing in such a run.
- An invalid entry of `.flowguard/rules.toml` or `.flowguard/known.toml` is red, also in a run without a source change. Both files are new, so this only affects a project that adds them.

## Two new files

Both are optional and committed; FlowGuard 4.2.1 does not read them.

`.flowguard/rules.toml` holds the owner's current rules, each with one line of text and a source that quotes the stored words or an `authority_docs` sentence exactly:

```toml
[rule.late-fee]
text = "Each late day after the third costs 2."
source = 'R1 "Late days after the third cost 2 each."'
```

An intent rule may cite it as `source = 'rule.late-fee'`. `python -m flowguard show rules` lists the rules, each source's state and the open entries. A rule that newer owner words replace is deleted; its history stays in Git.

`.flowguard/known.toml` holds what is not settled, or what the owner deferred, and how to treat it:

```toml
[known.fee-copies]
sites   = ["fees.py:late_fee", "fees.py:preview_fee"]
why     = "The preview charges 3 per late day, the invoice 2"
act     = "ask"
ask     = "Which daily late fee is right, 2 or 3?"
finding = "same:FEE"
```

`act` is `leave` (deferred, or not this project's to fix now), `ask` (tell the owner, do not fix), `fix` (fix it when you change a site) or `ignore` (a false finding of an automatic structure check: counted, never a line). With `finding`, FlowGuard can say `known fixed?`; without it, the entry only reminds. Once the owner decides, store the answer with `req add`, write it into `rules.toml` and delete the entry.

An entry FlowGuard cannot read counts for nothing and is red. With `act = "later"` the block says:

```text
red: known.night-transfer: act is one of leave, ask, fix, ignore, not 'later' -> correct [known.night-transfer] in known.toml
```

Correct the entry from the question it records; nothing else needs rebuilding.

## Comment spellings

| 4.2 | 4.3 |
| --- | --- |
| `# flowguard: sensor NAME` | `# flowguard: same NAME` |
| `# flowguard: owner NAME` above a function | `# flowguard: same NAME ref` (also in TS/JS) |
| `# flowguard: owner A with=B,C` | `# flowguard: together A B,C` |
| `# flowguard: owner A with=B=value` | `# flowguard: together A B=value` |
| `alone=f(reason)` | `except=path:f(reason)`, which needs the owner's yes |
| `# flowguard: owner A writers=f,g` | `# flowguard: writers A f,g` |
| one owner line with `writers=` and `with=` | a `together` line and a `writers` line |

`on=update` and `on=create` keep their place after the partners. A bare writer name means a function of the comment's own file; another file's function is written `path:function`.

The 4.2 spellings are read with their old meaning. This 4.2 comment still gives the same red for a function that writes the field alone:

```python
# flowguard: owner Booking.employee_id with=Booking.unit_id
def reserve(booking, employee, unit):
    booking.employee_id = employee
    booking.unit_id = unit
```

and prints, once per process and after the block, `deprecated: owner with= goes in 5.0 -> write together FIELD PARTNERS` on stderr.

## Deprecated: goes in 5.0

A project that uses one of these gets one `deprecated` line per feature on stderr, after the block in pytest and vitest; the feature works as in 4.2 until 5.0.

| Feature | Instead |
| --- | --- |
| `anchor draft`, `model draft`, `try`, `watch`, `compare` | `new-task`, `check` or `show NAME` |
| `show --draft`, `show --gaps` | `show NAME` |
| `check --since REV` | `check --base REV` |
| `check --leads` | `show --last` |
| `req add --kind glossary`, `--kind adoption` | `req add FILE --id R<n>` |
| `precedes`, `guarded_by`, `transitions`, `checks`, `distinct`, `structure_rule`, `Transition`, `pytest.mark.rule` | none: do not use them |
| `[unverified]` in `.flowguard/ledger.toml` | none |
| `[structure]` decisions in `.flowguard/ledger.toml` | a `known.toml` entry with `act = "ignore"` or `"leave"` |
| old-value, label-spelling and similar-implementation leads, unregistered copy discovery | none; they are FlowGuard's own, so they print no notice, and `show --last` keeps them |

## The closed environment and what it does not compare

A Python function is compiled from its source, with the same-file functions it calls, into globals that hold only `abs`, `all`, `any`, `bool`, `dict`, `divmod`, `enumerate`, `filter`, `float`, `frozenset`, `int`, `isinstance`, `len`, `list`, `map`, `max`, `min`, `range`, `repr`, `reversed`, `round`, `set`, `sorted`, `str`, `sum`, `tuple`, `zip`, the built-in exceptions, `math`, `decimal.Decimal` and `datetime`'s `date`, `datetime` and `timedelta` (whose `now`, `today` and `utcnow` refuse). Module-level literal constants are read from the source, also arithmetic on them (`10 ** DECIMALS`) and a literal constant imported from another module of the project; nothing of the project is imported or executed. A TS/JS function, its types removed, runs in a fresh `vm` context that keeps only JavaScript's own built-ins (no `console`, `process`, `require`, `fetch` or timers); `Date` without arguments, `Date.now()` and `Math.random()` refuse, and only `null`, booleans, strings and finite numbers are compared as results.

Whatever cannot run there is `not compared` with its reason, for example:

```text
not compared: 2 items: price (prices.py:6) and fetch_price (uses unavailable binding RATE, or is async) -> not a failure
```

Not compared, in Python: decorated, async and generator functions, methods, defaults that are not literals, a name the environment lacks (a configuration read, a database client), arguments or results that are not JSON (`no comparable JSON result`); in TS/JS: enums, namespaces, decorators, JSX and parameter properties. A comparison is due only for a function this change edited (its body, a constant it reads or a same-file function it calls), a function in another file that imports a constant this change altered, and names with two or more copies, so a lone unchanged `same` function is never listed. Inputs come only from what the tests called: to have an input compared, let a test call the function with it. Plain `check` runs the affected intent rules but not the project's ordinary tests, so it records no calls and prints no `changed` line; `check --all` runs the ordinary tests too. A project in a subfolder of its Git repository is compared like one at the top.

## Builds and the dev server

4.2's vitest plugin also applied in `vite build`, `vite` and `vite preview`, which read the same config: the bundle and the served code could carry FlowGuard's recording calls, and a build on a machine without FlowGuard failed. In 4.3 only a vitest run loads FlowGuard. The plugin applies only when vitest has set `VITEST`, and the `flowguard.vitest.mjs` that `init` writes returns no plugin outside vitest and starts no Python. With FlowGuard 4.3 installed an older `flowguard.vitest.mjs` builds cleanly too, but it still starts Python for its preparation, and on a machine without FlowGuard it stops `vite build` with `no Python that can import flowguard was found`; run `init` again to rewrite it.

## Known limits

- Only inputs the tests used are compared (copies add their numbers and ±1). A function that takes objects, reads configuration or a database, or calls helpers in another file stays `not compared`; comparing such helpers is left to 4.4.
- `impact` counts the readers of a model from the map's queries; the readers of one field come in 4.4.
- vitest keeps its own cache in FlowGuard's adapter folder (`flowguard/adapters/vitest/node_modules/.vite`), as in 4.2.1.
