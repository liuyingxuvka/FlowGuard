# Moving from FlowGuard 4.3 to 5.0

5.0 is a major release. FlowGuard 4.3 announced a set of commands, options, intent API names, comment spellings and ledger sections for removal in 5.0. They are removed now, and each use is refused with its replacement: a removed command or option exits 2 with one line on stderr, and a removed intent name, comment spelling or ledger section is a red line whose step says what to write instead. Nothing of them is read with its old meaning. The work prepared as 4.4, documents that follow the code, was never released; it ships here. Everything 4.3 did not announce keeps its meaning and bytes: 4.3 comments, intent rules, literal rows, sources, flows (nodes, edges, relations), the ledger's handler entries, `rules.toml`, `known.toml` and the owner-word archive, its glossary and adoption records included. One meaning changed: a `known.toml` entry with `act = "ignore"` now also takes its finding out of the brief's count of open structure problems, which 4.3 did not (see [What you may notice](#what-you-may-notice)).

FlowGuard is the agent's tool. Its lines say what is known and who decides; none of them tells the agent to ask or tell the owner, and the agent chooses when to raise a question. An old problem stays out of an ordinary run until a change touches its place, and stays visible in the brief's counts, in `python -m flowguard show NAME` and in `python -m flowguard check --all`.

## Upgrade steps

1. Install 5.0 from this repository's tag; the PyPI project named `flowguard` is a different project: `python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@v5.0.0"`. Add `[languages]` after `flowguard` if the project reads TS/JS, Prisma or SQL, as before.
2. Run `python -m flowguard init`. It rewrites the FlowGuard block of `AGENTS.md`, and of `CLAUDE.md` when it holds one, in the file's own encoding (UTF-8, or UTF-16 or UTF-8 with a BOM). In an npm project it also rewrites `flowguard.static.test.mjs` (or `.js`) and `flowguard.vitest.mjs`, so the project's tests run as usual on a machine without FlowGuard. Until then the brief says `AGENTS.md holds a FlowGuard rules block that differs from the one FlowGuard 5.0 writes: python -m flowguard init rewrites it`.
3. Start the task with `python -m flowguard new-task`, run the project's tests and `python -m flowguard check --static --all`, and follow each red line: its step after `->` is what to write instead. The sections below list every case.
4. Reinstall the skill with `scripts/install_skill.py --target <skills folder>`.

The block `init` writes:

```text
## FlowGuard rules for the project agent
1. Start each task with `python -m flowguard new-task`; read its brief (owner rules, open items) before you change code.
2. Run the project's tests. FlowGuard prints last; its first line counts each kind. `python -m flowguard show NAME` explains any name.
3. `red` means your change broke a recorded agreement: fix the code. An `except=`, a removed flowguard comment or a `.flowguard/known.toml` edit that clears it loosens the agreement, which is the owner's decision.
4. `known` and `before` were there before your task; after `->` each line says what is known and who decides. You choose when to raise an open question with the owner.
5. `changed` means a function returns something else for the input shown: if you meant it, say so in your report; if not, fix it. `impact` and `not compared` are not failures.
6. When you find two places that must agree, mark each with `flowguard: same NAME` in the same change; record a problem only the owner can decide in `.flowguard/known.toml` with `act = "ask"` (`known add` writes one).
7. Store the owner's own words once with `python -m flowguard req add - --id R<n>`, never your own text, and keep `.flowguard/rules.toml` current, each rule's source quoting those words.
```

Rules 3, 4 and 6 changed. 4.3's rule 3 ended `Never add except= ... without the owner's yes`, rule 4 said `do what the line says after ->. Tell the owner only when it says ask owner`, and rule 6 said `add it to .flowguard/known.toml`.

### A 4.3 project, upgraded

This project ran green on 4.3, which printed its `deprecated:` notices on stderr after the block. It has two copies of `FEE` in `fees.py`, an `owner ... with=` comment in `booking.py`, two `Status` declarations that differ (`status.py` and `report.py`) and a `[structure]` decision in its ledger that says why they differ, citing the stored owner words R1. Its first test run with 5.0:

```text
FlowGuard 5.0 (since 5c633bf): 4 red; 0.1 s
red: comment booking.py:1: owner with= was removed in 5.0 -> write # flowguard: together Booking.employee_id Booking.unit_id
red: comment fees.py:1: owner NAME above a function was removed in 5.0 -> write # flowguard: same FEE ref
red: comment fees.py:6: sensor was removed in 5.0 -> write # flowguard: same FEE
red: ledger.toml: [structure] was removed in 5.0 -> delete the section and record each decision in .flowguard/known.toml: python -m flowguard known add NAME --act leave|ignore --why TEXT
```

Write the three comments as the steps say and delete the `[structure]` section, its header and every `[structure."..."]` table, and keep the rest of `.flowguard/ledger.toml` (a file left empty is fine; a `[structure]` header left alone is still red, and deleting the file is red). The decision's problem is then an old one again, which `check --static --all` lists:

```text
FlowGuard 5.0 (since 5c633bf): 0 red, 1 before; 0.1 s
before: declarations Status at report.py:3 was broken at task start -> leave it unless your task is about it
```

Record the decision in `known.toml`, from its words and its source:

```bash
python -m flowguard known add declarations:Status --act leave --why "The report shows late bookings; a booking itself is never stored as late (R1)" --site report.py:Status
```

```text
known.declarations-status added to .flowguard/known.toml: act leave, sites report.py:Status, finding declarations:Status
the next run lists it as loosened, as every new entry whose act is not ask
```

The next test run says `FlowGuard 5.0 (since 5c633bf): 0 red, 1 loosened; 0.2 s` with `loosened: known.declarations-status added with act = "leave" -> name it in your report; loosening an agreement is the owner's decision`: the report names the entry, whose decision R1 already holds. The brief then lists `known.declarations-status: left as it is: The report shows late bookings; a booking itself is never stored as late (R1)`.

## Commands and options

Each use exits 2 before any project file is read or written, with one line on stderr; nothing of the command runs, is ignored or is read as another command.

| 4.3 accepted | 5.0 prints on stderr, exit 2 | Instead |
| --- | --- | --- |
| `python -m flowguard anchor draft LIMIT` | `flowguard: anchor draft was removed in 5.0 -> python -m flowguard new-task, check or show NAME` | `python -m flowguard show LIMIT` |
| `python -m flowguard model draft PUBLISH` | `flowguard: model draft was removed in 5.0 -> python -m flowguard new-task, check or show NAME` | `python -m flowguard show PUBLISH` |
| `python -m flowguard try LIMIT days=4` | `flowguard: try was removed in 5.0 -> python -m flowguard new-task, check or show NAME` | a test that calls the function with `days=4`; its run compares it |
| `python -m flowguard watch -- python app.py` | `flowguard: watch was removed in 5.0 -> python -m flowguard new-task, check or show NAME` | the project's tests |
| `python -m flowguard compare fees:late_fee fees:preview_fee` | `flowguard: compare was removed in 5.0 -> python -m flowguard new-task, check or show NAME` | the project's tests: they compare the copies of one `same` name input by input |
| `python -m flowguard show --draft LIMIT` | `flowguard: show --draft was removed in 5.0 -> python -m flowguard show NAME` | `python -m flowguard show LIMIT` |
| `python -m flowguard show --gaps LIMIT` | `flowguard: show --gaps was removed in 5.0 -> python -m flowguard show NAME` | `python -m flowguard show RULE` of a rule that decides `LIMIT`: its `undecided` lines list the classes no rule decides |
| `python -m flowguard check --since HEAD~1` | `flowguard: check --since was removed in 5.0 -> python -m flowguard check --base REV` | `python -m flowguard check --base HEAD~1` |
| `python -m flowguard check --leads` | `flowguard: check --leads was removed in 5.0 -> python -m flowguard show --last` | `python -m flowguard show --last` |
| `python -m flowguard req add owner.txt --kind glossary` | `flowguard: req add --kind glossary was removed in 5.0 -> python -m flowguard req add FILE --id R<n>` | `python -m flowguard req add owner.txt --id R2` |
| `python -m flowguard req add owner.txt --kind adoption` | `flowguard: req add --kind adoption was removed in 5.0 -> python -m flowguard req add FILE --id R<n>` | `python -m flowguard req add owner.txt --id R2` |

`req add --kind request`, 4.3's default, is still accepted and changes nothing. Glossary and adoption records already in `.flowguard/requests/` keep loading, listing and showing. `status` and `where` of FlowGuard 0.7x still print the command to run instead.

## Intent API names

An intent file that imports, reads or calls one of these names is refused before it runs. Its `load` line is red at that file and line, in pytest, `check` and the vitest report: `red: load FILE:LINE: NAME was removed in 5.0 -> STEP; until then none of its file is checked`. A name the file reaches only when it runs (`api.distinct(...)`) gives the same line, and reading it from `flowguard.intent` raises `IntentError` with the same text. The block shortens a long line; `python -m flowguard show --last` prints it whole.

| 4.3 accepted | The step of its 5.0 red line |
| --- | --- |
| `precedes`, `guarded_by` | `declare the order as flow(ID, source=..., nodes=[Node(...), ...], edges=[...])` |
| `transitions`, `Transition` | `delete it; 5.0 checks no state changes, states(...) still checks the values a field is given` |
| `flow(..., transitions=...)` | `delete transitions= from this flow; 5.0 checks no state changes` |
| `checks` | `bind the rule to its scenario test with flow(ID, ..., relations=[Relation(RULE, {...}, Read(...))])` |
| `distinct` | `delete it; two rules of one decides= key must agree unless one overrides= the other, and python -m flowguard known add copies:NAME --act ignore --why TEXT records copies that are meant to differ once python -m flowguard check --all lists them` |
| `structure_rule` | `delete it; states(...) checks the literal values a field is given, an ordinary test can check any other source fact` |
| `allow` | `delete it with its structure_rule` |
| `@pytest.mark.rule("LIMIT")` on a test | a red `marker` line at the test: `delete the marker; a rule is checked at its anchors, not through marked tests` |

Without `distinct`, two rules of one `decides=` key that disagree are a conflict, and two keys on one decision site get the question `one decision under two names?`, which ends `(merge the keys)`. A flow's finite model is its graph alone, one state per node; a finite invariant over a state field stays unverified.

In the two-copy example of the [skill's reference](../.agents/skills/flowguard/reference.md), this flow over the `ACCEPT` copies loads and passes in 5.0:

```python
from flowguard.intent import flow, Node

flow('ACCEPT_FLOW', source='doc policy.txt "At most three days."',
     nodes=[Node('check', 'ACCEPT'), Node('answer', 'ACCEPT', phase='return')],
     edges=[('check', 'answer'), ('answer', 'check')])
```

The 4.3 form with `transitions=[Transition('check', 'answer')]` (and `Transition` imported) is refused:

```text
red: load order_flow.py:1: Transition was removed in 5.0 -> delete it; 5.0 checks no state changes, states(...) still checks the values a field is given; until then none of its file is checked
red: load order_flow.py:3: flow(transitions=) was removed in 5.0 -> delete transitions= from this flow; 5.0 checks no state changes; until then none of its file is checked
```

## Comment spellings

5.0 no longer reads the 4.2 spellings, with `#` in Python and `//` in TS/JS. Each is a red line of its own at its place, binds nothing, and its step is the 4.3 comment that says the same, as the "Comment spellings" table of the [4.3 notes](upgrade-4.3.md) gives it. pytest, `check` and `check --static` print the same step.

| 4.2 comment, in `shop.py` | 5.0 red line |
| --- | --- |
| `# flowguard: owner FEE` above `late_fee` | `red: comment shop.py:1: owner NAME above a function was removed in 5.0 -> write # flowguard: same FEE ref` |
| `# flowguard: sensor FEE` | `red: comment shop.py:6: sensor was removed in 5.0 -> write # flowguard: same FEE` |
| `# flowguard: owner Booking.status with=Booking.closed_at=None on=update alone=reopen(the owner reopens by hand)` | `red: comment shop.py:11: owner with= and alone= were removed in 5.0 -> write # flowguard: together Booking.status Booking.closed_at=None on=update except=shop.py:reopen(the owner reopens by hand)` |
| `# flowguard: owner Booking.unit_id writers=move,reserve` | `red: comment shop.py:21: owner writers= was removed in 5.0 -> write # flowguard: writers Booking.unit_id move,hold.py:reserve,reserve` |
| `# flowguard: owner Booking.price writers=price_up with=Booking.priced_at` | `red: comment shop.py:30: owner writers= and with= were removed in 5.0 -> write # flowguard: together Booking.price Booking.priced_at and, on its own line, # flowguard: writers Booking.price price_up` |

A 4.2 bare name in `alone=` or `writers=` meant the function of that name in any file, so the step names every such function of the map: here `hold.py` also has a `reserve`. Written as the steps say, the agreements loosen nothing and the run is `0 red`. Leaving out `hold.py:reserve` allows less and loosens nothing either; deleting a 4.2 line, dropping a partner, or adding a writer or an `except=` is a `loosened` line, as it would be for the 4.3 comment (`loosened: reopen added to writers Booking.unit_id -> name it in your report; loosening an agreement is the owner's decision`). An `owner NAME` on no function is told to write `same NAME ref` above the function it names, or to delete the comment.

## The ledger's `[structure]` and `[unverified]` sections

A ledger that still has one of these sections gets one red line naming it, in pytest, `check`, `check --static` and `python -m flowguard ledger check`, and what the section holds is not read. The handler entries of the ledger keep their meaning.

This 4.3 decision is refused:

```toml
[structure."declarations:Status"]
decision = "The report shows late bookings while a booking itself is never stored as late."
source = "R1"
```

```text
red: ledger.toml: [structure] was removed in 5.0 -> delete the section and record each decision in .flowguard/known.toml: python -m flowguard known add NAME --act leave|ignore --why TEXT
```

The 5.0 form is the `known.toml` entry that `known add` writes from the decision's words (see the upgraded project above):

```toml
[known.declarations-status]
sites = ["report.py:Status"]
why = "The report shows late bookings; a booking itself is never stored as late (R1)"
act = "leave"
finding = "declarations:Status"
```

`act = "ignore"` is for a false finding: it takes the finding's line out of every run and, for a finding the brief counts (a field's writers, deletes, columns, `onDelete`, labels, tables nothing fills, copies that drifted apart), the finding out of the brief's count of open structure problems, as a 4.3 decision did; `leave` keeps such a finding counted and lists it as `known` when a change touches its site. A `declarations:` finding, as here, is not in the brief's count: for it `ignore` only takes the line out, and `leave` lists it as `known`.

`[unverified]` has no replacement:

```toml
[unverified]
"rule.WINDOW" = { reason = "the window rule reads a clock the tests cannot set" }
```

```text
red: ledger.toml: [unverified] was removed in 5.0 -> delete the section; nothing replaces it: restore each rule's observability so it is checked again
```

`check --all` fails a grey rule whose source quotes the owner's words, and nothing exempts it.

## Notices and hidden leads

| 4.3 | 5.0 |
| --- | --- |
| `deprecated: sensor goes in 5.0 -> write same NAME` on stderr, once per process, after the block. | No notice: the feature is a red line or a usage error, as above. Nothing is announced for a later removal. |
| `show --last` ended with `deprecated features used (5.0): function owner, owner with=, sensor`. | Under each line, `show --last` names its finding (`finding declarations:Status`), the name `known add` takes. |
| `show --last` listed FlowGuard's own leads under `deprecated leads (5.0)`: old values that other decisions still spell, label spellings, similar implementations, the copy discovery listing and `copies at X changed; rule R is unchanged`. | Gone, with nothing in their place. The findings those checks also make stay: `copies:` for a diverged copy, `changed-alone:` and `declarations:`. |

## New in 5.0

### What the map knows about a name

`python -m flowguard show NAME` starts, after the entries and agreements that concern the name, with what the map read about it. `Model.field` gives the Prisma declarations, the SQL columns, the value sets, the `CHECK` ranges and the zod bounds, those of the field's own schema objects first, each schema object belonging to the model whose name is the longest model name its camel-case words hold (`lendingAssignmentCreateSchema` to LendingAssignment, not Assignment); `table.column` answers with the Prisma field its `@@map` and `@map` map to it, as `Model.field` does (`show assignments.fte_share` prints the lines below). In a project with a Prisma schema, one migration and one zod schema:

```text
show Assignment.fteShare
Map: prisma 1/1 parsed; sql 1/1 parsed; typescript 3/3 parsed; static facts, foreign native-home execution not verified.
declared Assignment.fteShare: Float @map("fte_share") (backend/prisma/schema.prisma:8)
column assignments.fte_share DOUBLE (backend/prisma/migrations/20260101000000_init/migration.sql:3)
range assignments.fte_share: 0 <= fte_share <= 2 (CHECK backend/prisma/migrations/20260101000000_init/migration.sql:5)
zod key fteShare in assignmentSchema: 0 <= fteShare <= MAX_FTE_SHARE=1 (backend/src/schemas.ts:6)
... 3 more lines, 2 of them only share a word with Assignment.fteShare: python -m flowguard show Assignment.fteShare --full lists them all
```

The SQL reader reads a `CHECK` that bounds one column by numbers (`>=`, `>`, `<=`, `<`, `BETWEEN`, either side) in `CREATE TABLE` and `ALTER TABLE ... ADD CONSTRAINT`. `show AssignmentStatus` gives `values AssignmentStatus: DRAFT | ACTIVE | CLOSED (enum AssignmentStatus backend/prisma/schema.prisma:13)`, `show MAX_FTE_SHARE` gives `const MAX_FTE_SHARE = 1 (backend/src/schemas.ts:3)`, `show assignmentSchema` gives `const assignmentSchema = z.object(...) (backend/src/schemas.ts:5)` and the zod line of its key, and `show Assignment` gives one line per schema and table and the count of writes and reads:

```text
model Assignment (table assignments): 3 fields (backend/prisma/schema.prisma:6)
table assignments: 3 columns (backend/prisma/migrations/ as its migrations leave it, created at backend/prisma/migrations/20260101000000_init/migration.sql:1)
Assignment on the map: 0 writes in 0 functions, 0 reads in 0 functions: python -m flowguard show Assignment.FIELD lists the writes and reads of one
```

A function's name gives its node view: its id and place, its signature, the fields it writes and the functions that call it through a call the map resolved; `object.method` gives the method also when a module function of the file has its name, as a generated region names it (`show capacityService.sliceDateRangeByMonth`). A write in a test file that the test scope leaves out, or that a script runs as a suite that reaches real databases and services, says so on its `writes` line as on its `test ... reaches a writer` line. An object literal or class that holds functions gives its place and members. A name the map does not know gets one `not on the map` line, and a misspelt field names the model's nearest field.

### Lists generated from the code

The lines between `<!-- flowguard: generate KIND ARG -->` and `<!-- flowguard: end -->` in a Markdown file are FlowGuard's. `python -m flowguard docs` writes them; the kinds are `fields Model`, `values NAME`, `functions path` and `constants path`, and none carries a line number. With an empty region under `<!-- flowguard: generate fields Assignment -->`:

```text
impact: assignments.md:8 generate fields Assignment is out of date -> python -m flowguard docs rewrites it
```

```markdown
<!-- flowguard: generate fields Assignment -->
| Field | Type | Column |
|---|---|---|
| id | Int | id |
| fteShare | Float | fte_share |
| status | AssignmentStatus | status |
<!-- flowguard: end -->
```

A relation field has no column: its cell names the model (`| demand | Demand? | relation Demand |`). `functions path` names each function and method of the file as a flowguard comment or `show` does, `capacityService.sliceDateRangeByMonth` for a method of an exported object, with its whole signature as declared, and leaves out what another function holds: a closure, a callback, an object literal's method.

A region holds only what the map knows: names, signatures, values, fields, types and columns. Prose such as the Purpose column of a hand-written function list has no place in it; keep it outside the region, in a text or a table of its own above or below it, when you replace such a list by a region. A region that lists a file's functions or constants, or a model's fields, is a text that describes them: `show` of that file, of a name it lists or of a field of that model says `described by docs/FUNCTION_INVENTORY.md:307 (generate functions backend/src/services/central-employee.service.ts)`, and the module view gives such a file no `described by no text` advice.

A region is named when the change edits what it is written from, or the region or its marker. One this change writes that cannot be generated is red: `red: generate values Nope: no value set of that name -> correct the marker at lists.md:12`. Write around a region, not inside it.

### Texts tied to the code they describe

```markdown
<!-- flowguard: about backend/src/share.ts:totalShare -->
The total share of a person adds the shares of their assignments.
```

When a change edits `totalShare` and not the text, the run says `impact: assignments.md:3 describes backend/src/share.ts:totalShare, which this change edits -> reread that text and correct it if it no longer holds`. It never fails a run, and a change that edits both says nothing. A marker this change writes that names nothing is red (`red: about backend/src/share.ts:sumShares: ...`). A `known.toml` site may be a Markdown file's path alone (`sites = ["docs/setup.md"]`); FlowGuard 4.3 reads such an entry as invalid. A marker or `known.toml` site on a `.sql` file names a table or `table.column` its statements name, or the Prisma `Model.field` mapped to one (`backend/prisma/azure-sql-setup.sql:Assignment.fteShare`); a file whose statements are all in comments names none (`site backend/prisma/constraints.sql:Assignment.fteShare names nothing in backend/prisma/constraints.sql: name one table or table.column of that file (the map reads no table statement in it)`).

### Module contracts

A text about a file or a folder (`<!-- flowguard: about backend/src/report.ts -->`, a folder with its trailing `/`) is that module's contract. A change to a function of another file that the module calls, or that calls it, names the contract once:

```text
impact: report.md:3 describes backend/src/report.ts, whose backend/src/report.ts:overbooked calls backend/src/share.ts:totalShare, which this change edits -> reread that text and correct it if it no longer holds
```

`python -m flowguard show backend/src/share.ts` lists a module's contracts and connections, after the header and the Map line every view begins with:

```text
show backend/src/share.ts
Map: prisma 1/1 parsed; typescript 2/2 parsed; static facts, foreign native-home execution not verified.
module backend/src/share.ts: 1 file, 1 function
described by no text: put <!-- flowguard: about backend/src/share.ts --> above the Markdown text that is its contract
called by backend/src/report.ts (1 call; described by docs/report.md:3)
```

The connections are the calls the map resolved, never a method matched by its name alone. Each text the module has comes right after its known entries with the site its marker names, and a connected module's text says so when its marker names a folder. With `<!-- flowguard: about backend/src/ -->` in `docs/report.md` and `<!-- flowguard: about backend/src/share.ts:totalShare -->` in `docs/assignments.md`:

```text
show backend/src/share.ts
Map: prisma 1/1 parsed; typescript 2/2 parsed; static facts, foreign native-home execution not verified.
described by docs/report.md:3 (about backend/src/)
module backend/src/share.ts: 1 file, 1 function
called by backend/src/report.ts (1 call; described by docs/report.md:3 about backend/src/)
```

`show totalShare` begins with the texts whose marker names the function, its file or a folder holding it (a marker on a symbol only when `check --static` resolves its site to that function: `backend/src/share.ts:sumShares` describes nothing), after its known entries (it has none) and before its node view, and `show docs/assignments.md` lists a document's markers and generated regions:

```text
show totalShare
Map: prisma 1/1 parsed; typescript 2/2 parsed; static facts, foreign native-home execution not verified.
described by docs/assignments.md:3 (about backend/src/share.ts:totalShare)
described by docs/report.md:3 (about backend/src/)
```

```text
show docs/assignments.md
Map: prisma 1/1 parsed; typescript 2/2 parsed; static facts, foreign native-home execution not verified.
document docs/assignments.md
docs/assignments.md:3 describes backend/src/share.ts:totalShare
docs/assignments.md:8 generate fields Assignment is out of date -> python -m flowguard docs rewrites it
```

### JSON data in TS/JS

A TS/JS call is recorded and compared when its arguments and result are JSON data: `null`, booleans, strings, finite numbers, and arrays and plain objects of them; each argument and the result may hold at most 200 arrays and objects, nested at most 7 deep counting the value itself (primitives are not counted). 4.3 recorded only primitives, and this call of a function that takes rows was `not compared`; 5.0 compares it:

```text
changed: totalShare (share.ts:1): (rows=[{"fteShare": 0.5}, {"fteShare": 0.25}]) was 0.75, now 0.8; 1/1 inputs differ -> if you meant it, say so
```

A getter, a proxy, a class instance, a `toJSON`, a symbol key, a hole, `undefined`, `-0` or a key that starts with `$` is not data, and telling so runs no project code.

### Recording a finding

`python -m flowguard known add FINDING --act leave --why TEXT` (or `--act ask`, `fix` or `ignore`) appends a `known.toml` entry whose sites are the places of the last run's lines of that finding; `show --last` names each line's finding. After a run with `before: same FEE disagreed at task start on days=5: ...`:

```bash
python -m flowguard known add same:FEE --act ask --why "The preview charges 3 per late day, the invoice 2" --ask "Which daily late fee is right, 2 or 3?"
```

```text
known.same-fee added to .flowguard/known.toml: act ask, sites fees.py:late_fee, fees.py:preview_fee, finding same:FEE
```

The entry is checked as a run reads it, and the file is left as it was when it does not load. `--id` names the entry and `--site path:symbol` gives its sites instead of the finding's places.

A matter no check finds, such as a page that names a command the project no longer has, takes `-` for the finding and its sites from `--site`, which may also be a Markdown file's path alone:

```bash
python -m flowguard known add - --act ask --why "The setup page names a make target that is gone" --ask "Should the setup page name npm run setup?" --site docs/setup.md --id setup-target
```

```text
known.setup-target added to .flowguard/known.toml: act ask, sites docs/setup.md
```

Without `--id` such an entry is `matter` (then `matter-2`, ...).

### What `show` begins with

`show NAME`, `show PATH`, a rule's and a flow's view begin with what is already known and decided about the query: the `known.toml` entries in the brief's words, the texts that describe it, the intent rules and the `rules.toml` rules they cite, the flowguard comment agreements, and the last run's lines there (five without `--full`):

```text
show fees.py
known.same-fee: open question for the owner: Which daily late fee is right, 2 or 3? (python -m flowguard show known.same-fee)
same FEE ref fees.py:2
same FEE fees.py:7
together Job.status Job.closed_at fees.py:11
module fees.py: 1 file, 3 functions
described by no text: put <!-- flowguard: about fees.py --> above the Markdown text that is its contract
```

Every view begins so: the `show QUERY` header, the Map line when the map reads more than Python, what concerns the query, then the view's own lines (a site's or a map id's node view, a module's or a document's lines).

`show same-fee`, an entry's bare id, prints the entry, and `show "late fee"` also lists the entries whose why or ask shares those words.

### The brief

The brief still has at most eight lines. It counts the generated regions the last check or docs run found out of date (`1 generated region is out of date (last check or docs run): python -m flowguard docs rewrites it`, and those that cannot be written), says when `AGENTS.md` or `CLAUDE.md` holds another FlowGuard rules block, and names such a file that is no UTF-8 or UTF-16 text with the decoder's error. Its structure line points at `check --all`, which also lists copies that drifted apart.

## What you may notice

| 4.3 | 5.0 |
| --- | --- |
| `known: known.fee-copies at fees.py:late_fee, fees.py:preview_fee -> ask owner (not asked yet)` | `known: known.fee-copies at fees.py:late_fee, fees.py:preview_fee: Which daily late fee is right, 2 or 3? -> an open question for the owner, not asked yet`. This entry names the finding `same:FEE`, and a change that touches that finding gets a known line that names the finding's places this change touches, with their count (`known: known.fee-copies at fees.py:preview_fee (1 of 2 places): ...` for an edit of `preview_fee`), and every place when it touches none of them. Otherwise a known line names the entry's sites this change touches, with the entry's count when it has others (`known: known.fee-copies at fees.py:close (1 of 3 sites): ...`). An `ask` entry's question follows the places. |
| An entry asked on a date: `-> asked on 2026-11-15; leave it until the owner answers`. `leave`: `-> leave it (the owner deferred it)`. `fix`: `-> fix it in this change and say so in your report`. | `-> asked the owner on 2026-11-15; no answer yet`, `-> left as it is on purpose; yours to change only if your task is about it`, `-> marked to fix when its code changes, as this change does`. |
| `known fixed?: known.fee-copies: copies of FEE now agree -> the owner has not decided: revert, or say why in your report`; for a `leave` entry `-> the owner deferred it: revert, or say why in your report`, for `fix` and `ignore` `-> say so in your report; remove known.fee-copies once the owner agrees`. | `... -> the owner has not answered known.fee-copies: if this change settles it, say so in your report`; `leave`: `-> it was left on purpose: if you meant to fix it, remove known.fee-copies and say so in your report`; `fix`: `-> if you fixed it, remove known.fee-copies and say so in your report`; `ignore`: `-> if it is fixed, remove known.fee-copies and say so in your report`. |
| `loosened: except=reopen added to together Job.status -> name it in your report; needs the owner's yes` | `... -> name it in your report; loosening an agreement is the owner's decision` |
| `show`'s fix of a together agreement: `fix: also write Project.leaderId in the same operation; only with the owner's yes add except=path:function(reason) to the together agreement (backend/src/services/project.service.ts:2), which the next run shows as loosened` | `fix: also write Project.leaderId in the same operation as each write marked missing; an except=path:function(reason) on the together agreement (backend/src/services/project.service.ts:2) loosens it, which is the owner's decision and the next run shows as loosened` |
| `show Assignment.fteShare` on Planning Tool: `with= candidate (reference only): Assignment.periodEnd is written by 10 of the 10 functions that write Assignment.fteShare -> if the owner says they change together: // flowguard: together Assignment.fteShare Assignment.periodEnd` | `together candidate (reference only): Assignment.periodEnd is written by 10 of the 10 functions that write Assignment.fteShare -> if they must change together: // flowguard: together Assignment.fteShare Assignment.periodEnd` |
| `check --static --all`, a change that adds a writer to a field several files write: `impact: no writers agreement for Job.status: archive.py:archive writes Job.status, which 4 files write without a writers agreement -> fix it, or say why in your report` | `... -> which functions should write it may be the owner's decision; name it in your report` |
| A `known.toml` entry with `act = "ignore"` took the lines of its finding out of every run, and the brief still counted the finding: `0 open structure issues (1 other fields have multiple writers and no writer agreement); highest severity: write Job.status`. | The brief no longer counts it either, as it did not count a finding a 4.3 `[structure]` decision closed; `leave`, `ask` and `fix` entries keep their finding counted. To have it counted again, write `act = "leave"`. |
| The brief: `known.fee-copies: ask owner: Which daily late fee is right, 2 or 3?`; an asked question `asked on 2026-11-15; leave it until the owner answers: ...`, a `fix` entry `fix: ...`, a `leave` entry `leave it: ...`. | `known.fee-copies: open question for the owner: Which daily late fee is right, 2 or 3?`; `asked the owner on 2026-11-15, no answer yet: ...`, `to fix when its code changes: ...`, `left as it is: ...`. Their order is a correction, below. |
| `not compared: ROUND (no recorded JSON inputs) -> not a failure` on every run, for same-name copies no test called (vitest: `not reached by any test`). | Nothing until a change edits a copy or writes its mark; `check --all` still lists them. |
| `not compared: totalShare (share.ts:1) (only primitive JSON arguments and results are recorded) -> not a failure` | `changed: totalShare (share.ts:1): (rows=[{"fteShare": 0.5}, {"fteShare": 0.25}]) was 0.75, now 0.8; ...` |
| SQL inside a string literal of a SQL file (`EXEC(N'ALTER TABLE ... ADD ...')`) was read as SQL that runs. | It is not read: a column, a `CHECK` or a write that only such SQL adds is not declared, so the columns check may give one more `before` line. A string ends where its dialect ends it (`E'it\'s'`, a dump's `'O\'Brien'`). SQL in Python string literals and TS/JS raw SQL is read as before. |
| A label-table disagreement was a `before` line for any edit of a file that holds one of its tables. | Only when the change edits the declaration lines of one of its tables; a change that adds a table or changes its keys or labels gets an `impact` line. |
| A one-line edit of the assignments CHECK in Planning Tool's azure-sql-setup.sql: `FlowGuard 4.3 (since 139895c): 0 red, 7 before`, `before: declarations CapacityCalendarEntry.entryType at azure-sql-setup.sql:775 was broken at task start`, `before: declarations DeputyAssignment.role at azure-sql-setup.sql:114 ...` and five more, six of them about other tables. | A declarations or columns finding is touched through a SQL file only when the change edits a statement of its table there (CREATE, ALTER or DROP TABLE, the CHECKs they hold): `0 red, 1 before`, the file's columns line, which names assignments; an edit of a comment outside the statements gives none. |
| `show typescript/backend/src/utils/capacity-conversion.ts:convertPercentToHours`, a map id, began with its node line, signature and doc, then the Map line. | `show typescript/backend/src/utils/capacity-conversion.ts:convertPercentToHours`, the Map line and what concerns it (its known entries, the texts that describe it), then the node view. The views new in 5.0, a site `path:symbol`, a file, a folder and a document, begin the same way. |
| `check --static --all`: `before: no writers agreement for Job.status at close.py:close was broken at task start -> leave it unless your task is about it` | `before: Job.status has no writers agreement and 3 files write it, close.py:close among them; so at task start -> leave it unless your task is about it`, the files that wrote it at task start, not a writer the change adds. The other families still say `was broken at task start`. |
| `show` of a TS/JS function or anchor printed `not searched: not searched: ... -> bind the real decision site` and `copy search unavailable: ...`; an anchor on a Python function printed `copy search unavailable: not searched: no readable decision sites -> bind the real decision function`. | One line, `copies not searched: ...`, without a bind step for a TS/JS function or a Python function an anchor already marks: `copies not searched: no readable decision sites`. An agreement on a TS and a TSX copy: `copies not searched: the map reads no decision sites in typescript and tsx code`, once. |
| `show Project.lifecycleStatusId` of a TS/JS writers agreement: `anchor Project.lifecycleStatusId -> typescript/backend/src/services/project.service.ts: backend/src/services/project.service.ts:1`, `owner Project.lifecycleStatusId backend/src/services/project.service.ts:1; writers=typescript/backend/src/services/project.service.ts:create,typescript/backend/src/services/project.service.ts:update`, then `Project.lifecycleStatusId: historical observations (not a new verification)`, `results: {}; 0 distinct observed outputs`, `rules: ` and `info: not referenced by a current model: Project.lifecycleStatusId`, all under the header `ANCHOR Project.lifecycleStatusId`. A `same` reference read `owner FEE fees.py:2; ...`. | `show Project.lifecycleStatusId` and the map notice, as every view begins, then `anchor Project.lifecycleStatusId -> backend/src/services/project.service.ts:1` and `writers Project.lifecycleStatusId projectService.create,projectService.update backend/src/services/project.service.ts:1`, the 4.3 comment spelling at the agreement's place, then its fix, declaration and writes; no empty observation lines or `rules: `, and for no agreement (`same`, writers or together) a `not referenced` line. A `same` reference reads `same FEE ref fees.py:2; ...`. |
| `show`'s node view cut a function's signature at 160 characters, also inside a word (`buildLendingSummaryForWindow( lendingAssignments: Array<{ ... fteShare: Prisma.Decimal; valid`). | The whole declaration header, as the source spells it. |
| A long `not compared` line was cut at 200 characters wherever that fell, also inside an item's name or place. | Paths and places do not count toward the 200 characters, the reasons are shortened first, and items that leave no room are counted (`not compared: 3 functions (...) -> not a failure`). A single item keeps its name and place. |
| `not compared: TimeRangeSelector (TimeRangeSelector.tsx:39) (unsupported jsx_element) -> not a failure`; in Python `unsupported With`. | The construct in a few words: `(holds a JSX element)`, `is async`, `holds a with statement`; the line keeps whole reasons, `not compared: 3 functions: TimeRangeSelector (...), loadPlanning (...) and PlanningGrid (...) (holds a JSX element, or is async) -> not a failure`. |
| `show Assignment.fteShare` listed `test backend/tests/integration/lending.routes.test.ts reaches a writer of Assignment.fteShare` like a unit test. | `... reaches a writer of Assignment.fteShare (a suite that reaches real databases and services: backend/package.json script "test:integration" runs tests/integration)`; a test the test scope leaves out says `(left out of the test scope: ...)`. |
| `show batchAssignSchema` of a zod constant: `word matches: the 191 lines below only share a word with batchAssignSchema`. | `const batchAssignSchema = z.object(...) (backend/src/api/schemas/assignment.schemas.ts:21)` and its keys' zod lines; the names that share a word wait for `--full`. |

## Corrections of 4.3 bugs

These are corrections within the existing contract, separate from the new behaviour above:

- On a machine without FlowGuard, the npm static test and the vitest plugin failed every run, so a project's own tests could not pass there. Now the static test is skipped under a name that says FlowGuard is not installed, and the vitest config gets no plugin and one notice; a `FLOWGUARD_PYTHON` that cannot import FlowGuard still fails. Run `init` to rewrite the two generated files.
- An unchanged copy compared on some of its inputs was `not compared` when a made-up input gave a result that is not data (Planning Tool's three ISO week copies in every frontend run: `86400000 + 1` taken as a year gives `NaN`). Only a real call that could not be recorded or run is `not compared` now.
- The brief put an asked but unanswered question after the `fix` and `leave` entries, so Planning Tool's open questions fell out of its eight lines.
- The brief's structure line pointed at `check --static --all`, which runs no copy discovery, so copies that drifted apart were counted but not listed there.
- A rule source quoting a UTF-16 document ended `show rules` and `check --static` with exit 2 and `flowguard: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte`, and so did `init` on a UTF-16 `AGENTS.md`. Rule sources, ledger rules, the brief and `init` read UTF-16 and UTF-8 with a BOM now, and `init` writes the file back in its encoding; a document in another encoding is that reader's problem, naming the file.
- A 4.3 cross-file writer or exception (`path:function`) whose target file was renamed gave a false `loosened` line.
- In TS/JS, a flowguard comment after a line that holds U+2028, U+2029, a form feed or another character Python's `splitlines` breaks at was numbered one line late. For a `// flowguard: same FEE` right above its function, 4.3 said `red: comment a.ts:4: a.ts:4: sensor FEE needs a function declared on the next line -> correct this flowguard comment`; 5.0 counts lines at newlines only, as the JS/TS parser does, and the run is `0 red`.
- An assignment whose object a resolved Prisma write passes on (`updateData.lifecycleStatusId = ...` before `tx.project.update({ data: updateData })` in a `$transaction` callback) counts as that one write. 4.3 also reported the callback as a writer outside the agreement, a second line for one write: `before: writers Project.lifecycleStatusId at import.service.ts:ImportService.commitProjects.<anonymous@3,31> was broken at task start -> leave it unless your task is about it` beside the line of `ImportService.commitProjects`, or a second `red` when the change added the code.

## Known limits

- A rule in `tests/intent/` runs only Python functions; TS/JS copies are compared by `same` alone. Only inputs the tests used are compared (copies add their numbers and ±1). Functions that read configuration or a database, or call helpers of another file, are not compared sealed.
- A TS function runs sealed in steps of at most 100 ms, and its `not compared` line does not yet tell a timeout from a failure (`sealed execution failed or timed out`).
- vitest keeps its own cache in FlowGuard's adapter folder (`flowguard/adapters/vitest/node_modules/.vite`), as in 4.3.
- Whether `changed` catches an unintended change in a real task is not yet measured. `impact` counts the readers of a model, not yet of one field.
- zod lines read `z.number(` and `z.coerce.number(` chains, also inside `z.optional(`, `z.nullable(`, `z.nullish(`, `z.preprocess(` and a pipe. zod 4's `z.int()`, `z.union(...)` and a shorthand key (`{ fteShare }`) give no line; `.or(...)` and `.catch(...)` on a number chain are not named, so `z.number().min(0).or(z.string())` reads `0 <= fteShare`; a schema object a function returns is `an unnamed object`.
- SQL that a string builds at run time is not read, also when an `EXEC(N'...')` holds one complete literal; on Planning Tool, `assignments.internal_order_id`, which only such SQL adds, is one more `before` line of the columns check in `check --static --all`. In a plain string, `\'` counts as MySQL's escaped quote only before a letter or digit: `'rock \' roll'` ends at `\'`, and the statements after it are read as inside a string.
- The pair and delete checks still resolve JS/TS member calls by name, and a delete finding says `(calls resolved by name)`. The module view and contracts count resolved calls only, so a destructured dynamic import (`const { x } = await import(...)`) connects nothing.
- `show` gives no const line for a Python module constant, `generate constants` lists JS/TS constants only, and a Python name whose value is no literal, such as `Status = Literal[...]`, gets a `not on the map` line. A TS interface or type name gets no declaration line. Holder lines cover JS/TS object literals and classes; a Python class gets its node view.
- `known add` turns a place into a site only where a function, constant or `Model.field` is declared; for another declaration, such as that `Status`, give `--site path:symbol`.
- Only the writers family states what held at task start; labels, delete, together and the other families still say `was broken at task start`.
- After the upgrade the brief shows no structure or region line until the first `check`, `python -m flowguard docs` run, or pytest run while the task has changed code, because its saved counts moved to a new key; the first run also rebuilds the map.
- Generated regions cover four kinds; routes, environment variables and package scripts are not generated. A Markdown document that is neither UTF-8 nor UTF-16 is named only when a change edits it.
- `show` of a constant does not name its users: `show batchAssignSchema` does not name the route that applies it (`validateBody(batchAssignSchema)`), and `show MAX_FTE_SHARE` no reader.
- A zod validator that a route applies is not linked to the model the route's service writes: a field's own schema objects are found by their name alone, so `lendingCreateSchema`, which Planning Tool's lending routes validate before LendingAssignment.fteShare is written, is among the keys of other schema objects in `show LendingAssignment.fteShare`.
- A `known` line that comes from an entry's finding names the finding's places: an edit of a site of the entry that is no place of the finding (`fees.py:close`) names every place of the finding (`at fees.py:late_fee, fees.py:preview_fee`) without a count, where `check --static` names the edited site (`at fees.py:close (1 of 3 sites)`).
