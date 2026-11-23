# Changelog

## v5.1.0 - 2026-11-23 - Field feedback on 5.0.1: the owner's pick among offered options

A minor release: backward-compatible features and corrections within the 5.0 contract, answering what the agents maintaining Planning Tool (a TypeScript full-stack app) and PEMEL Studio (a Python desktop app) reported on 5.0.1 (R105). Every 5.0.1 saved input keeps its bytes and meaning, and old material needs no migration. The owner-word archive gains a record kind, `choice`, with its own files and sidecar fields, and sources gain a form, `R<n> picked "words"`; FlowGuard 5.0.x reads a choice's sidecar as invalid (`invalid request sidecar fields`, with its restore advice), so a project requires 5.1 before it stores one. A request stored by 5.0.1 (`R74 "words"` and its sidecar) loads, lists, shows and holds as before; `R104 picked "..."` on such a plain request is refused with its step.

New:
- `show --last` keeps one last run per slot and prints each, newest first, with the full version of the FlowGuard that ran it (PTWF-3b, PTWF-3a, PTWF-3d): pytest, `check` and `check --static` share the `repo` slot, and each vitest package has its own, `FlowGuard 5.1.0 last run: vitest web/ at 2026-11-23 08:21:55`. A slot whose package folder no longer holds a vitest or vite config is not read. Under a pytest run's header comes pytest's own outcome (PEMEL17-12), `pytest: exit 1, 1 failed, stopped early (-x)`, also `1 error`, `stopped early (--maxfail=2)`, `interrupted` or a `pytest.exit` reason: the block's `0 red` counts agreements, and read alone later it no longer hides that the tests failed. After the runs, `show --last` lists what the brief counts besides their lines: the intent results' reds, and each failed test kept from its last run (PEMEL17-14), `tests/test_a.py::test_x: failed (call) at 2026-11-23 12:54:36; not selected by the last pytest run, at 2026-11-23 12:54:37`. A vitest run notes its start in its package's slot when it prepares, and its report replaces the note, so a run that never reports says so (PTW-V2-2): `a vitest run of web/ started at 2026-11-23 12:55:08 did not report; the lines below are from the run at 2026-11-23 12:55:00`.

- The owner's pick among options the agent offered is his original choice and is recorded too, never with the agent's option text attributed to him (R105). `python -m flowguard req add REPLY --id R106 --offer OPTIONS --picked "TEXT"` (`--picked` once per option for a multi-select, `--selected` when he picked without typing) stores one `choice` record in the same archive: his reply, as it reached the agent, in `.flowguard/requests/R106.md`; the question and options, exactly as the agent showed them, in `.flowguard/requests/offers/R106.md`, kept as the agent's words and never listed as a request; and a sidecar with the options' digest and size, each picked option's whole text and `reply` `typed` or `selected`. Both files are written once with their first-write receipts and checked against their original bytes as a request is: an edited or deleted options file makes the record unverified (`offer of R106 differs from its stored original -> restore the stored original`). Each picked text must occur exactly once in the options, compared after CRLF and CR become LF. A `--picked` or `--selected` without `--offer`, an `--offer` without `--picked`, an empty options file, a picked text that occurs 0 or 2 or more times (`choice_picked_absent: "..." occurs 0 times in the offer; ...`) and a stored id are refused with exit 2 and write nothing. `req add` prints `stored R106 (choice: the owner's reply 5 bytes, the agent's options 106 bytes, 1 picked; sha ...)`, for a selected answer `stored R107 (choice: the answer selected 53 bytes, ...)`, and a reminder naming `source = 'R106 picked "<words of the picked option>"'`, for a typed reply also `'R106 "<his exact words>"'`. `show R106` prints `OWNER R106 chose among options the agent offered`, his reply (or `the owner selected, with no words of his own:` and what the interface returned), the options under `options the agent offered (the agent's words, not the owner's) .flowguard/requests/offers/R106.md:` and each `picked: "..."`, the reply and the options read as the checks read them (UTF-8, or UTF-16 by its byte order mark, as Windows PowerShell 5.1's `>` writes it); bytes that are neither stop `show` with the decoder's text, `flowguard: .flowguard/requests/R106.md is no UTF-8 or UTF-16 text: 'utf-8' codec can't decode byte 0xe9 in position 3: invalid continuation byte` (exit 2), and nothing is replaced. `req list` shows the record as `choice`. On 5.0.1, `req add --offer` was an unknown argument: an agent could store only the owner's `选 A`, which says nothing alone, or the options as if they were his words.
- A source in `rules.toml`, `known.toml` or an intent rule cites words of a picked option as `R106 picked "words"`: they must occur exactly in an option he picked, and that option in the stored options. Words of an option he did not pick are refused (`"直接删除" is in the options R106 offered, not in one the owner picked -> quote the option R106 picked`), as are words in no option (`"..." is not in the option R106 picked -> quote the picked option exactly`) and the form on a request that holds no options (`R104 holds no offered options -> quote its words: R104 "words"`). `R106 "words"` quotes his typed reply as for any request and is refused for a selected one (`R106's answer was selected, not written by the owner -> quote the option: R106 picked "words"`). Both forms are judged at the task's baseline with that commit's sidecar, reply and options; a choice stored in this task was not stored then, as for a request. A picked source citing an id not stored, now or at the baseline, names the choice route, `R9 is not stored -> store his reply with the options you offered: python -m flowguard req add REPLY --id R9 --offer FILE --picked "TEXT"`: a plain request under R9 would close it, as the archive is written once. A source written as the pick without its words between double quotes says where they go, `source "R1 picked 'Keep one version'" names a pick: the option's words go between double quotes, R1 picked "exact words"`; one whose words are between them names the text after their closing quote, `source 'R1 picked "Keep one version" (A)' names a pick with text after the closing double quote of its words: ' (A)'`; and every refusal that lists the source forms names `R<id> picked "exact words"` (`... is neither R<id> "exact words", R<id> picked "exact words" nor doc PATH "exact words"`), which is what any other malformed pick gets, such as two spaces before its words or a head that is no request id (`owner picked 'x'`). Lines print a picked source that holds as `owner R106 picked "..." (the agent's option, the owner's pick)`, one that does not hold as the rule writes it (`R106 picked "直接删除"`), its red saying why, and `show rules` says `(holds: the agent's option, the owner's pick)`. A rule that cites the choice depends on its options file too. Two rules that cite the owner's records and disagree are his to settle, each side judged and named by what its source holds: `(owner R1, R2) -> the owner's words of the two rules disagree` for his typed words, `(owner R1 picked "Three days.", R2 picked "Four days."; the agent's options, the owner's picks) -> the owner's choices behind the two rules disagree` for two picks, `(owner R3, R2 picked "Four days." (the agent's option, the owner's pick)) -> the owner's words behind THREE and his choice behind FOUR disagree` for one of each, and `owner R5` on a record whose answer he selected as `R5 selected`. The `(owner ...)` list names only sides whose source holds; a side that does not hold is named outside it as the rule writes it, `(owner R1 picked "Three days." (the agent's option, the owner's pick); FOUR cites R2 picked "Three days.", which does not hold) -> the owner's choice behind THREE and the pick FOUR cites disagree`, as `the words FOUR cites` when it quotes words as his (`R3 "words"` the request lacks, `R5 "words"` on a selected answer), and with neither side holding there is no owner's list. `check --all` fails such a rule while it is grey (`cites the owner's pick among the agent's options (R106), but is now grey (unverified): ...`), as for his words.
- Rule 7 of the FlowGuard rules block `init` writes names the route: after "never your own text" it says "when he picks one of options you offered, store his reply with them (`--offer FILE --picked TEXT`), the options as your words and the pick as his". A project's brief says its block differs from this version's until `python -m flowguard init` rewrites it; rewriting a project's FlowGuard files is the owner's decision (R95). FlowGuard's own `rules.toml` gains `rule.offered-choice`, quoting R105.

- `show Class.field` of a Python class lists the functions that read it (PEMEL23-5a, PYREAD18-2): each read through `self` or `cls` in the class, a name its annotation types, a local name holding such a value (`settings = controller.settings`) or an attribute whose class declares its type (`controller.settings.appearance` when Controller declares `settings: Settings`), as `reads Pane._hovered app/pane.py:11 Pane.highlighted (attribute)`; `asdict(x)`, `astuple(x)` and `vars(x)` read every field of x's class (`(asdict)`), `replace(x, f=...)` every field but those it sets, and writes none of x. The class follows the annotation: `SettingsDialog.appearance` is another field than `Settings.appearance`. 5.0.1 listed only the writes. The map's facts hold these reads as `field_reads` (`MapHandle.field_reads`); a map cache an older FlowGuard built is rebuilt on the first run, as after any reader change.
- The node view of a Python method lists the functions that read it as an attribute (PEMEL23-5b): `show Pane.highlighted` of a property said only `called by no function through a call the map resolved`, as reading a property calls nothing; it now adds `read as an attribute by 1 function (untyped reads not counted): badge (app/badge.py:5)`, and a `@property` or `@cached_property` no such function reads says so.
- `show Class.field` of a field this change stopped writing lists, after its `not on the map` line, the writes and reads of the task-start code that no function has now (PEMEL23-6c): `writes Pane.title app/panel.py:6 Pane.__init__ (assign) at the task start`, `reads Pane.title app/panel.py:9 Pane.label (attribute) at the task start`. The step of a `no longer writes` impact line names this view, which 5.0.1 left with `not on the map` and words. A read compares by its function and kind, never by its line: on a tree with no change since `new-task`, `show PaneHandle.highlighted` of a @property and `show Controller._closing_window` of an attribute only read list each read once, as it reads now, and an edit that only shifts the lines adds no `at the task start` line; a function that no longer reads the field keeps its task-start line.

- The README, the intent guide and the skill reference describe routes 5.0 already had, for what the agents asked for (PEMEL23-4a, PEMEL23-11, PEMEL23-12, PTW-4.235-4, PTWF-4b, PTWF-V116b, PTW-G68-2). Agents that work at the same time use one git worktree each, with its own `.flowguard/cache`, task baseline and change set; in one working tree they share them, one agent's `new-task` moves every agent's baseline and each agent's uncommitted edits are part of the others' change. A marker's site may be any file of the repository, so a checked-in generated file is listed in a Markdown text under `about` markers for the function that produces it and for each file it is made from, with the command that regenerates it, and a data file a function reads under a marker for itself. `check --static` and `show rules` check the sources that `rules.toml` and `known.toml` quote without running the suite. That a route uses its owner function is a test's job: a module contract names a connection only while its call is there. `together` checks which fields one write holds, not values under a condition. A SQL file kept in the repository describes the tables it creates (one that only alters a table, none), and a description left out of date on purpose is recorded with `python -m flowguard known add columns:prisma/migrations/~prisma/schema.prisma --site prisma/migrations/20240101_init/migration.sql:central_employees --act leave --why TEXT`.

Reads differently:
- The brief's tail names what it counts (PEMEL17-14, PTWF-3b). The reds of every slot's last run and the intent results' reds are `2 red in the last run: python -m flowguard show --last`, naming the runs once a vitest package's holds some (`1 red in the last run of web/`, `3 red in the last runs of check --static and web/`); a failed test is counted apart and never called red, `1 test failed when last run and has not run since: tests/test_a.py::test_x` (with more, `3 tests failed ... tests/test_a.py::test_x and 2 more: python -m flowguard show --last`), the most recent named. 5.0.1 said `N still red: python -m flowguard show --last` for both. A failed test stays counted until a run of it passes or a complete collection of its file no longer has it, as before. The one last run a 5.0.1 cache keeps is read as its slot: a pytest, `check` or `check --static` run as `repo` (printed as 5.0 printed it, with no version), and a vitest run, which named no package, as `vitest` until the next vitest run of any package replaces it. The cache is disposable; FlowGuard 5.0.x reads only the `repo` slot of a 5.1 cache.

- A change that adds files to `[tool.flowguard] exclude` takes their agreements off the map, and each `same`, `together` and `writers` agreement their baseline versions held is now a `loosened` line, in pytest and `check --static` (PEMEL17-3, PEMEL23-2b): `loosened: same RATE removed from app/b.py:rate (its file is now excluded by [tool.flowguard] exclude) -> name it in your report; loosening an agreement is the owner's decision`. On 5.0.1 an exclude added together with an edit that broke the `same` copy gave `0 red` and no line, while deleting the comment gave the loosened line. A Python file's agreements are read from its baseline facts; a JS/TS file's from its `//` comment lines as text, without its grammar, so its `same` is named by its line (`same RATE removed from web/b.ts:2`). An exclude the baseline already had, or one that takes no file of the baseline out of the map, loosens nothing. pytest now runs the map checks when pyproject.toml changes, as it does for a changed mapped file. A baseline pyproject.toml that is no UTF-8 text or no TOML, such as a committed conflict marker or Latin-1 bytes that pytest itself refuses, leaves unknown which files the change takes out of the map, and a task that repairs it gets one line in the decoder's or parser's words, `not compared: the files this change takes out of the map (pyproject.toml at the baseline a1ca773 does not parse: Invalid statement) -> not a failure`, whose detail in `show --last` keeps the place (`(at line 4, column 1)`); every other map check runs, and pytest's summary and exit are as without FlowGuard (R85).
- The error of a reader whose extra is not installed gives its step after ` -> `, with the alternative for a file that is no source of that language: `web/a.ts: typescript reader unavailable: missing tree-sitter -> pip install "flowguard[languages] @ git+https://github.com/liuyingxuvka/FlowGuard.git", or list it in [tool.flowguard] exclude` (5.0.1: `...: missing tree-sitter; install the optional dependencies with pip install "..."`). `check --static` still exits 2 with it.
- Each name a Python tuple or list assignment writes is a write of its own, in `together`, `writers`, the value gate, `impact` and `show` (PEMEL17-4): `self.task_id, self.operation = "id", "parse"`, nested targets (`self.a, (self.b, rest) = ...`), a starred element (`self.head, *self.tail = items`, which writes no value) and the target of a `for` or `with ... as` (no value). An element takes the value at its place only when the right side is a tuple or list of the same length without a starred item; otherwise it writes no value, as a call's result does. A project whose code already wrote a field this way outside its writers, or without its partner, sees those writes as `before` (`check --all`, and in a run whose change touches the function); a change that adds one is red. The map rebuilds once with the new reader. A name a loop or `with` target binds no longer resolves to the module it named before (after `from os import path`, `path.exists()` in the body of `for path in paths:` is no call of `os.path.exists`), as an assignment already did.
- A run that has waited 5 s for another FlowGuard run's write to the cache says so once on stderr, `flowguard: waiting for .flowguard/cache/map.sqlite (another FlowGuard run is writing it; 5 s so far, at most 30 s)`; 5.0.1 waited without a word. A wait that runs out still stops with sqlite's error and its text (PTWF-2). vitest shows a successful preparation's stderr nowhere, so a vitest run says its preparation's wait in its first line instead: `FlowGuard 5.1 (since 9e14575): 0 red; waited 9 s for .flowguard/cache/map.sqlite (another FlowGuard run was writing it); 9.4 s`. The preparation keeps its waits in the plan by its package, so of two packages' runs of one change only the one that waited says so. The generated `flowguard.vitest.mjs` is unchanged: a wired project needs no new `init`.

- Same-name copies that take different parameters are named as such (PTWF-4a): an input one copy takes that another cannot be given (in Python a parameter that copy lacks, or a required one the input leaves out, by the names the comparison gives; in TS/JS another parameter name at a position the input fills, where the copies answer differently) is not run on that copy, and the copies' red is `red: same PROJECT_SCOPE: scope.py:can_view(user, project) and scope.py:visible_projects(user, projects) take different parameters -> check whether these are copies of one decision, then correct the code or the marks`, in pytest, `check` and vitest; where every copy took these parameters at the task start it is `before: same PROJECT_SCOPE disagreed at task start: scope.py:can_view(user, project) and ...`. 5.0.1 said `scope.py:visible_projects returns raises {'type': 'TypeError', 'message': "visible_projects() got an unexpected keyword argument 'project'"} -> decide which copy is right, then make the other agree` in pytest, `visibleProjects returns raises TypeError: projects.filter is not a function` in vitest, and `anchor signature or units changed; no common declared input/output role -> declare the same inputs and outputs on every copy` in `check`: the step to make one agree with the other is wrong for a boolean check beside a list projection. The red is the same red as before, worded by what is known; TS/JS copies whose answers agree give no such line.
- The not compared line of the block names a function by its own name, not by the agreement it is marked with: `not compared: 2 functions: can_view (scope.py:2) and visible_projects (scope.py:6) (no baseline source)`, where 5.0.1 printed `PROJECT_SCOPE (scope.py:2) and PROJECT_SCOPE (scope.py:6)` (PTWF-4a), and `not compared: standing (policy.py:2) (...)` for one function. `show --last` keeps each line's own text and reasons.
- Copies whose flowguard comments themselves show other parameters (a TS/JS function's parameter names; in Python a parameter annotated with a value type, `days: int`, or other annotated return types) are that same one red in `check --static` too, now with the return type each copy declares: `red: same PROJECT_SCOPE: scope.ts:canView(user, project): boolean and scope.ts:visibleProjects(user, projects): Project[] take different parameters -> check whether these are copies of one decision, then correct the code or the marks` (U5-PTWF-4a, Planning Tool's own case: its red came from `check --static`). It is the group's only red in `check --static`, pytest, `check` and vitest. 5.0.1 printed one line per comment, `red: comment scope.ts:4: same anchor PROJECT_SCOPE has conflicting roles, units or signature -> correct this flowguard comment`, which named no function, parameter or difference, and a vitest run printed it twice beside the copies' own red. The second comment's line offered `write # flowguard: same PROJECT_SCOPE(user=<its parameter>, project=<its parameter>) on this copy`: a Python comment, which in a .ts file FlowGuard does not read and the TypeScript build refuses, and which the TS reader refuses written with `//` (`same needs one NAME: // flowguard: same NAME`). A JS/TS comment names no parameters and FlowGuard gives JS/TS copies each input by position, so no line offers a mapping there: `show --last` says so, and for a Python copy keeps the mapping it can write (`parameters correspond only by name: write # flowguard: same PROJECT_SCOPE(user=<its parameter>, project=<its parameter>) above scope.py:visible_projects if it is a copy of scope.py:can_view`).
- Comments of one name that declare other roles, units or types (the same parameters) stay red at each comment, and each line names what differs and where: `red: comment policy.py:1: same anchor DAYS has conflicting return types (bool at policy.py:first, int at policy.py:second) -> correct this flowguard comment`, where 5.0.1 said `has conflicting roles, units or signature`; `check` no longer adds `declare the same inputs and outputs on every copy` as a third red of that group. Two references of one name give the step in the file's own comment syntax, `keep one reference; mark the copies // flowguard: same NAME` in TS/JS, where 5.0.1 wrote `#` in every file.

- A filtered vitest run says on a line of its own that its package's map checks did not report to it (PTWF-3e): `not compared: flowguard.static.test.mjs (map checks did not report to this vitest run) -> not a failure`, before the line that sums up the other items as before. 5.0.1 summed that item up with the others, and among three or more reasons it was folded away: Planning Tool's run of seven frontend test files printed `not compared: 4 items (only JSON data arguments and results are recorded, uses imported or mutable binding axios, or 1 other reason)`, while whether the map checks (every agreement, known entry and ledger entry) ran decides what its `0 red` covers. A run whose static test reported has no such line. Besides red, loosened and known fixed?, the block now has at most eleven lines.
- The completion policy (`skip_policy = "forbid"`, `--flowguard-record-tests`) says `2 selected test(s) never ran (...)`, the tests the first line counts (5.0.1: `collected`, for the same selected tests).

- A copies finding says what was found, where the copies differ and who decides (PTW-4.252-2, PEMEL17-20, PEMEL23-15a, R101). Its impact line's step, in place of `fix it, or say why in your report`, and its before line's detail in `show --last` are `they resemble (structural similarity 0.87); keeping one implementation or marking each copy same DISPLAY_ANCESTRY makes them agree; whether they must stay separate is the owner's decision; if they must: python -m flowguard known add copies:display_ancestry --act ignore --why TEXT`, the entry that also takes the finding out of the brief's count. A before line says `before: copies _literal at model_source.py:_literal differed from its same-named copies at task start` (5.0.1: `was broken at task start`). A change that adds every copy of a finding of two files gets one impact line naming both, `impact: copies display_ancestry: app/psp.py:display_ancestry and web/psp.py:display_ancestry differ -> ...`, where 5.0.1 printed one line per copy, each `has another body than the same-named display_ancestry in web/psp.py`; a member's own impact line names the copies its body differs from, `app/report_c.py:_section and app/report_a.py:_section, app/report_b.py:_section differ`. The first line counts `1 impact` for such a pair; an ignore entry still counts each copy (`ignored: 2`). `show --last` lists under the line each copy's place, signature, structural similarity to the first copy and the functions that call it through a call the map resolved, then where each copy's body first differs from the first one's (`first difference: app/psp.py:5 break | web/psp.py:5 raise ValueError("cycle")`): difflib over at most 400 lines of each, CRLF and CR read as LF and runs of white space folded, each side cut to 60 characters. That locates the difference; what each copy answers stays with the tests. A reference's look-alike says the same in its own words: `they resemble the reference accept (structural similarity 1.00); calling accept or marking each copy same ACCEPT makes them agree; ...` (5.0.1's step, printed nowhere: `choose one for each copy: call accept; ...`), an exact copy `they answer as the reference half on 11 representative values (not a proof); ...` where its impact line said `fix it, or say why in your report`, and their before lines `was a diverged copy of the reference at task start` or `was a copy of the reference at task start`.
- A block line whose subject, places and step alone leave its text no room within 200 characters keeps its words: a copies line's step is longer than that by itself, and its text would have given way to `orders.py:preview_accept i...e orders.py:accept`, still too long and unreadable. A line that can be brought within 200 characters gives way as before.

- The impact line of a function that now writes a field of a Python class counts the functions that read that field, as `show Class.field` lists them, and says what it leaves out (PYREAD18-1, PEMEL23-5a, R101): `impact: Settings.__post_init__ now writes Settings.appearance; 0 other writers, 5 readers (untyped reads not counted)`, where 5.0.1 said `0 readers of Settings` for every Python class, having counted only Prisma queries and SQL reads. Counts change in every Python project; a database model's count keeps its words (`2 readers of Entry`). `show --last` lists the first ten readers in the line's detail and counts the rest (`3 more readers of Entry: python -m flowguard show Entry.value --full lists them`).

- Writes that moved into a function the changed one calls are one impact line (PTWF-V125, PEMEL17-18): `impact: set_default's writes of Prefs.model moved to _apply, which it calls (model.py:7); 1 other writer, 1 reader (untyped reads not counted)`, where 5.0.1 gave two, `_apply now writes Prefs.model; ...` and `set_default no longer writes Prefs.model; 2 other writers, ...`, without saying that one calls the other. Only a call the map resolves links them (an import, a lexical binding, the Python store's links; never a name alone), and the line names the helper's other resolved callers (`; other callers of reactivateOrCreateMember: other`); the helper's own line is left out when every field it newly writes is one the caller wrote at the task start (Planning Tool's `reactivateOrCreateMember now writes ProjectMember.active, ProjectMember.projectId, ProjectMember.userId`), and `show --last` keeps it with the call's place, `assignProjectManager calls reactivateOrCreateMember at src/members.ts:7`. So the first line counts one impact where 5.0.1 counted two. A call the map does not resolve (a helper reached through a parameter, `deps.reactivateOrCreateMember(tx, ...)`) keeps the two lines. So does a call that does not run on every path of the function (PEMEL17-18 asked to keep the writer lines when the mutation moved across a condition): `if source == "library": _apply_default_model(...)` gives `_apply_default_model now writes ...` and `set_default_model no longer writes ...` as in 5.0.1. In Python the call must be a statement of the function's body or of a `with` block in it, not under an if/elif/else, for, while, try/except/finally, match, assert, a conditional expression, the second operand of and/or, a comprehension, a lambda or a nested def, and after no statement that can return (a guard that raises leaves it on every path); in JS/TS the same, with switch, ternaries, `&&`/`||`/`??`, an optional call (`svc?.reactivate()`) and a named inner function, and a call in an anonymous callback (`prisma.$transaction(async (tx) => ...)`) counts only where the write it replaces was in as many callbacks at the task start, so Planning Tool's call in its transaction callback is still one line and one in a new `forEach` callback is not. A call the current text does not spell with the helper's name (a Python import alias) keeps the two lines too. In the block the line keeps what moved where (PTWF-V125, PEMEL17-18, 5.1 review): its 200-character cut had removed the middle, `set_default_model's wri...model, which it calls (model_preferences.py:10); other callers of _ap...yped reads not counted)`. Now `F's writes of FIELDS moved to G, which it calls (place)` stays whole; the other callers and the writer and reader counts give way first, then the fields are counted, and the line runs past 200 characters rather than cut that clause: `impact: assignProjectManager's writes of 2 ProjectMember fields moved to reactivateOrCreateMember, which it calls (member-helpers.ts:1); ... -> check them for this change only (python -m flowguard show ProjectMember.projectId)`. `show --last` keeps every name.
- A function whose update of a field became a delete says so (PTWF-4255): `impact: remove no longer writes Assignment.status; now deletes Assignment (assignments.ts:8); ...`, for a delete of that field's model the function did not have at the task start.
- A new read of a model no code creates says what was searched (PTWF-V116a, PTWF-G61, R101): `impact: uncreated ProjectRequest: registry2.ts:referenceCount reads ProjectRequest; no creator found; ProjectRequest was already read so at task start (src/registry.ts:countRequests) -> find where these rows come from (seeds, migrations, another system) and say so in your report; python -m flowguard known add uncreated:ProjectRequest --act leave --why TEXT records a creator outside the repository`. 5.0.1 said `whose rows no code creates -> fix it, or say why in your report`, while only the files FlowGuard reads had been searched, and its step could lead to a creation path no one had asked for; the owner of Planning Tool keeps that table and its count on purpose. The new reader's line stays impact, and a task-start reader the change touches stays a before line.

- A `changed` line of a function whose result is a dict, or a list of dicts as long as before, names the keys that changed (PTW-G54-2, R101): `changed: parseSnapshotConfig (snapshot.ts:1): (text='{"baseline":"b1"...rsion":2,"version":3}') now adds demandPeriodConvention='legacy-half-open' (3 other keys equal); 3/3 inputs differ -> if you meant it, say so`, with `removes KEY` and `changes KEY from 1 to 2`, nested keys as paths (`summary.total`, `rows[1].b`, `[0].value` of a list), at most three keys named and the others counted (`2 more keys differ, 1 other key equal`). 5.0.1 printed both results as whole JSON, and the block's 200-character cut left them the same text on Planning Tool's line: `was {"baseline": "b1...2, "version": 3}, now {"baseline": "b1...2, "version": 3}`. When the line needs cutting, its input gives way first and the keys after it. Keys are compared by their JSON, as the whole values are: key order is no difference, NaN equals NaN, and 1, 1.0 and True differ. Any other result keeps its `was X, now Y`.
- `show --last` prints each differing input of a `changed` line once (PTW-G58): the line's own input on the line, and every other input in its detail. 5.0.1 printed the line's input again as the detail's first row, so Planning Tool's `isEmploymentActive(person, day)` printed each person, with its name, code and six rows, N + 1 times for N inputs that differ. A keyed line's detail adds the full values: `in full: was {...}, now {...}` under the line for its own input, and `(text='{"version":4}') now adds demandPeriodConvention='legacy-half-open' (3 other keys equal); in full: was {...}, now {...}` for each other input.

- A top-level command of FlowGuard 0.70 to 1.4 is refused as a command 5.0 removed is: one line on stderr with the release that removed it and the command that does its job now, exit 2 (PEMEL17-22). `python -m flowguard read --find "bounded validation"`, which a skill bundled for 0.7x still told agents to run, gives `flowguard: read was removed in 1.0 -> python -m flowguard show "words"`, where 5.0.1 printed argparse's usage and `invalid choice: 'read'`; `change`, `map`, `target` (1.0), `template`, `release`, `decide` and `draft` (2.0) likewise. `status` and `where` exited 0 with `this is a FlowGuard 0.7x command; here run python -m flowguard new-task`, which sent both to a command that moves the baseline; they exit 2 now too, `status` naming the brief (`python -m flowguard`) and `where` `show "words"`. A script or hook that still runs `python -m flowguard status` and relied on its exit 0 fails; `python -m flowguard` prints the brief.
- `known add` of a finding none of whose places is a site names a table of a `.sql` file among the sites to give: `name one with --site path:symbol (a function, constant or Model.field of a file, or a table of a .sql file)` (PTW-G68-2). A `columns:` finding's place is a migrations folder or a SQL file, and 5.0.1 named only a function, constant or Model.field of that file.

- The steps of two rules that conflict say what is known and who decides, and both routes of storing his decision (R101, R105): `rules THREE and FOUR conflict; only the owner can choose which holds` (5.0.1: `choose one by asking the owner`), then `when the owner decides, first store his typed words with python -m flowguard req add - --id R<n>, or his pick among options you offered with python -m flowguard req add REPLY --id R<n> --offer FILE --picked "TEXT", then update rule tests/intent/days.py:9`, as rule 7 of the rules block names them; 5.0.1 said `first store the exact owner words with python -m flowguard req add`, the route that would store an answer to options the agent offered as a plain request, which closes its id to the choice.

Corrections of 5.0 bugs:
- Another vitest package's pass no longer covers a package's red (PTWF-3b). Planning Tool checks `web/` and `api/` apart; 5.0.1 kept one last run, which the next run replaced, so after a red in `web/` and a pass in `api/` the brief said nothing and `show --last` printed `FlowGuard last run: vitest at 12:47:13` with `0 red`. The same runs now give `1 red in the last run of web/: python -m flowguard show --last` and both packages' runs.
- A vitest run killed before its report no longer leaves the static test's lines as a finished check (PTW-V2-2). The static test inside vitest (`check --static` with `FLOWGUARD_LINES`) saved its lines as the last run, which the report then replaced; under `timeout 4` with an 8-second test (exit 124) `show --last` printed `FlowGuard last run: check --static at 08:21:55` and `0 red`, and the earlier vitest run's red was gone. It now saves nothing of its own: the package's slot keeps its earlier run, under the line that says the later run did not report.
- The brief counted failed tests kept from earlier runs as red, with no route to them (PEMEL17-14). After `pytest` (test_a failed), `pytest tests/test_b.py`, a commit and `new-task`, 5.0.1 said `1 still red: python -m flowguard show --last`, while `show --last` printed the last run alone, `0 red`; PEMEL Studio's handoff said `6 still red` for six failures outside its focused run. It now says `1 test failed when last run and has not run since: tests/test_a.py::test_x`, and `show --last` lists the test. `check`'s own red for a pytest that failed with no finding to say why (`red: pytest: exit 2 -> read .flowguard/cache/check-output.txt ...`) was in no count of the brief; it is counted with its run's reds.

- A file `[tool.flowguard] exclude` lists is out of every comparison (PEMEL17-1, PEMEL23-2a). The map left it out, but the task's change set (`MapHandle._git_changed`, which feeds `impact` and the map checks) took every path Git named, so an excluded file that differed from the task start was read there with its reader: PEMEL Studio's Qt Linguist catalogues (`translations/*.ts`, XML) went to the TypeScript reader, and on a Python-only install `check --static` exited 2 with `translations/app.ts: typescript reader unavailable: missing tree-sitter` and pytest ended in a traceback with no `1 passed` line; three agents patched `_git_changed` in a local plugin for every run. One decision in the map's store, `store.mapped`, now picks the files the map reads, the paths that changed against the task baseline, the old paths of renames, and the files the session's source index reads; the same pytest and `check --static` give `1 passed` and `0 red`, exit 0. Untracked bytecode (`__pycache__/*.pyc` in a project without a .gitignore) and a source inside an interpreter environment are no change either; a file the change deletes still is.
- A reader that cannot run no longer replaces pytest's own outcome (PEMEL17-2, R85). When the map checks stop on such an error (or on Git or the cache), the session gives one red line with the error's text and step after pytest's summary, `red: map checks: web/a.ts: typescript reader unavailable: missing tree-sitter -> pip install ..., or list it in [tool.flowguard] exclude`, keeps its other lines, records the run for `show --last` (which adds `the map checks of this change did not run`) and the JUnit `flowguard::session` case, and exits 1. 5.0.1 raised a traceback at session finish in place of the `1 passed` line, and with a Python file changed as well it stopped pytest when its tests were collected (`INTERNALERROR`, `no tests ran`, exit 3); the tests now run, and `show --last` says that the functions the change edits that no flowguard comment names, and the files that import a constant it changes, were not compared without the map.
- A project source file saved while pytest runs no longer changes a test's outcome (PEMEL23-1a, PEMEL23-1b, R85). The call hook of a changed or `same` function is compiled from its text in its file, read again in each test, and 5.0.1 read whatever the file held at the function's lines by then. When another agent (or a test) saved a shorter file, pytest stopped with `INTERNALERROR` (`OSError: lineno is out of bounds` from `inspect.findsource`, or an `IndentationError` from the parse), naming neither the file nor the function, exited 3 and still printed `0 red`. When lines were inserted above the function, `inspect.findsource` read the def above them, and FlowGuard installed a call stub with that function's parameters as the hooked function's code: a later test failed only under FlowGuard (`TypeError: area() got an unexpected keyword argument 'w'`, `area.__code__.co_varnames == ('a', 'b', 'c')`), with `0 red` and no other line. The text now counts as the function's only while its file holds the bytes FlowGuard's import finder loaded (`util.source_hash`, recorded at import, checked before and after the read), and while it starts at the line where the function's code starts (its first decorator's) and defines that function's name. Otherwise the function keeps its own code in that test, and the run says `not compared: area (source of app/mod.py changed on disk after import) -> not a failure` (for a module another loader read, `source of app/mod.py no longer holds area at line 5`), and the run ends as it does without FlowGuard (`3 passed`, exit 0, in PEMEL Studio's shape). An unchanged file is hooked and compared as before, and the probes and mutants `check` compiles from a function's text are refused the same way.
- A `together` partner value spelled `=true`, `=false` or `=null` holds the bool or null a TS/JS, Prisma or SQL write gives, and `=True`, `=False` or `=None` holds it too, whichever language wrote it (PTW-G55-2). The readers read a TS `true`, a SQL `TRUE` and a Python `True` to one value, and 5.0.1 compared its Python spelling with the comment's text, so Planning Tool's `// flowguard: together Employee.name Employee.planningEnabled=true on=create except=src/sync.ts:mirrorCentral(...)` was red for a correct new create: `red: together Employee.name: employee.service.ts:importEmployee writes Employee.name without Employee.planningEnabled=true (creates only)` for `{ name, planningEnabled: true }`, exit 1, and `check --all` listed the existing `createEmployee` as `before`. That create now holds it (`0 red`), a create writing `false` is red, the seed creates that omit the field stay `before` and the mirror under `except=` is not held. Strings and numbers compare by their text as before; a string `'true'` still holds `=true`.
- A Python tuple write no longer reads as no write (PEMEL17-4). 5.0.1 recorded `self.task_id, self.operation = "id", "parse"` as one write of a field named `(self.task_id, self.operation)`, which no agreement names: `show Runner.task_id` listed only the constructor, a tuple that dropped the partner (`self.task_id, self.unrelated = "id", "parse"`) gave `0 red` where `self.task_id = "id"` gave `red: together Runner.task_id: runner.py:Runner.start writes Runner.task_id without Runner.operation`, and `self.state, self.code = "stop", 0` in `Job.stop` gave `0 red` under `# flowguard: writers Job.state Job.start`. Both are now red with those lines, and `show Runner.task_id` lists `writes Runner.task_id runner.py:8 Runner.start (assign)`.
- Two FlowGuard runs on one repository both finish (PTWF-2, R85). Planning Tool ran the checks of its two packages at the same time and one ended with no result. A map build held the cache's write lock (`BEGIN IMMEDIATE`) from its first file read to its commit, the parse included, and every connection took that lock just to open the cache, so the second run's `check --static` stopped after 30 s with `SQLite cache could not be opened: database is locked; no cache result was accepted` (exit 2); a reader of the cache waited only sqlite's 5 s while another run committed (`task baseline could not be read: database is locked`, and `show --last` ended in a traceback). A build now reads the files and plans against the map in one read transaction, parses the files that changed with no transaction open, and takes the write lock only to plan once more against the map as it then is and write what still differs: a file another run wrote with the same bytes meanwhile is left as it is, a file saved again since the parse is parsed again under the lock, so the map is what one build at the moment of its write gives, and a map that already holds the files takes no write lock. Opening the cache takes the lock only to add a missing table, index, column or format row, and every connection, reader or writer, waits up to 30 s. With a parse of 35 s, two parallel `check --static` runs of `web/` and `api/` each print both red lines and exit 1 after 36 s; 5.0.1 gave one of them the lock error after 30 s.

- A recorded call is replayed at the task start only as a call of the same input (PTWF-4c). Planning Tool's G80 inserted a required parameter first, `businessPersonLabel(record)` became `businessPersonLabel(kind, record)` and `createBusinessDraft(record?)` became `(kind, record?)`: the replay gave the old functions the new calls' arguments by position, and beside `0 red` the block printed `changed` for all 11 inputs (7 and 4), `changed: businessPersonLabel (labels.ts:1): (kind='person', record={"dept": "HR", "name": "Ann"}) was 'undefined [directory unavailable]', now 'Ann [HR]'` and `changed: createBusinessDraft ... was {"title": ""}, now {"title": "X"}`; in Python `changed: person_label ... was raises {'type': 'TypeError', 'message': 'person_label() takes 1 positional argument but 2 were given'}`. In TS/JS a call now fits the task-start version when every position it fills has the same parameter name in both; in Python each value goes to the parameter of its name, a parameter the task-start version lacks is left out where the call left it at its constant default, and every required parameter of that version needs a value. Otherwise the old version is not run, and the line is `not compared: 2 functions: businessPersonLabel (labels.ts:1) and createBusinessDraft (labels.ts:5) (parameters differ from the baseline) -> not a failure`, with `parameters differ from the baseline (was businessPersonLabel(record), now businessPersonLabel(kind, record))` in `show --last`. A trailing parameter added keeps a call compared: TS `over(x)` that became `over(x, strict?)` as before, and now Python `over(x)` that became `over(x, strict=False)`, called `over(3)`, where 5.0.1 printed `changed: over ... was raises {'type': 'TypeError', 'message': 'over() takes 1 positional argument but 2 were given'}, now True` and 5.1 prints `changed: over (policy.py:4): (x=3, strict=False) was False, now True`. A function whose parameters stay the same keeps its `changed` lines.

- The first line of a pytest session that ended before its selected tests had all run says so (PEMEL23-1c): `FlowGuard 5.1 (since 3e4ecdc): 0 red; run ended early (exit 3): 2 of 3 selected tests ran, the rest not checked; 0.1 s`, after an internal error, an interrupt or a collection error (exit 2), `-x`, `--maxfail` or `pytest.exit`, with the exit the shell sees; `show --last` keeps that line under `pytest: exit 3, 0 failed`. 5.0.1 printed a plain `FlowGuard 5.0 (since 3e4ecdc): 0 red; 0.1 s`: PEMEL Studio's run that pytest stopped with INTERNALERROR after 190 of 2544 tests read as if every agreement had been checked. A session that finished, and one that only collects or sets up (`--collect-only`, `--setup-only`, `--setup-plan`), has no note.

- `known add` of a copies finding records every copy's site (PEMEL23-15a). It read the sites from the last run's lines, and a run whose change touched one copy has that copy's line alone, so `known add copies:_literal` after `check --static` wrote `sites = ["src/app/model_source.py:_literal"]` for a finding of two copies. Each copies line now holds the places of its finding's other copies too, and the same command writes `sites = ["src/app/model_source.py:_literal", "packaging/build_runtime.py:_literal"]`.
- The brief counts in the number it needs (PEMEL23-15b): `1 open structure issue` and `(1 other field has multiple writers and no writer agreement)`, where 5.0.1 printed `1 open structure issues` and `1 other fields have`.
- A copies member's line names only the copies whose body differs from its own: of three copies two of which have one body, 5.0.1 said each of those two had another body than the other.

- A field still written through data whose fields are not visible is no longer said to be no longer written (PTWF-FIa). Planning Tool changed `phases.map((phase) => ({ startDate: phase.startDate, endDate: phase.endDate, share: phase.share, absenceRecordId: id }))` to `({ ...phase, absenceRecordId: id })`, and 5.0.1 said `update no longer writes AbsencePhase.endDate, AbsencePhase.share, AbsencePhase.startDate`, while `show AbsencePhase.endDate` listed that write as `AbsencePhase.?` (`phase is a parameter`). The line now says `update writes AbsencePhase.? where it wrote endDate, share, startDate (fields not visible: phase is a parameter)`; a field really dropped from the literal is still `no longer writes AbsencePhase.endDate`.

- pytest runs the map checks for a change to any file the map lists, as `check --static` does (PEMEL23-11, PEMEL23-12). 5.0.1 ran them in pytest only when a source file, `rules.toml` or `known.toml` changed: a change that edited only `src/app/resources/model.json`, which a Markdown text's marker names, printed `0 red` where `check --static` gave `impact: generated.md:8 describes src/app/resources/model.json, which this change edits -> ...`, and a change of a Markdown file alone that wrote a marker whose site names nothing was `0 red` in pytest and red in `check --static`. A file the map leaves out (its ignore patterns and `[tool.flowguard] exclude`) runs nothing still.
- Markers stacked above one text all describe it (PEMEL23-11): a list item under `<!-- flowguard: about src/app/build_model_source.py:support_documents -->` and `<!-- flowguard: about docs/manual.txt -->`. 5.0.1 ended each marker's text at the next marker, so each marker of a stack but the last described nothing: an edit of `support_documents` named `generated.md:3`, and rewriting the item it stands above did not answer it.

- `show R3` of a request stored as UTF-16 with its byte order mark (Windows PowerShell 5.1's `>`) prints its words (R105). Its quote held, as the checks read UTF-16 by its byte order mark, but 5.0.1's `show` decoded it as UTF-8 and stopped with `flowguard: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte`. `show` now reads a request, a choice's reply and its options by that one route; bytes that are neither UTF-8 nor UTF-16 stop it with the decoder's text and the file's name, where 5.0.1 named no file.
- An intent rule's `owner R1` source with `quote=` reads the stored request as every other source does (R105): a request stored as UTF-16 with its byte order mark holds the quote, where 5.0.1 read it as UTF-8 and the rule's test failed with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte`, while `R1 "words"` held the same words. Bytes that are no UTF-8 or UTF-16 text stop it with the decoder's error, as they stop the other forms.

Known limits:
- A pytest or `check` run killed by a signal before its session finishes (an outer timeout's SIGTERM, a SIGKILL) notes no start: `show --last` shows the `repo` slot's run before it, as 5.0.1 did. `check`'s slot does not carry pytest's outcome line; its block names a failed test or pytest's exit as a red line itself. A vitest run's start is noted in the slot of the folder of its vitest config and its report is kept in the slot of the vite root, which differ when the config sets another `root`: that note then stays. Of two runs of one package at once, the first report replaces the second's note. Whether the last pytest run selected a failed test is read from the start its reading carries: a test that run selected but never reached (`-x`, an interrupt) reads as not selected.

- A JS/TS file a change newly excludes is read for its agreements as text: a `// flowguard:` comment after code on its line, or a line of a template literal that starts with `//`, is read as its grammar would not read it. The pytest plugin's choice of which Python calls to record still matches `exclude` with `fnmatch`, where `*` also crosses folders, while the map's `*` stays within one folder.
- In a vitest run the map checks report through `flowguard.static.test.mjs`, which fails with `check --static`'s exit 2 and its text; the vitest preparation step builds the map too, and a reader whose extra is not installed there still stops vitest before its tests (`FlowGuard vitest preparation exit 1`).
- Which option the owner's reply means (`B`, `the second one`) is the agent's statement: FlowGuard checks that each picked text occurs exactly once in the stored options and shows it beside his reply, but cannot check that the reply names that option. It does not know where one option ends either: a picked text may be a part of an option, as long as it occurs once.
- A module that FlowGuard's import finder did not load (another loader, `exec`) has no recorded bytes: a save that keeps a function's first line and name, but changes its body or parameters below them, is read as that function's text. pytest's project modules and `check`'s are loaded by the finder.
- An augmented assignment (`self.count += 1`) and a JS/TS destructuring assignment (`[this.a, this.b] = [1, 2]`, `({ a: this.a } = row)`) are still no write. In a `# flowguard: states Class.field = a | b` comment a bare word stays a string, `true` and `null` too: a set of bools or None is written `True | False` or `None` there.
- Builds of two runs that overlap both parse the files that changed, and the second writes nothing; a build that writes reads the project's files twice, once before its parse and once under the lock. The cache keeps SQLite's rollback journal (no WAL, which network filesystems do not support): a reader still waits while another run commits, or while a build writes more than SQLite's page cache holds, up to 30 s.
- A parameter that was only renamed counts as another one: its calls are not compared at the task start (TS/JS by position, Python by name), and the reason says that the parameters differ. A Python default that is not a constant (`opts=[]`, `limit=LIMIT`) is not read, so a call that left a parameter the task-start version lacks at such a default is not compared either. Python copies are given an input with every default of the copy whose call recorded it: beside `f(a)`, a copy `g(a, strict=False)` that a test called takes different parameters. A same-name red that says the copies take different parameters names at most three of them, with their parameters as written (annotations left out), and its red or before follows whether every copy took these parameters at the task start, in Python, and how the copies' answers compared there, in TS/JS.
- The comments' red of copies that take different parameters is red in every run, also where the copies took these parameters at the task start, as every flowguard comment problem is (so in 5.0.1); only where a comparison that runs the copies finds them alone (unannotated Python, a TS/JS input that fills a position whose names differ while the names agree as a set) is an old one `before`. A vitest run whose static test did not report names the copies by its own comparison, without the `show --last` detail. A JS/TS return type is named, never compared.

- The note of a pytest session that ended early counts the selected ordinary tests that gave an outcome, as the completion policy does: a test whose call an interrupt cut short counts as not run, and neither the intent items of `tests/intent/` nor the sentinel test are counted. `check` gives no note (its block names a failed test or pytest's own exit as a red line), and neither does a vitest run.

- A copies finding's first difference compares source lines, not behaviour: two bodies that differ only in their parameter names differ at their first line (`def _section(title, rows): | def _section(heading, items):`), and one past the 400 lines compared is `none in the first 400 lines of each with white space folded`. Its callers are the calls the map resolved, as `show NAME` lists them: a test that calls a copy through a path the map does not resolve is not named. Of a finding of several functions shared by the same files, the step names each function's `same NAME`. A `known add copies:NAME --act leave` entry turns the before lines into known lines and keeps the finding in the brief's count, as 5.0 documented for every family; whether a leave entry should also leave that count is the owner's decision, so the copies step offers `--act ignore`.

- A Python read through a name nothing types is not counted and not listed (`untyped reads not counted`): a name bound to a constructor's result (`p = Pane(); p.title`, whose writes are not typed either), an unannotated parameter, a comprehension's target, an attribute whose class declares no type for it, and an augmented assignment's read (`self.count += 1`). A read through `self` in a subclass's method counts for the subclass, as its writes do, and a call through `self` of a method a base class holds reads an attribute of that name (`(call)`). Two classes of one name in different modules share their fields' reads, as they share their writes. `replace(x, **changes)` reads every field its named keywords leave.

- A moved-writes line links a function only to the functions it calls directly; each field goes to the first such callee by id. Whether a call runs on every path is read from the current text alone. A JS/TS callback is counted, not judged: one as deep as the old write's counts as run, whatever the function it is passed to does with it. A call under the same condition or after the same early return as the write it replaced (`if source: prefs.model = m` that became `if source: _apply(prefs, m)`) keeps the two lines, for the task start's text is not compared. Its detail gives a JS/TS call's line, and names a Python call without one: the map keeps the function a Python call is in, not its line. A field of a model the function still writes with data whose fields are not visible is said as `writes Model.?`, never as moved. The task-start places of an `uncreated` line are printed as their whole repository paths, and the line, whose step is longer than 200 characters by itself, keeps its words, as a copies line does.

- A `changed` line reads a result key by key only where both results are dicts, or lists of dicts of one length: a list that grew or shrank, a list of other values and a scalar keep their whole values (`was [...], now [...]`), as does a nested pair of that kind (`changes rows from [...] to [...]`). Two results that differ only where FlowGuard spells them alike (vitest's `undefined` and `null`, both `None`) keep their whole values too. `show --last` still prints each differing input whole: it does not leave out the fields of an argument the function does not read (PTW-G58's `person.name`, `person.rows`).

- A marker may name a file the map leaves out (under `build/`, `dist/` or `node_modules/`, or matched by `[tool.flowguard] exclude`), but a change to it is no change of the task and names no text. The map records no file a function reads (`files("app").joinpath("resources/model.json")`, `open(...)`): only a marker ties a data file to the function that reads it, and no `changed` line follows from a data file (PEMEL23-12). Agents in one working tree share one baseline and one change set, and no option scopes a run to some paths (PEMEL23-4a). No agreement says that one function calls another, and a change that removes a route's call to its owner names nothing (PTWF-4b).
- A vitest run's first line says the waits of its preparation only. Its report writes the run's last lines after the block is made: a wait for that write is said on stderr, which vitest shows after the teardown's report and not after the report of FlowGuard's own test case `FlowGuard execution side`. A vitest config whose `root` is another folder than the config's own names another package slot in its report than in its preparation, and its first line says no wait.

## v5.0.1 - 2026-11-17 - A folder of the task start is no file there

A correction within the 5.0 contract. Saved inputs keep their meaning and bytes; nothing needs migrating.

- Where FlowGuard asked for a file that is a folder (or a submodule) in the task-start commit, it read the folder's tree as the file's bytes and stopped the tests before they ran, with `git cat-file failed in ...: fatal: git cat-file <tree id>: bad file`. Two ways led there: vitest's plan probing a relative import of a folder at its exact path (`import { LIMIT } from "./settings"` with `src/settings/index.ts`; Planning Tool's frontend tests met it with 5.0.0 through `frontend/src/components/employee-utilization`), and a file in the work tree where the task start had a folder of that name, also in `check --static`. A folder or a submodule there is now no file at the task start, as for a path Git does not list: the probe goes on to the index file, read as committed, an existing file at the exact path that is no script still ends the probe, and a file where a folder was is new. A tree or blob Git cannot read still stops the run with Git's message. 4.3 read it the same way as 5.0.0.
- Verification on the release commit: the full suite passed with Python 3.11, 3.12 and 3.13 from virtual environments outside the repository, and the complete CI ran on this commit (Linux Python 3.11 and 3.13, Windows Python 3.12).

## v5.0.0 - 2026-11-17 - Show what the code holds, tie documents to it, remove what 4.3 announced

A major release. FlowGuard 4.3 announced commands, options, intent API names, comment spellings, two ledger sections and its own hidden leads for removal in 5.0. They are removed, and each use is refused with its replacement instead of being read with its old meaning: a removed command or option exits 2 with one line on stderr, and a removed intent name, 4.2 comment spelling or ledger section is a red line whose step says what to write instead. These are incompatible changes to the supported CLI, the intent API and two saved input forms (the 4.2 comment spellings and the ledger's `[structure]` and `[unverified]` sections), so the version rises to 5.0.0; the deprecation notices that announced them are gone too. The work prepared as 4.4, documents that follow the code, was never tagged or published: as the owner decided (R99), it ships in this release with the removals, so 5.0.0 follows 4.3.0. What 4.3 did not announce keeps its meaning and bytes: 4.3 comments, intent rules, literal rows, sources, flows (nodes, edges, relations), the ledger's handler entries, `rules.toml`, `known.toml` and the owner-word archive, its glossary and adoption records included. One meaning changed: a `known.toml` entry with `act = "ignore"` now also takes its finding out of the brief's count of open structure problems, which 4.3 did not (see Reads differently). Run `init` again for the new rules block and, in an npm project, the new generated tests; see [the 5.0 notes](docs/upgrade-5.0.md) for each migration with a valid and a rejected example. On Planning Tool the 4.4 features passed on small fixtures and then gave wrong or noisy lines on its real code (R97); the corrections are pinned by tests on fixtures shaped like that code. FlowGuard is the agent's tool (R101): a line says what is known and who decides, and the agent chooses when to raise a question.

Removed, each use refused with its replacement:

- The commands `anchor draft`, `model draft`, `try`, `watch` and `compare`, and the options `show --draft`, `show --gaps`, `check --since`, `check --leads` and `req add --kind glossary|adoption`. A use exits 2 before any project file is read or written, with one line on stderr: `flowguard: try was removed in 5.0 -> python -m flowguard new-task, check or show NAME`. `check --since` names `check --base REV`, `check --leads` names `show --last`, `show --draft` and `--gaps` name `show NAME`, and `req add --kind glossary` names `req add FILE --id R<n>`. `req add --kind request`, 4.3's default, is accepted and changes nothing. Glossary and adoption records already stored keep loading, listing and showing.
- The intent API names `precedes` and `guarded_by` (declare the order as a flow's nodes and edges), `transitions`, `Transition` and `flow(..., transitions=)` (5.0 checks no state changes; `states(...)` still checks the values a field is given), `checks` (bind the rule to its scenario test with a flow relation), `distinct`, `structure_rule` with `allow`, and `pytest.mark.rule`. An intent file that imports, reads or calls one is refused before it runs: its `load` line is red at that file and line, in pytest, `check` and the vitest report (`red: load order_rules.py:1: precedes was removed in 5.0 -> declare the order as flow(ID, source=..., nodes=[Node(...), ...], edges=[...]); until then none of its file is checked`), and reading the name from `flowguard.intent` raises `IntentError` with the same text. A test marked `pytest.mark.rule` is a red `marker` line. Without `distinct`, two rules of one `decides=` key that disagree are a conflict unless one `overrides=` the other, two keys on one decision site get the question that ends `(merge the keys)`, and copies meant to differ are recorded with `known add copies:NAME --act ignore` once `check --all` lists them. A flow's finite model is its graph alone, one state per node; a finite invariant over a state field stays unverified.
- The 4.2 comment spellings `sensor NAME`, `owner NAME` above a function, `owner A with=...`, `alone=f(reason)` and `owner A writers=...`, in Python and TS/JS. Each is a red line at its place that binds nothing, and its step is the 4.3 comment that says the same (`red: comment fees.py:6: sensor was removed in 5.0 -> write # flowguard: same FEE`). A 4.2 bare name in `alone=` or `writers=` meant the function of that name in any file, so the step names every such function of the map, another file's as `path:function`. Written as its step says, the agreement loosens nothing; deleting the line, dropping a partner, or adding a writer or an `except=` is a `loosened` line, as for the 4.3 comment. pytest, `check` and `check --static` give the same step.
- The ledger's `[structure]` and `[unverified]` sections. A ledger that still has one gets one red line, in pytest, `check`, `check --static` and `ledger check`, and what the section holds is not read: `red: ledger.toml: [structure] was removed in 5.0 -> delete the section and record each decision in .flowguard/known.toml: python -m flowguard known add NAME --act leave|ignore --why TEXT`; `[unverified]` has no replacement. A `known.toml` entry with `act = "ignore"` takes its finding's lines out of every run and, for a finding the brief counts, the finding out of the brief's count of open structure problems, as a `[structure]` decision did; `leave` keeps it counted. A `declarations:` finding is never in that count: for it `ignore` only removes the line, and `leave` gives a `known` line. `check --all` still fails a grey rule whose source quotes the owner's words, and nothing exempts it.
- FlowGuard's own leads that 4.3 printed only under `show --last`'s `deprecated leads (5.0)`: old values that other decisions or rules still spell, label spellings, similar implementations, the look-alikes an unmarked changed function left behind, the copy discovery listing and `copies at X changed; rule R is unchanged`. The findings those checks also make stay: `copies:` for a diverged copy, `changed-alone:` and `declarations:`.
- The deprecation notices: `deprecated: sensor goes in 5.0 -> write same NAME` on stderr after the block, and `show --last`'s `deprecated features used (5.0)`. What 5.0 removed is a red line or a usage error, and nothing is announced for a later removal. The records FlowGuard keeps for `show --last`, `check --static` and the vitest report lose their `deprecated` and `notices` keys.

New, from the 4.4 work and after it:

- `show NAME`, after the entries and agreements that concern the name (see below), gives what the map read about an exact name. For `Model.field`: each distinct declaration in the Prisma schemas with the files that declare it so, the column type each SQL description ends with after its migrations (a SQLite rebuild, `RENAME COLUMN`, `ALTER COLUMN ... TYPE`), the value sets, each numeric `CHECK` range and the bounds of the zod number schemas given to a key of that name, with the schema object it belongs to (`zod key fteShare in assignmentSchema: 0 <= fteShare <= MAX_FTE_SHARE=1`): the keys of the field's own schema objects come first, a schema object belonging to the model whose name is the longest model name its camel-case words hold (`lendingAssignmentCreateSchema` to LendingAssignment, not Assignment), and the others follow one line that says they are keys of the same name in other schema objects, matched by the name only (`the 8 zod lines below are keys of the same name in other schema objects, matched by the name only`); a field the known model lacks gets `not on the map` instead. `table.column` answers with the Prisma field its `@@map` and `@map` map to it, as `Model.field` does, and an upgrade script's `ALTER TABLE ... ADD` of a table another file creates gives its column line. A test file that reaches a writer says when it lies in a folder a test script of its package runs as a suite that reaches real databases and services, or when the test scope leaves it out (`test backend/tests/integration/lending.routes.test.ts reaches a writer of Assignment.fteShare (a suite that reaches real databases and services: backend/package.json script "test:integration" runs tests/integration)`; vitest's `test.include` and `test.exclude`, pytest's `testpaths`, `python_files` and `norecursedirs`), and so does each `writes` line of a write in such a file. For a bare name: a JS/TS module constant's value (an object of literals too), the declaration of one whose value is a call, cut to its first call, with the zod lines of a schema object's number keys (`const batchAssignSchema = z.object(...) (backend/src/api/schemas/assignment.schemas.ts:21)`), an enum's members in each Prisma schema with that schema's state, a label table's keys and labels with its family's `structure:` line. A Prisma model or table gives a line per schema and SQL description and its count of writes and reads; a function, method or `object.method` its node view (signature, the fields it writes, its callers through resolved calls), the method of an object also when a module function of the file has its name (`show capacityService.sliceDateRangeByMonth`, as a generated region names it); an object literal or class its place and every function-valued member. A name the map does not know gets one `not on the map` line, a misspelt field the model's nearest field, and names that only share a word with the query follow a line that says so, after `--full` when the map knows the name. On Planning Tool, `Assignment.status` is `String` in two schemas and an enum in the third, and `fte_share` is at most 2 in SQL and in six zod schemas and at most 1 in four others, which no document said together.
- The SQL reader reads a `CHECK` that bounds one column by numbers (`col >= 0 AND col <= 2`, `BETWEEN`, either side) in `CREATE TABLE` and `ALTER TABLE ... ADD CONSTRAINT`; one inside a comment is not SQL that runs.
- Generated regions: the lines between `<!-- flowguard: generate KIND ARG -->` and `<!-- flowguard: end -->` in a Markdown file are written from the map by the new `python -m flowguard docs`, for `fields Model`, `values NAME`, `functions path` and `constants path`; none carries a line number. `fields Model` gives a relation field no column (`| demand | Demand? | relation Demand |`), `functions path` names each function and method of the file as a flowguard comment or `show` does (`capacityService.sliceDateRangeByMonth`, never the map's `sliceDateRangeByMonth@490`) with its whole signature as declared, and leaves out what another function holds (closures, callbacks, an object literal's methods). A region holds only what the map knows: prose such as the Purpose column of a hand-written function list stays outside it. A region that lists a file's functions or constants, or a model's fields, is a text that describes that file, each name it lists and that model: `show` names it (`described by docs/FUNCTION_INVENTORY.md:307 (generate functions backend/src/services/central-employee.service.ts)`), and the module view gives such a file no `described by no text` advice. A region out of date is an `impact` line, never red, when the change edits the declaration it is written from or the region or its marker; one this change writes that cannot be generated is red (`red: generate values Nope: no value set of that name -> correct the marker at lists.md:12`). Outside Git it reads the Markdown files the map's own folder walk finds, as the map reads the code there. Planning Tool's function inventory, schema notes and frontend documentation were written by hand: a review on 2026-11-15 that sampled their claims found 17 of the 27 it could compare with the code out of date.
- `<!-- flowguard: about path:symbol -->` (or a file's path alone) above a Markdown text ties it to that code, read as a `known.toml` site is. When a change edits that code and not the text, an `impact` line names the text (`impact: assignments.md:3 describes backend/src/share.ts:totalShare, which this change edits -> reread that text and correct it if it no longer holds`); a change that edits both says nothing. A marker this change writes that names nothing is red, one whose code this change removed is named, and `check --all` lists every such marker. A `known.toml` site may be a Markdown file's path alone (4.3 reads such an entry as invalid). On a `.sql` file a site names a table or `table.column` its statements name, or the Prisma `Model.field` mapped to one (`backend/prisma/azure-sql-setup.sql:Assignment.fteShare`); a site there that names nothing is the entry's or marker's usual input problem (`... names nothing in backend/prisma/constraints.sql: name one table or table.column of that file (the map reads no table statement in it)`). Markers shown in code spans or fenced blocks are text. Markdown is read as UTF-8, or as UTF-16 or UTF-8 when a BOM says so, and `docs` writes it back in that encoding and with its line ends. In that review, 91 of the 120 claims sampled from twelve of Planning Tool's documents were about its code: 40 of them were out of date, 46 held and 5 could not be decided.
- Module contracts (R98): a text about a file or a folder (`path/`) is that module's contract. A change to a function that another module calls, or that calls into another module, names those modules' contracts once each while their text is unchanged, and `show PATH` prints a file's or folder's contracts right after its known entries, each with the site its marker names (`described by docs/FUNCTION_INVENTORY.md:718 (about backend/src/utils/capacity-conversion.ts)`), and the modules it calls and is called by, with theirs (a folder's site named: `described by docs/report.md:3 about backend/src/`). `show NAME` of a function, method or constant lists the texts whose marker names it, its file or a folder holding it in the same place, a marker on a symbol only when the site resolves to it as `check --static` reads the site (`capacity.service.ts:getUtilization`, which names nothing because the method is `capacityService.getUtilization`, describes nothing) (`described by docs/schema-documentation.md:858 (about backend/src/services/demand.service.ts:resolveFullPspNumber)`), and `show` of a Markdown document lists its about markers and its generated regions with their lines, each region with whether it is up to date (`docs/FUNCTION_INVENTORY.md:307 generate functions backend/src/services/central-employee.service.ts is out of date -> python -m flowguard docs rewrites it`). The connections are the calls the map resolved: in JS/TS an import or lexical binding, a member call on an imported object whose module defines that member (a method of its object literal or class, a function it lists or holds, a method of the class of `const x = new C()`), and the calls of callbacks such as route handlers; never a method matched by its name alone (such as `Map.get` or `Array.find` taken for a project function), and not a call whose receiver a parameter, a destructured parameter, a local, a loop variable inside its loop or a catch parameter inside its clause hides. On Planning Tool, read by resolved calls, `audit.service.ts` has 22 calling files and each of its 51 services a caller outside the tests.
- TS/JS calls are recorded and compared when their arguments and result are JSON data: `null`, booleans, strings, finite numbers, and arrays and plain objects of them; each argument and the result may hold at most 200 arrays and objects, nested at most 7 deep counting the value itself (primitives are not counted). A value is read through its property descriptors only; a getter, a proxy, a class instance, a `toJSON`, a symbol key, a hole, `undefined`, `-0` or a key that starts with `$` is not data, and telling so runs no project code. 4.3 recorded only primitives, so Planning Tool's functions, which take rows and return objects, were mostly never compared.
- `known add FINDING --act ACT --why TEXT` (with `--ask`, `--id`, `--site path:symbol`) appends a `known.toml` entry whose sites are the places of the last run's lines of that finding (a line's place becomes the function or constant declared there), checks it as a run reads it, and leaves the file as it was when it does not load. `known add - --act ACT --why TEXT --site SITE` records a matter no check finds: its sites are the `--site` places (`path:symbol`, or a Markdown file's path alone), and its id is `matter` (`matter-2`, ...) unless `--id` names it. `show --last` names each line's finding. The structure findings' steps give that command instead of a ledger `[structure]` snippet, and in `show` the step first names the `check --static --all` run that `known add` needs.
- `show NAME`, `show PATH`, `show RULE_ID` and a flow's view begin with what is already known and decided about the query: the `known.toml` entries in the brief's order and words with the command that prints each (an entry whose site, symbol, holding model or object, a Prisma field's `table.column` or finding names it, or whose why or ask holds an exact field, constant or path as the code spells it), the Markdown texts that describe it, the intent rules anchored there and the `rules.toml` rules they cite, the `writers`, `together` and `same` agreements that name it, sit above it or are written in its file, and the last run's lines at that function or file (`before (last run): ...`, five without `--full`). A name found only through the last dotted part of a site, such as `show update`, names that site. `show <id>` prints a known entry, and a words query also lists the entries whose why or ask shares its words. Every view, a site `path:symbol`, a map id, a file, a folder and a document too, begins with the `show QUERY` header and the Map line, then what concerns it, then its node, module or document lines (`document docs/x.md`); a file or folder the map does not read says so in one line.
- The brief counts the generated regions the last check or docs run found out of date or unwritable (`1 generated region is out of date (last check or docs run): python -m flowguard docs rewrites it`), and `docs` updates that count. It says in one line when `AGENTS.md` or `CLAUDE.md` holds a FlowGuard rules block other than the one this version writes, and `init` rewrites the block in `CLAUDE.md` too. Both files are read as UTF-8, or UTF-16 or UTF-8 by their BOM, and `init` writes them back in that encoding; a file that is neither gets one brief line naming it with the decoder's error.

Reads differently:

- Steps say what is known and who decides (R101); none orders the agent to ask or tell the owner, and a test keeps such orders out of FlowGuard's strings and its agent-facing documents. A `known` line of an unasked question ends `-> an open question for the owner, not asked yet` (4.3: `-> ask owner (not asked yet)`), an asked one `-> asked the owner on D; no answer yet`, a `leave` entry `-> left as it is on purpose; yours to change only if your task is about it`, a `fix` entry `-> marked to fix when its code changes, as this change does`; a `loosened` line ends `loosening an agreement is the owner's decision` (4.3: `needs the owner's yes`); `known fixed?` of an ask entry says `the owner has not answered known.ID: if this change settles it, say so in your report` (4.3: `the owner has not decided: revert, or say why in your report`), of a leave entry `it was left on purpose: if you meant to fix it, remove known.ID and say so in your report` (4.3: `the owner deferred it: revert, or say why in your report`), of a fix entry `if you fixed it, remove known.ID and say so in your report` and of an ignore entry `if it is fixed, remove known.ID and say so in your report` (4.3, both: `say so in your report; remove known.ID once the owner agrees`). The brief's question reads `known.ID: open question for the owner: ...` (4.3: `ask owner: ...`). A conflict of two rules that quote the owner ends `-> the owner's words of the two rules disagree; only the owner can settle which holds` (4.3: `-> ask owner`). The `impact` line of a change that adds a writer to a field several files write without an agreement ends `-> which functions should write it may be the owner's decision; name it in your report` (4.3: `-> fix it, or say why in your report`). In `show`, the fix of a `together` or `writers` agreement says that an `except=` or another writer loosens it, which is the owner's decision (4.3: `only with the owner's yes add ...`), and a partner candidate reads `together candidate (reference only): ... -> if they must change together: ...` (4.3: `with= candidate (reference only): ... -> if the owner says they change together: ...`). Rules 3, 4 and 6 of the block `init` writes say the same, and rule 6 names `known add`. The labels finding's step says that whether the differences are meant is the owner's decision.
- A `known.toml` entry with `act = "ignore"` that 4.3 wrote now also takes its finding out of the brief's count of open structure problems, as a `[structure]` decision did; 4.3 counted the finding while it printed no line for it. This is the replacement 4.3 named for a `[structure]` decision, and it now closes what that decision closed; `leave`, `ask` and `fix` entries keep their finding counted. To have such a finding counted again, change the entry's `act` to `leave`.
- An old problem stays out of an ordinary run until a change touches its place (R99), and stays visible in the brief's counts, `show` and `check --all` (R100). Same-name copies no test reached no longer say `no recorded JSON inputs` (pytest) or `not reached by any test` (vitest) on every run, only once the change edits a copy, writes its mark or, in vitest, edits the binding the reason names. A generated region an earlier change left out of date or unwritable is quiet the same way. An old label-table disagreement is a `before` line only when the change edits the declaration lines of one of its tables, and a declarations or columns finding is touched through a SQL file only when the change edits a statement of its table there (CREATE, ALTER or DROP TABLE with their CHECKs): on Planning Tool, a one-line edit of the assignments CHECK in azure-sql-setup.sql gave 7 `before` lines, six of them about other tables, and now gives the one columns line of that file, which names assignments.
- A `known` line names the sites of its entry this change touches and how many sites the entry has (`known: known.fee-copies at fees.py:close (1 of 3 sites): ...`), then an `ask` entry's question. When the change also touches the finding the entry names, the line comes from that finding and names the finding's places this change touches, a place being one of the entry's sites, with their count (`known: known.fee-copies at fees.py:preview_fee (1 of 2 places): ...`), and every place of the finding when the change touches none of them (`known: known.fee-copies at fees.py:late_fee, fees.py:preview_fee: ...` for an edit of `close`).
- The `before` line of a field several files write without a writers agreement states what held at task start, counting the files that wrote it at the baseline, not a writer this change adds: `before: Job.status has no writers agreement and 3 files write it, close.py:close among them; so at task start -> leave it unless your task is about it` (4.3: `no writers agreement for Job.status at close.py:close was broken at task start`).
- SQL inside a string literal of a SQL file is not read any more (`EXEC(N'...')`, `SET @sql = N'...'`, `E'...'`); 4.3 read it as SQL that runs. SQL in Python string literals and TS/JS raw SQL is read as before. A column, a `CHECK` or a write that only such SQL adds is not declared, so the columns check may give one more `before` line: on Planning Tool, `assignments.internal_order_id` in `check --static --all`. A string ends where its dialect ends it: `E'...'` takes backslash escapes, a plain string's `\'` before a letter or digit is MySQL's escaped quote, and `"..."`, `[...]` and `` `...` `` are names.
- The view of a `together` agreement marks each write that misses a partner (`missing PARTNER: file:line function (kind)`) and prints its fix only then; a `writers` fix and step name the writers as the agreement spells them, and the writers comment a `structure:` step suggests spells each writer as a comment resolves it (`path:object.method`). `show` names an agreement in its 4.3 comment spelling at its place (`writers Project.lifecycleStatusId projectService.create,projectService.update backend/src/services/project.service.ts:1`; 4.3 printed a TS/JS agreement as `owner ...; writers=typescript/...:create,...`, and a `same` reference as `owner FEE`), the agreement's `anchor` line without a module id, and no empty observation lines (`historical observations`, `results: {}`) or `rules: ` line. An agreement's view begins as every other view, with `show NAME` and the map notice (4.3: `ANCHOR NAME`), and no agreement (`same`, `writers` or `together`) gets `info: not referenced by a current model`. `show Model.field` lists writes by file and line number, unclear writes before the reads. The copy search's reason is printed once, `copies not searched: ...`, one line that names every language whose decision sites the map does not read (`copies not searched: the map reads no decision sites in typescript and tsx code`), without a bind step for a TS/JS function or for a Python function an anchor already marks (4.3: `copy search unavailable: not searched: no readable decision sites -> bind the real decision function`).
- A function's signature in `show`'s node view is its whole declaration header; 4.3 cut it at 160 characters, also in the middle of a word (`... fteShare: Prisma.Decimal; valid`).
- The `not compared` line no longer cuts through an item: its paths and places do not count toward its 200 characters, its reasons are shortened first, items that leave no room are counted (`3 functions (...)`), and a single item keeps its name and place. A reason names a construct the sealed comparison does not run in a few words, never the parser's node type, and the line keeps whole reasons: `not compared: TimeRangeSelector (TimeRangeSelector.tsx:39) (holds a JSX element) -> not a failure`, `not compared: 3 functions: TimeRangeSelector (...), loadPlanning (...) and PlanningGrid (...) (holds a JSX element, or is async) -> not a failure` (4.3: `(unsupported jsx_element, or unsupported async or generator)`; Python: `holds a with statement`, 4.3 `unsupported With`).

Corrections of 4.3 bugs, within the existing contract:

- R85: on a machine without FlowGuard, the npm static test and the vitest plugin failed every run, so a project's own tests could not pass there. The static test is now skipped under a name that says FlowGuard is not installed, and the vitest config gets no plugin and one notice; a `FLOWGUARD_PYTHON` that cannot import FlowGuard still fails. `init` rewrites both generated files.
- An unchanged copy compared on some of its inputs was `not compared` when a made-up input gave a result that is not data: Planning Tool's three ISO week copies were listed in every frontend run, because `86400000 + 1` taken as a year gives `NaN`. Only a real call that could not be recorded or run is `not compared` now.
- The brief put an asked but unanswered question after the `fix` and `leave` entries, so Planning Tool's open questions fell out of its eight lines.
- The brief's structure line pointed at `check --static --all`, which runs no copy discovery, so copies that drifted apart were counted but listed nowhere it named.
- A rule source quoting a UTF-16 document ended `show rules` and `check --static` with exit 2 (`'utf-8' codec can't decode byte 0xff in position 0`), and so did `init` on a UTF-16 `AGENTS.md`. Rule sources, ledger rules, the brief and `init` read UTF-16 now; a document in another encoding is that reader's problem, naming the file.
- A 4.3 cross-file position (`path:function`) whose target file was renamed gave a false `loosened` line.
- In TS/JS, a flowguard comment after a line that holds U+2028, U+2029, a form feed or another character Python's `splitlines` breaks at (`\x0b`, `\x1c`-`\x1e`, `\x85`) was numbered one line late: 4.3 said `red: comment a.ts:4: a.ts:4: sensor FEE needs a function declared on the next line -> correct this flowguard comment` for a `same FEE` right above its function. 5.0 counts lines at newlines only, as the JS/TS parser does.
- An assignment whose object a resolved Prisma write passes on (`updateData.lifecycleStatusId = ...` before `tx.project.update({ data: updateData })`) counts as that one write. 4.3 also reported the callback that holds the assignment as a writer outside the agreement, a second `before` or `red` line for one write: `before: writers Project.lifecycleStatusId at import.service.ts:ImportService.commitProjects.<anonymous@3,31> was broken at task start`.

- Verification on the release commit: the full suite (2,780 tests; 2 skipped by their Windows-only platform marker) passed with Python 3.11, 3.12 and 3.13 from virtual environments outside the repository, and the complete CI ran on this commit (Linux Python 3.11 and 3.13, Windows Python 3.12). A scratch copy of Planning Tool was upgraded to a candidate of this release as its upgrade notes say (the pin, `init`, the fte_share range as an open question in `known.toml`, seven `about` markers and three generated regions, whose hand-written lists had one wrong row and three missing, two wrong values of five and one missing value). Its 2,283 backend unit tests and 1,972 frontend tests gave the same result test by test with FlowGuard 4.3, with the candidate and without FlowGuard; Planning Tool's own 47 and 17 failing tests failed alike in all three. Three one-line changes and about 20 `show` names on that copy were judged line by line; what they showed wrong (a site on a `.sql` file crashed, generated function lists held map-internal names and cut signatures, relation fields were written as columns, `show` did not say which text describes a name, and others) is corrected in this release. A blind comparison with 4.3 on real Planning Tool tasks is not yet made: its first attempt ran out of disk and did nothing, and it follows on the Planning Tool that is being upgraded now.

Known limits:

- A rule in `tests/intent/` runs only Python functions; TS/JS copies are compared by `same` alone. Only inputs the tests used are compared (copies add their numbers and ±1). Functions that read configuration or a database, or call helpers of another file, are not compared sealed.
- A TS function runs sealed in steps of at most 100 ms, and its `not compared` line does not yet tell a timeout from a failure (`sealed execution failed or timed out`).
- vitest keeps its own cache in FlowGuard's adapter folder (`flowguard/adapters/vitest/node_modules/.vite`), as 4.3 did.
- Whether `changed` catches an unintended change in a real task is not yet measured. `impact` counts the readers of a model, not yet of one field.
- zod lines read `z.number(` and `z.coerce.number(` chains, also inside `z.optional(`, `z.nullable(`, `z.nullish(`, `z.preprocess(` and a pipe. zod 4's `z.int()`, `z.union(...)` and a shorthand key (`{ fteShare }`) give no line; `.or(...)` and `.catch(...)` on a number chain are not named (`z.number().min(0).or(z.string())` reads `0 <= fteShare`); a schema object a function returns is `an unnamed object`.
- SQL that a string builds at run time is not read, also when an `EXEC(N'...')` holds one complete literal, as the older central migrations of Planning Tool do. In a plain string, `\'` counts as MySQL's escaped quote only before a letter or digit: `'rock \' roll'` ends at `\'`, and the statements after it are read as inside a string.
- The pair and delete checks still resolve JS/TS member calls by name (`(calls resolved by name)`); only the module view, the module contracts and a function's callers use resolved calls, so a destructured dynamic import (`const { x } = await import(...)`) connects nothing there.
- `show` gives no const line for a Python module constant, `generate constants` lists JS/TS constants only, and a Python name whose value is no literal, such as `Status = Literal[...]`, gets a `not on the map` line. A TS interface or type name gets no declaration line. Holder lines cover JS/TS object literals and classes; a Python class gets its node view.
- `known add` turns a line's place into a site only where a function, constant or `Model.field` is declared there; for another declaration, such as a type alias, it asks for `--site path:symbol`.
- Only the writers family states what held at task start; labels, delete, together and the other families still say `was broken at task start`.
- The brief's saved counts moved to a new cache key (`brief_counts`), so after the upgrade the brief shows no structure or region line until the first `check`, `python -m flowguard docs` run, or pytest run while the task has changed code. The map records each JS/TS module object's members and each function's whole signature (4.3 cut it at 160 characters), so the first run after the upgrade rebuilds it.
- Generated regions cover four kinds; routes, environment variables and package scripts are not generated. A Markdown document that is neither UTF-8 nor UTF-16 is named only when a change edits it.
- `show` of a constant does not name its users: `show batchAssignSchema` gives its declaration and range, not the route that applies it (`validateBody(batchAssignSchema)` in demand.routes.ts), and `show MAX_FTE_SHARE` no reader either.
- A zod validator that a route applies is not linked to the model the route's service writes: a field's own schema objects are found by their name alone, so `show LendingAssignment.fteShare` lists `lendingCreateSchema` and `lendingUpdateSchema`, which lending.routes.ts validates before LendingAssignment.fteShare is written, among the keys of other schema objects.
- A `known` line that comes from an entry's finding names the finding's places: when the change edits a site of the entry that is no place of the finding (`fees.py:close` of `known.fee-copies`), the line names every place of the finding (`at fees.py:late_fee, fees.py:preview_fee`) without a count, while `check --static` names the edited site (`at fees.py:close (1 of 3 sites)`).

## v4.3.0 - 2026-11-15 - Record real calls, compare them sealed, say what this change did

A feature release from rebuilding FlowGuard around what maintaining Planning Tool showed: an agent reads the last lines of a test run, a red must mean "your change broke this", and a second run of a function inside a test can break the test. Saved inputs keep their meaning and bytes: comments in either spelling, intent rules, literal rows, sources, flows, ledger entries, owner-word records and `[structure]` decisions; nothing needs migrating. Run `init` again for the new rules block and, in a vitest project, the new `flowguard.vitest.mjs`. See [the 4.3 notes](docs/upgrade-4.3.md). 4.2.2 was prepared on the development branch but never tagged or published; its two commits were reverted, so 4.3.0 follows 4.2.1.

- Sealed comparison. During the tests FlowGuard only records the JSON arguments and result of real calls: of functions marked `same` and of functions this change edited, the first 20 distinct calls per process. After the tests it runs their old and new source in a closed environment: in Python the def and its same-file helpers compiled into globals with a short list of built-ins, `math`, `decimal.Decimal` and `datetime` without the clock, module-level literal constants read from the source (also arithmetic on them, and a literal constant imported from another project module, read statically); in TS/JS the function without its types in a fresh `vm` context. Nothing of the project is imported, and no function or test runs a second time inside the session, so test results, test doubles and coverage are those of a run without FlowGuard. `calibrated_by=` reads the call the named test made in its ordinary run instead of running it again; scenario contracts are completed from the test's recorded calls; event anchors record their real path and no longer run the test again with the old code. The in-test replay, its audit-hook guard around project code, sqlite savepoints and authorizer, argument deep copies, the replay grid and partition cache, the reuse fingerprints and the vitest Node-module interception are removed. Against 4.2.1, flowguard/ gains 9,749 lines and loses 5,073 (36,754 lines of Python and JavaScript, from 32,078); what is marked for removal in 5.0 is still there.
- Same-name copies run sealed on the recorded inputs, the numbers the copies use and the ±1 neighbours of both, recorded inputs first and at most 64 inputs per name, and their task-start versions run on the same inputs. Each input is judged on its own: copies that agreed there and differ now are red; copies that already differed are `before` (or `known`). A frontend test no longer loads the backend to compare a copy. `git mv` of a copy compares it with its old path.
- What cannot run sealed is `not compared` with its reason (a name the environment lacks, a result that is not JSON, async, generators, decorators, methods, non-literal defaults; TS enums, namespaces, decorators, JSX, parameter properties, non-primitive results) and fails nothing; a lost observation no longer fails the run. A comparison is due only for a function this change edited (its body, a constant it reads, a same-file function it calls), a function that imports a constant this change altered, and names with two or more copies; a project in a subfolder of its Git repository is compared like one at the top. Plain `check` runs the affected intent rules, not the project's ordinary tests, so `changed` lines come from test runs and `check --all`. On 62 functions sampled from Planning Tool, 31 qualify by their source and 6 (9.7%) ran sealed with synthesized primitive inputs; this is a lower bound for that sample, not a coverage figure for the code base. FlowGuard's own suite shows what this means for code that reads paths, syntax trees and configuration: in a full run on Python 3.12, compared with 4.2.1, all eight of its sensors have items that are `not compared` and fail nothing. The rule items on PROJECT_SOURCE, SOURCE_AUTHORITY, ROW_LITERAL and ROW_PROBLEMS use what the closed environment lacks (`uses attribute resolve`, `uses attribute strict`, `uses attribute Constant`, `uses attribute name`), those on QUOTE_MATCH need a quote argument the scenario test computes, SOURCE_AUTHORITY's result is not JSON, the observation flows of ORIGINAL_BYTES, REQUEST_BODY and REQUEST_METADATA keep unobserved error edges, and those of the other five say that the trace hook changed during the calibration probe.
- One block for every run. pytest, `check`, `check --static` and vitest end with the same English block after the runner's summary. Its first line counts each kind and FlowGuard's own seconds, `FlowGuard 4.3 (since 99f025e): 1 red, 1 changed; 0.3 s`, and names the baseline it compared with. The lines that follow start with `red`, `before`, `known`, `known fixed?`, `changed`, `impact`, `loosened` or `not compared`; `deprecated` notices for what the project itself uses go to stderr, once per process, after the block in pytest and vitest. The block is printed also when vitest observed nothing and outside Git (`no baseline: nothing compared`), and goes to stderr when a JSON, junit or TAP reporter writes to stdout. red, loosened and known fixed? are listed in full, the others share ten lines, and `python -m flowguard show --last` prints every line of the last run with its details. Red lines no longer suggest the comment that would silence them. All output is English.
- Colours. A run fails only for a red line: what this change broke. A new agreement over code that already broke it gives `before` (it is judged against the task-start code), copies that already disagreed give `before`, automatic structure checks (deletes, columns, onDelete, labels, never-filled tables, look-alike copies, declarations) give `impact` when new and `before` when touched, never red. `impact` also says when a changed function now writes another set of fields, with the field's other writers and its model's readers.
- `.flowguard/rules.toml` holds the owner's current rules (one line of text, a source quoting stored words or an `authority_docs` sentence exactly); intent rules may cite `rule.<id>`. `.flowguard/known.toml` holds open questions and deferred problems with `act = "leave" | "ask" | "fix" | "ignore"`, an optional `finding` and the `asked` date; an entry whose site's text this change edits (comments and spacing included, not a line beside it) is a `known` line, an entry whose finding is gone is `known fixed?`, and changing or removing an entry is `loosened`. `show rules`, `show rule.<id>` and `show known.<id>` list them. FlowGuard 4.2.1 reads a project with both files without a red (pinned by a test that runs 4.2.1).
- `new-task` prints a brief of at most eight lines: baseline, the first rules, the open known entries by urgency, the structure count and what the last task left. `init` writes a seven-line rules block. FlowGuard's own repository keeps its first `rules.toml`, six rules quoting the owner's words.
- Comments: `same NAME` (`same NAME ref` for the reference copy, in TS/JS too), `together A B,C` (`on=`, `B=value`, `except=path:function(reason)`) and `writers A f,g`. The 4.2 spellings (`sensor`, `owner`, `with=`, `alone=`, `writers=`) are read with their old meaning and print a deprecation notice. Rewriting them in the 4.3 spelling loosens nothing: a 4.2 bare name in `alone=` or `writers=` meant the function of that name in any file, and `except=path:f` names one of them. A writer named by its position holds the writes of the callbacks inside it, as a 4.2 bare name did. A test's own write is not held to a writers agreement, as it was not to a pair; 4.2.1 called it red.
- Deprecated, removed in 5.0: `anchor draft`, `model draft`, `try`, `watch`, `compare`, `show --draft/--gaps`, `check --since` (use `--base`), `check --leads` (use `show --last`), `req add --kind glossary|adoption`, the relation templates, `distinct`, `structure_rule`, `Transition`, `pytest.mark.rule`, the ledger's `[unverified]` and `[structure]` (use a `known.toml` entry), and FlowGuard's own old-value, label-spelling, similar-implementation and unregistered-copy leads, which print neither a line nor a notice (`show --last` keeps them). `status` and `where` of FlowGuard 0.7x print the command to run instead.
- R85: FlowGuard never changes the software it maintains. The vitest plugin applies only in a vitest run, and the generated `flowguard.vitest.mjs` returns no plugin and starts no Python outside one, so `vite build`, the dev server and `vite preview` carry nothing of FlowGuard and build where FlowGuard is not installed. 4.2 bundled its recording calls into a build of a changed function and failed to build without FlowGuard; run `init` again to rewrite an older `flowguard.vitest.mjs`.
- vitest: the failed case "FlowGuard execution side" says one line, `FlowGuard: N red, see the FlowGuard block at the end`, which is all of its JSON `failureMessages`; the map checks of the static test join the block. A run whose path filters, `-t` or `--project` leave that case out still has its red in the exit status and the block, but not in vitest's JSON or junit results, which vitest writes before FlowGuard can judge. `init` says when vitest's `test.include` leaves `flowguard.static.test.mjs` out, or cannot be read. Recorded TS positions follow the lines JavaScript counts (CR, LF, CRLF, U+2028, U+2029), so a stack position after a line separator is right.
- Corrections that can turn a run red where 4.2.1 reported nothing: a helper file that stops writing a pair's partner makes its unchanged caller red; a partner written for another record (another `where`), only in one branch or in a conditional spread, or by a sibling route handler, no longer holds a pair; a request stored during the task that supersedes or retires a cited source makes the citing rule red; an intent file that does not load is red in vitest as in pytest; a vitest run outside Git, before the first commit or with a recorded task start the repository lacks compares its same-name copies as pytest does, where 4.2 compared nothing; an invalid `rules.toml` or `known.toml` entry is red (new files only).
- Verification on the release candidate: the scenario library (195 scenarios, each under vitest 4.1 and 3.2) gives the test results of a run without FlowGuard in every scenario (two of the 390 runs failed once, one with FlowGuard and one without, both in scenario tests that read a file before their own write had finished, and passed when run again); the 54 variants of fixed Planning Tool problems meet their expectations (a problem brought back is red, a correct fix passes); on Planning Tool the frontend and backend tests give the same results test by test with and without FlowGuard, a comment changed in `calendar-iso.ts` gives `before` with `year=2025` for the ISO weeks copies, and a frontend run no longer loads backend code; eight Python test-double scenarios (among them pytest-mock, a module-global MagicMock, a mutable default and a decorated function) end with the results of a run without FlowGuard; `vite build`, the dev server and builds started inside a vitest run carry nothing of FlowGuard. Three corrections came from upgrading Planning Tool after that: the 4.3 spelling of a 4.2 exception or writer is not `loosened`, a writer's callbacks write for it and a test's own write is not held to a writers agreement, and a rule bound to a TS copy says why it is red. They change only what `check` reports about comments and rules; Planning Tool's tests were compared again with 4.2.1's, test by test. FlowGuard's own suite passes in CI on Linux with Python 3.11 and 3.13 and on Windows with Python 3.12.
- Speed on Planning Tool (median of five runs, FlowGuard's own seconds): with nothing registered and no change it adds 1.4 s to the backend unit tests (23 s) and 1.7 s to the frontend tests (123 s); with a change, 1.9 s and 2.3 s; a warm `check --static` takes 1.4 s, 2.2 s for that change and 3.8 s when a file that 79 others import changes. FlowGuard's own suite, about 2,780 tests with 29 verified intent items, spends 48–53 s in FlowGuard of about 1,050 s (about 214 s of 1,250 s on the candidate before three speed fixes), and about 50 s with a change; most of what remains is the look at the loaded modules at the start of every test, which 4.4 is to change.
- Use by an agent, measured once on this release: three Planning Tool tasks, each done three times by one agent model with this release and three times with 4.2.1, scored blind. In the task that touched the open percent-scale question, a `known` entry with `act = "ask"`, every run with this release raised it with the owner and no run with 4.2.1 did. An intended change shown as `changed` drew no agent away from its task (0 of 3), no agent worked on the deferred ISO weeks problem with either release, and tool calls, minutes and tokens were about the same. 4.4 keeps the before/after comparison on by default.

Known limits:

- A rule in `tests/intent/` runs only Python functions; bound to a TS/JS copy it is red and says so (4.2.1 said `home gone` with a `ModuleNotFoundError`). TS/JS copies are compared by `same` alone.
- Only inputs the tests used are compared (copies add their numbers and ±1). Functions that take objects, read configuration or a database, or call helpers of another file are not compared; comparing helpers across files is left to 4.4, as are the readers of one field for `impact`.
- vitest keeps its own cache in FlowGuard's adapter folder (`flowguard/adapters/vitest/node_modules/.vite`), as 4.2.1 did.
- A TS function runs sealed in steps of at most 100 ms. On a heavily loaded machine a few comparisons ended `not compared (sealed execution failed or timed out)` (3 of 390 scenario runs); such a line never fails a run and test results stay the same, but its cause was not reproduced under synthetic load, and the line does not yet tell a timeout from a failure.
- Whether `changed` catches an unintended change in a real task is not yet measured: in the measurement above no agent made one. It catches a careless edit in the same file, not logic moved to a new file and imported.

## v4.2.1 - 2026-11-10 - Next steps that do not mislead

Corrections from maintaining Planning Tool with 4.2.0 and from three rounds of adversarial review. Saved inputs keep their meaning; nothing needs migrating.

- Same-name copies: a red says what each copy answered (`3 份：2 份得 52（…），1 份得 1（…）`) and no longer picks the copy to change: without an owner the next step is to decide which answer is right; with an owner the other copies follow it. Every copy that differs from the owner is named on its own nearest input, in pytest and `check` alike, and `check`'s "one copy changed, its former equals did not" red follows the owner too. On the TS side the step says to give copies that are meant to differ different names, since TS has no `distinct`.
- A violated rule's next step follows the kind of red, the same in pytest, `check` and vitest: code that differs from the rule → change the code (a changed requirement: store the owner's words first); a rule against its own row or a gap → fix the row or the rule; two rules that conflict → decide one, asking the owner. Reds that are not a rule's keep their own step.
- TS/JS projects whose tests npm runs and pytest has none of its own: `new-task` says to compare dropped commits with `python -m flowguard check --static --base X`, and `init` writes a CI fragment that runs `check --static` against the merge-base with the default branch, failing when that base cannot be found. Python projects keep their fragment. Virtual environments, conda environments and folders that cannot be read are not searched for the project's own tests. An empty `--base` or `--flowguard-base` is refused.
- `--help` describes every command.
- `init` lists, in the AGENTS.md it wrote and outside its own rules block, only lines that name a command, launcher, install or required version of an earlier FlowGuard, each with the releases that had it (`python -m flowguard status` from FlowGuard 0.71–1.4), numbered as written; a launcher may carry the interpreter's own options (`py -3.11 -m flowguard status`). A line that explains 0.70's files, or a minimum 4.x meets, is not listed.
- Ledger: a `[structure]` entry with fields of a later FlowGuard is unverified instead of red and closes nothing; its `decision` and `source` are still checked, and a near spelling of either while it is missing stays red.
- A Prisma write of `undefined` (also `void …`, `data.x = undefined` and `{ set: undefined }` or an arithmetic update of `undefined`) writes nothing, so it no longer satisfies a pair rule.
- An unverified count line no longer repeats the reason of its only item.

## v4.2.0 - 2026-11-10 - Lessons from maintaining a TypeScript monorepo

A feature release from applying 4.1 to Planning Tool 0.6.28 (TypeScript, Prisma, SQL Server) and from four rounds of adversarial review of the result. Saved inputs keep their meaning; see [the 4.2 notes](docs/upgrade-4.2.md), which also list the problem names that change for a schema folder. The README and the skill now say how FlowGuard is meant to work: review finds a problem, registration keeps it from coming back, and the registrations grow with the software.

- Task baseline: commits made during a task keep its baseline. `python -m flowguard new-task` starts a task (rule 1 of the block `init` writes says so; run `init` again to update an older block), and says which earlier commits it stops comparing. When nothing is recorded, the first pytest session, `check` or `check --static` on a branch records HEAD (not on a detached HEAD, not in `--collect-only`, not under `--base` or `--flowguard-base`). The title says how far the task start lies before HEAD, `相对 HEAD` where HEAD stands in, and names a recorded start the clone lacks instead of comparing nothing silently. The brief on a detached HEAD moves nothing.
- Run the map checks in ordinary pytest when a TS/JS, Prisma or SQL file changes, with the TS/JS owners `check --static` reads.
- Pairs and deletes: a by-name JS/TS call resolves only inside the caller's package and the way up from production code skips tests, for pair rules and the delete check alike; a test's fixture write is no pair violation. `on=update` (or `on=create`) after `with=` holds only the writes that change (or make) a row. Each owner's pair red is its own line, `配对没写 OWNER：…`. Prisma's default delete rule follows the key fields; a tree's self relation is exempt when its parent key can be null.
- Value gate: Prisma enums come from the schemas the generator reads (`schema.prisma`, `prisma.schema` or `--schema` of any `package.json` up to the root, `prisma.config.ts` read without comments); archived files take no part; a schema folder is one schema. A package that names none is judged by its own schemas, each enum its own set, and says so. A Prisma write is judged by an enum of its own package's schema in use (another schema that lacks the field, or a template that types it as text, does not stand in the way; two clients that disagree leave it unjudged), a typed object of a schema's client output by that schema. A field keeps its SQL `CHECK` beside its enum. A TS typed object is judged by the type its own file declares, else the one it imports, resolving a set name through the file's import. `x ?? 'v'` is judged. Problem names keep 4.1's: `values:NAME` for the enum of a schema in use, else the CHECK, else the TS type; further sets add their place.
- Structure listing (`check --all`): tables production code reads or deletes but never fills (`uncreated:Model`, Prisma views aside); label tables and option lists that copy each other but spell a label differently or lack a key (`labels:file:NAME`); delete rules that differ between two Prisma schemas (`ondelete:A~B`, files in path order; either direction, and a foreign key one database lacks; relations matched by mapped table, key columns and parent); unreviewed legacy fallbacks of production code grouped by how the catch ends (substitute value, log only, empty; a JS/TS catch that returns an answer through the handler's response, also under `void`, answers the request). A one-row delete of a tree the code builds is checked for its child rows. A problem the owner decided in `[structure]` gets no lead; a `copies:` decision covers the functions of the decided problem.
- Less noise: schema descriptions are compared once, with the schema in use; SQLite rebuilds (`RENAME TO`) and `CREATE TABLE ... AS SELECT` are followed; files under a `docs` folder are archives (`[tool.flowguard] archives` replaces the default). Label spellings group only within one kind (codes, keys, texts) and leave test files and FlowGuard's own generated files out. A comment added above a function no longer touches its structure problems.
- Output: `--all` lists this change's leads first; `check --leads` and `check --static --leads` print every lead, and overflow lines name the command with the run's options (`--base`, a pytest session's `--flowguard-base`); `check --base X` is titled `相对 --base X`. `show Model.field` lists `.sql` writes and the fields its writers also write as `with=` candidates; `show QUERY --full` prints a whole listing. `check --base X` in a project without rules reads the ledger against X.
- `init` adopts a FlowGuard 0.70 project: it replaces the 0.70 workflow sections of `AGENTS.md` and updates only the pinned version and the install line, keeping the project's own rules byte for byte and listing other lines that name 0.70. In a `package.json` project it adds the static test to one test script that runs named folders only (`test` first, then a unit script), never to a watch, debug, integration or end-to-end suite, and only to a call whose options it can read (an option's value is never a path); says which script runs the check, or that none does, with the edit spelled the way that script starts the runner; writes an ES module jest test only where jest runs under `--experimental-vm-modules`; writes no test where no runner is named; lists stale 0.70 test bindings with the `norecursedirs` line to add; registers the pytest plugin once; and keeps machine paths out of the generated npm files (`.flowguard/cache/python`, git-ignored).
- vitest: an execution-side red is a failed test case ("FlowGuard execution side") in JSON and junit reports; a disagreement names the replayed input closest to one a test used; same-name sensors that disagreed are compared again without a TS change; each run lists only its own package's unreached points.

## v4.1.0 - 2026-11-09 - Guard a project's consistency while an AI changes it

- Add the fallback ledger `.flowguard/ledger.toml`: every exception handler that can end without raising, per `file:function:caught`, with its count, what it does and the written rule it serves. `ledger init` records existing handlers as legacy, which can only shrink; ordinary pytest and `check` fail on a new, changed or vanished one. Bare `except`, `except Exception`, `contextlib.suppress`, warning filters, exits from `finally` and truthy `__exit__` cannot be listed. JS/TS `catch` blocks that hand the error to `next`, `reject` or `throw` are not fallbacks.
- Report a grey intent item as its own outcome (`U`, `UNVERIFIED`, `N unverified`) instead of a pass, without changing the exit status; mark it in JUnit XML and write session reds as the failed testcase `flowguard::session`. A point the baseline code still observes but the new code cannot is a lost observation and fails the run unless `[unverified]` lists it with a reason. `check --all` fails an unverified rule, flow or template whose source quotes the owner. FlowGuard refuses pytest-xdist workers, which dropped session reds.
- Print one closing block titled with its baseline: every red, then changes, leads and unverified within ten lines, untruncated, each red and lead with the next step to copy.
- Guard call-site replays at runtime instead of requiring a static proof: an audit hook refuses file, process, network, thread and signal effects before they happen; shared sqlite3 connections hold a savepoint, stay read-only and are checked afterwards; arguments are replayed on deep copies; uncopyable or unseen arguments, timeouts and recursion stay grey with their reason. The `random` state and working directory are restored; the original-value recheck waits for a clock tick.
- Add owners: `# flowguard: owner NAME` for a function compared with its same-name sensors, and data owners `owner Model.field writers=... with=... alone=...` for allowed writers and fields that must change in the same operation. Read Python attribute and SQL writes with their values; gate written values against `states`, enums, Prisma enums and SQL `CHECK` sets. Discover look-alike copies in `check` and group them as copies, forked copies or similar code; lead when a function changed alone while its former equals did not. Projection outputs (`-> result.ok`) and explicit parameter maps compare differently shaped copies.
- Read rule fields from the call's context with `fields name=expression`. Lead when a rule still holds a replaced value and when a rule's copy changed while the rule did not; `show` lists the classes a rule leaves open.
- Add literal drift, declarations that differ, deletes that leave restricting children, columns missing between schema descriptions and a structure listing in `check --all`, with `[structure]` decisions for the owner. Touching an open structure problem prints a lead to tell the owner.
- Add `precedes`, `guarded_by`, `transitions` and `checks` relation templates on the existing flow checks; `model draft` drafts template lines.
- Extend the TS/JS reader with Prisma writes, `catch` facts, literals, declared sets, folded constant names and shapes, and read Prisma schemas and SQL files. `check --static` runs the map checks without pytest; `init` wires it into `npm test`. Vitest (ESM) projects also get the before/after comparison, same-name copies and rule checks, judged by the Python core; jest stays static.
- Reuse a changed anchor's comparison while its fingerprint is unchanged. Store map facts by kind so `show` and queries answer within a second; check only the owner words a rule cites; prepare imports once per session. Fix the `check` self-lock, the grey regression of calibrated config rules, broken source files, global monitoring of every call, a closed pipe under `PYTHONUNBUFFERED`, the engine digest under a C locale and `show` on camelCase names.
- `init` writes three project rules and replaces the older level-one rules block. Remove weak copy candidates. Existing comments, rules, rows, sources, flows and owner-word records keep their meaning; see [the 4.1 notes](docs/upgrade-4.1.md). Other skills keep their existing pins.

## v4.0.0 - 2026-11-08 - Compare real behavior before asserting requirements

- Make ordinary pytest report changed outcome classes, inconsistent same-name sensors and violated independent rules in a bounded three-signal view. Keep unavailable historical comparisons visibly incomplete; map copy suggestions remain clues.
- Replace observation subprocesses, archive execution and nested pytest sessions with one shared runtime. Replay safe representatives before the real call with its actual context; drive scenarios through existing collected tests with fresh function fixtures and native lifecycle reports. Preserve the one real application call, native exceptions, foreign debugger ownership and mandatory observer failures.
- Read previous function bodies and constants from a fixed Git baseline. Retain every representative and actual input, and add representable neighbours around the real input tuple without crossing them with every distant representative. Reuse unchanged static partitions within the session while observing current contexts and values again. Use function fingerprints and precise code-object identity; equal bytecode in different files must not merge readings. Reject forged enum members and unverified replacement bodies; explicit generated mutation checks remain in `check --deep`.
- Support the short `# flowguard: sensor NAME` comment and infer inputs versus context. Retain full comments, independent rules, literal rows, source authority, linear partitions and complete finite-model enumeration without a fixed state/depth cap; cycles and unobserved edges remain grey.
- Add optional historical `show` views, `try`, `watch` and `model draft`. Keep the task brief at ten lines, remember its baseline in the existing cache and store original words only as cited sources. Freeze foreign readers behind the optional `languages` extra.
- Retire observation RPC/child recording, historical archive comparison wrappers, diagnostic JSONL, the built-in CHECK_PIPELINE, shard switches and the legacy `python -m flowguard.intent` entrypoint. Remove unused change/release-record producers and move repository route-test helpers out of the product. Preserve original archives, snapshot readers and all historical releases.
- Run a complete unsharded suite on each required CI platform. Publication still requires the complete workflow on the exact main commit. This is a major release because supported execution and CLI boundaries changed; see [the 4.0 migration guide](docs/upgrade-4.0.md). Other skills keep their existing pins.

## v3.0.1 - 2026-11-08 - Restore test isolation and make deep checks explicit

- Restore the caller's exact import-path list after each calibrated pytest session, including its ordering, intentional duplicates and pytest path ownership. Preserve restoration after ordinary returns, controlled stops and exceptions.
- Keep a single FlowGuard SDK namespace in editable installations, while retaining protection against a project shadowing the installed SDK.
- Move decision probes and mutation-survival checks to explicit `check --deep`. Ordinary pytest and default checks retain rule, literal-row and source-copy checks using readable static code boundaries; unresolved boundaries remain grey. A default collection never substitutes for a complete deep run. CI uses `check --all --deep`.
- Remove an execution-order dependency for empty literal-row checks in composed rules. An empty row set does not claim that a lower witness ran; an incomplete or rejected lower contract still prevents reuse.
- This patch corrects execution and default check costs within the 3.0 source-anchor contract. Existing full anchor syntax, rules, saved inputs and release history remain supported.

## v3.0.0 - 2026-11-08 - Connect executable rules through source anchors

- Replace the public `Home` / `.home(...)` and custom adapter execution API with source sensors and ordinary calibrated tests. This is an incompatible SDK and saved-rule change; rebuild bindings from the original tests and inputs using [the migration guide](docs/upgrade-3.0.md). Archived owner words, rule predicates, literal rows and historical releases are unchanged.
- Draft and verify sensor, state and event anchors against real source signatures. Run supported pure judgments directly; retain unknown purity, input ranges and calibration boundaries instead of supplying an answer through an adapter.
- Connect actual anchor events to small layered flows with nodes, edges, existing state transitions and reading relations. Check supported source paths, observed order, finite state reachability and real reading identity. Registered child graphs must pass their own checks before exporting a same-invocation result to a parent. Untested paths and unsupported source constructs remain grey; this is not an exhaustive proof of arbitrary application behavior.
- Compare changed anchor behavior in isolated source processes, show only changed supported classes, and keep incomplete comparisons visibly incomplete. Automatic comparison defers open, calibrated or large domains to an explicit check rather than silently accepting zero changes. Compare same-named anchors and show unanchored copy candidates as inspection leads.
- Preserve effective rule replacements, real joint lower witnesses, conflict and mutation checks, incremental dependency boundaries, ordinary pytest integration and exact-source release CI. Compose only FlowGuard-owned trace observers; foreign debuggers remain an explicit boundary. Do not retain events outside declared test-entry scopes, while preserving events inside those scopes and production-entry bypass checks.
- Shorten default source navigation and resolve imported aliases. Language maps remain available for Python, JS/TS, C/C++ and C#; executable anchors in this release are Python only. Other projects keep their existing dependency pins until they separately migrate.
- Add explicit `check --diagnose` for the checker's small `CHECK_PIPELINE` model and live diagnostics over already activated project anchors. Reuse the same events, source identities and writer; record real starts, returns, exceptions, states and elapsed times. Ordinary checks retain project verification without enabling this extra diagnosis. `show CHECK_PIPELINE` reads the one built-in declaration without running it.
- Separate finite-model checks, observed paths and reading relations, and unverified static paths. The checker model's own static paths are not checked; missing or ambiguous batch readings remain grey. Private calibration probes are not expanded into ordinary diagnostics. Nested sessions in one process preserve their writer and timing identities; arbitrary concurrent processes sharing one project cache are outside the diagnostic guarantee.
- Keep synthetic pure-sensor verification out of ordinary-test event coverage, as for calibrated probes. Preserve real application calls, source and type checks, footprints and restoration of the surrounding observer.
- In explicit diagnostic mode, print final runtest failure details as they occur while preserving selection, later tests, effective xfail, private probes and exit codes.
- Recognize configured intent directories through real directory aliases while preserving pytest paths and existing leaf-link roles.
- Preserve comparison results on terminals that cannot encode their text by escaping only the human display; Unicode reports and original data stay unchanged.
- Close cache-reader SQLite connections after both successful and failed reads, retaining their transaction semantics so Windows can release the cache files.
- Avoid unused per-line callbacks in boundary observation. Preserve real call, return, exception and state readings, nested observers and the original frame flags on return or scope exit.
- Measure diagnostic event intervals with the high-resolution monotonic performance counter, including Windows Python 3.12 where the general monotonic clock has coarse ticks. Keep the raw timestamp difference, including genuine zero intervals.
- Stream the original test nodes and partial output during `check --all`, preserving real failures and interruptions. Keep readable latest-run diagnostics and CI artifacts. A shared diagnostic-output helper reports unavailable output without replacing the underlying check result.
- Read a saved owner statement through the existing owner's single-record projection while retaining its integrity and retirement checks. Avoid traceback-source formatting for internal controlled calibration stops; retain actual native exceptions, test lifecycle and outcomes.
- Keep the skill defaults to status, original words, source navigation and checks of existing bound decisions after the optional-use trial missed its benefit criterion. Anchor old judgments before a relevant edit; behavior comparison and small flow models remain available for focused maintenance.
- Keep source word search usable when a missing imported symbol has no documentation. Preserve its unresolved identity while continuing to rank actual source candidates.
- Reduce duplicated ownership work during import preparation: evaluate identical project/host roots once and exclude already resolved SDK paths before application checks. Preserve separate-root order and source/environment boundaries.
- Preserve both real caller edges when different functions resume the same generator. Remove the code-ID deduplication cache: footprints use their existing result sets and no longer retain temporary rewritten code just for deduplication.
- Support explicit `check --all --shard k/n` partitions through the existing pytest route. Each partition checks every intent item, the sentinel and required scenario tests; ordinary primary nodes are disjoint. A partition never refreshes a complete ordinary-file baseline. Optional shard reports record the final check result after source and history checks.
- Run all three CI platforms in six partitions each and require exact-source coverage of the complete collection before publication. Publish from that successful CI run and attempt; missing, failed, skipped or incomplete jobs do not satisfy the release gate.

## v2.1.1 - 2026-11-06 - Correct dependency and C++ source boundaries

- Rerun tests whose external imports or calls have unverified inputs, including helpers on pytest's outside pythonpath. Locate import origins without executing them and distinguish actual project code from in-project virtual environments. A package version or a familiar function name alone does not prove purity; supported modeled operations retain their provenance and input checks.
- Keep uninitialized dotted namespace-package provenance unverified instead of crashing while looking for its parent in the import cache; do not import that parent merely to inspect its source.
- Keep parent-package initialization, defaults, decorators, classes and real callbacks in scope. Do not invoke every ancestor's lazy attribute hook for a child-module lookup, or treat storing a function object as executing its body. Open external and dynamic inputs remain explicit and may require no-op reruns.
- Build read-only AST scope views instead of deep-copying function bodies that will be discarded. Preserve dependency values, fingerprints and unknown reasons; do not introduce a persistent cache protocol or remove missing import candidates.
- Recover the confirmed C++ reference direct-initialization grammar gap from independently parsed ranges of the same normalized source. Retain true calls, reads, writes, source locations and visible recovery metadata; uncovered syntax errors and unresolved compilation context remain incomplete. Correct reference-return declaration indexing without treating function-pointer variables as functions. Keep unresolved declaration bindings visibly incomplete and retain their locations through the existing Map store.
- Patch classification: these changes correct existing dependency, parsing and analysis-cost contracts. No new public command, language, required input field, runtime compiler or workflow was added. Historical tags and releases are unchanged.

## v2.1.0 - 2026-11-06 - Read common languages and check connected decisions

- Generate Python, JavaScript/TypeScript/TSX, C/C++ and C# source facts in the same Map, SQLite store and fixed queries. Ship the first grammar readers with the engine and load them only for their language. Preserve Python symbol identities; show foreign parse coverage and unresolved bindings explicitly.
- Track parser versions and relevant project configuration when invalidating maps. Keep overloads, macros, dynamic dispatch and incomplete compilation context distinct from uniquely resolved static targets. Foreign maps support navigation and structure constraints; native home execution remains Python-only.
- Make unsupported or failed source queries grey in structure checks instead of treating their empty result as proof of absence. A structure predicate that queries no source facts does not verify the code structure.
- Check the actual joint combinations of verified lower-rule partitions, including three lower decisions, rather than accepting only separate pair witnesses. Report the finite declared domain or partition representatives actually checked.
- Follow reachable test dependencies and real pytest collection settings for affected checks. Retain unknown dynamic, environment and external inputs conservatively; production functions with test-like names are not collected as tests merely because their names match.
- Retire obsolete failed node IDs only after a successful complete collection and execution of that test file. Preserve raw history, newer partial failures, incomplete collection and unresolved input boundaries.

## v2.0.0 - 2026-11-06 - Keep one owner for a decision

- Find existing decision sites, constants, callers and similar implementations from a generated Python map before adding another copy. Candidates are leads to inspect, not claims of semantic equivalence.
- Write an executable rule only for necessary copies, an explicit everywhere requirement or a fixed bug. Bind each real implementation through a small adapter, retain literal regression rows and cite original owner words or an agreed document.
- Compare rules and real code over complete supported cells, including supported linear expressions. Check that the declared inputs constrain the actual decision sites; show unverified boundaries as grey.
- Reuse results only while their source, helpers, data and authority remain current. Preserve applicable rows across replacements and detect missing marked guards. Content-checked project imports prevent same-size edits within one timestamp from executing stale bytecode.
- Use ordinary pytest for both intent and project tests. `check --all` establishes complete test-to-code links; affected checks refresh selected tests. Direct ordinary pytest traces explicit guards. Retain the observations required for reliable selection and report their cost.
- Include pytest in the normal engine installation, and ship one local rule guide with the skill: a complete executable example and its input/source boundaries. The first rule does not depend on retrieving a web page.
- Read a short screen without running the application or tests. Inspect a rule, function, request or candidate through `show`; use `init` for the sentinel, project rules and CI fragment.
- Retire the 1.x flow machines, native recorder, background jobs, pictures and separate release test runner. The old `status`, `where`, top-level `draft`, `decide` and `release` commands have no aliases. Keep the original request archive and migrate useful contracts into rules, rows and ordinary tests; see `docs/upgrade-2.0.md`.
- Publish only the main commit whose complete CI passed on Linux Python 3.11/3.13 and Windows Python 3.12. Package the current engine and the single small skill without retired runtime resources.

## v1.4.0 - 2026-11-05 - Affected checks and reusable current evidence

Restoring missing check records keeps their valid recorded decisions.

Native path walks start only after construction and inventory checks conform.

Recorded test evidence is stored compactly and shared losslessly between its conflicts.

- Ordinary checks compare changed native operations and record a bounded seeded walk of the affected main model. Existing saved-start checks retain their own scope.
- Mixed code and physical-input changes retain every affected operation; later data changes still invalidate a partial code-only result.
- Current completed parts and full-check recipes are reused across repeats and resumes. Retained conflicts still need complete original-scope proof and an executed regression to close.
- Changed code selects statically related tests; removed or renamed imports and property getter/setter helpers remain in scope. Unicode source and test paths keep their actual Git filenames.
- Known unreached findings retain their earlier setting-explanation attribution; new findings still get a fresh setting search.

## v1.3.0 - 2026-11-05 - Check actual old saved inputs

- Declare saved files on an existing code-bound model. The real program loads unchanged JSON, SQLite or migration fixtures through the same native recorder; model loading does not execute the sample loader.
- Compare distinct object states and supported pairs, retaining file versions, exact bytes and original object identities. Missing samples remain explicitly unchecked; unsupported relations and unavailable evidence remain UNKNOWN.
- Report actual file-load crashes and model/code drift. A repair checks the original saved input and executes its regression before closing the retained conflict.
- Show compact saved-input coverage while keeping full records private. Preserve current draft, composition, source-loading and owner-history behavior.

## v1.2.0 - 2026-11-05 - Start models from existing Python code

New adapter drafts include statically known source base classes.

- Read a Python file, class or method for static names, signatures, candidate values and settings references without executing the project.
- Create model and adapter TODO files once. Complete expected behavior from the requests, connect real calls through the existing adapter and inspect actual model/code differences; completed author files are never overwritten.

## v1.1.0 - 2026-11-05 - Compose feature models

- Compose existing feature models with shared object identities. Calls between features share one step, preserve ordinary action updates and original guards and requests, and commit effects only when every participant accepts.
- Keep one declared owner for a shared field. Read other features through explicit views; reject conflicting effects instead of choosing one silently.
- Show the declared composition boundary in check and picture results. Full checks qualify projection and renaming against the complete finite model; an optional next-size builder compares one additional object without claiming arbitrary-size correctness.
- Load current project helpers through the same source loader for ordinary models and next-size builders. Preserve actual source dependencies, failed imports and the caller's module identities.

## v1.0.0 - 2026-11-05 - One executable model engine

- Use one executable feature-model engine connected to real code, owner words and tests. Retire the old map/model/target and experimental pilot APIs, with an explicit migration guide.
- Preserve request bytes and conflict scope across sessions. Require actual current evidence for repairs and original owner words for replacement requirements.
- Keep static source, caller, architecture and original-text queries available during migration. Shard ordinary tests by their actual source tree without a hand-maintained map.
- Report the release's actual test scope, unfinished observations and surviving deliberate breakages. Existing adoption files keep their original bytes and receive actionable upgrade notices.

## v0.75.0 - 2026-11-05 - Real-code checks and lasting conflict records

Model-only findings are checked against the owner's words and actual code before recommending a repair.

Complete finite evidence uses compact storage without dropping cases or scope.

Local variables are not mistaken for module configuration.

Native capture preserves source-bound function dispatch.

Corrected model coverage can resolve its original conflict after complete native checks and an executed regression; real code differences remain open.

Unchanged source-bound predicates remain recognizable after a model route repair, without claiming that the real code was checked.

Repeated retained model facts share plan storage without dropping the original cases.

Missing model results stay visible after a partial check. Native comparisons keep actual global reads and writes separate from unrelated same-named attributes.

- Bind a flow model to real code once. Ordinary checks compare construction and a small operation witness set; full checks add a recorded seeded walk. Mismatches show their actual inputs and can be drawn from existing evidence.
- Conflicts keep their first scope and promises. Removing a start or weakening a sourced promise does not silently close one. A verified repair writes and executes a regression; implemented replacement requirements retain their original owner authority and are named separately from code fixes.
- Status refreshes changed models and puts unresolved questions first. Owner decisions require relevant live original words; provisional decisions apply only to genuinely conflicting requested rules. Read-only staged checks permit finished UNKNOWN and keep it visible.
- Explicitly selected pytest tests can audit fallback routes using their real execution and private disable probes. Reports distinguish a masked primary failure, two active routes, visible failure and finite unreached counts; ordinary checks never start the project suite.
- Static source queries join model declarations, sourced rules, open conflicts and actual Request commit lines without executing project code.

## v0.74.0 - 2026-11-04 - Model-first work and Windows flow checks

Flow explanations include the rendered diagram in the reply.

- Flow changes update the affected feature model before code; flow discussions use its pictures. The short skill describes how to resolve compatible requests and distinguish a temporary requirement choice from a dead end that still needs a code fix.
- Flow checks, pictures and release checks run on Linux and Windows through the same model engine. Waiting, resuming, caller death and expired background work retain their existing meanings. macOS flow execution remains unsupported.
- Request quotations prefer substantive words over Markdown headings. Status explains that CI blocks a release only when it runs the release check; a commit is blocked only by an installed hook.
- A caller waiting on work replaced by a newer model reports that replacement, even when the new worker finishes quickly.

## v0.73.0 - 2026-11-04 - Flow models, concrete conflicts and bounded checks

- Flow models: write the part of the design a change touches as a small model in `.flowguard/flow/<name>.py`, one model per file, importing `from flowguard.flow import Model, need`. The short guide is `flowguard/flow/HOWTO.md`, which the installed package carries too.
- `python -m flowguard check` tries every action of every flow model in every reachable state. It reports conflicts (something that gets stuck, an action, option, end or promise that is never reached, a promise some order breaks, an option offered where its action refuses, a second route to the same result) with the shortest path and the requests behind each, then model warnings, and what a capped search left UNKNOWN.
- The first line of `check` is the verdict. It exits 0 when clean, 1 on a conflict, 2 on a model error, 3 when only UNKNOWN is left, and 4 while work is still running. `--json` prints one line.
- A model that covers code and gives a setting its own value, where the covered code's settings object has that setting, is a model error that names both values (`settings not read from the code: maintain_every=3 (code default 4)`); read it with `config=` instead. Writing into `m.settings` is a model error too: declare settings with `m.setting`.
- To try an intentional setting change before changing the code, use `m.setting("limit", 2, propose=True, source="R12")`. `check` reports the proposed and code values as advisory; `release` fails while they differ, and `status` shows the proposal until the code and model agree.
- A tuple of per-id values in the declared order of interchangeable ids that is written into a field (directly, through a name, a helper or a starred display) now turns the renaming off, as comparing it as a whole already did: a rule or guard that read the stored tuple could tell the ids apart, and the reduced search reported clean.
- A bounded clock or counter no longer makes a dead end at its last value when its counting step works in every reachable non-end counter context, even if that step also changes other fields. A day that always advances until its limit is such a clock; a use count whose `rent` step requires a rentable object is still judged, even if another action can cycle. A number used as a status that some step sets back to another value is still judged. A value declared with `m.terminal` that some step leaves is a model error with the path to that step.
- `check` returns within `--wait` seconds (90 by default). Work still running continues for `--keep` seconds, and the same command resumes it.
- `check --full` also breaks each model on purpose and lists the breaks no check catches, and explores a model with interchangeable ids once more without renaming them. When some breaks are not caught, the first line counts them (`clean, complete; 4 deliberate breakages not caught - see below`, also after the conflicts of a complete check) instead of a bare `clean`. The release summary repeats the count and says when tests were not run. Full checks keep a clean ordinary check's committed conflict record unchanged.
- A `source=` that names no stored request is a model warning that says which part of the model names it and how to store the owner's words with `req add`. Storing the request ends the warning at the next `check`, with no change to the model. The guide says to store requests with `req add` (never by writing a file in `.flowguard/requests/`), to commit `.flowguard/conflicts.json`, and that `release` checks the flow models without a legacy map.
- Conflicts are recorded in `.flowguard/conflicts.json`; commit it. A conflict stays open until a complete check of its model no longer finds it.
- `python -m flowguard show` draws the conflicts, or else the change against HEAD, as a flowchart: Mermaid text, plus SVG and PNG pictures where node with Playwright is installed.
- `status` shows the flow models' open conflicts and says what they stop: release and CI fail until they are fixed; without a hook a commit is not blocked.
- A STUCK conflict names every value its object is stuck in (`T1 stuck in cond='repair', branch='library'`). `show` uses the same concrete subject in its first line and JSON; `subject_id` keeps the stable conflict ID. It counts states the way `check` does (every renaming, and how many up to renaming), lists as too big only the views that are, exits 2 when it draws nothing, draws a broken promise's red path unbroken into its last box, and gives the arrows of the drawn view before the whole model's step count. The progress line names the work after the search (finding what gets stuck, explaining with one-setting changes, verifying the renaming, deliberate breakage k of n), with live state counts during each deliberate breakage.
- `release` runs the full check of the flow models after the legacy models, and fails on a conflict or a model error. A project with flow models and no legacy map gets the same flow check, and its whole test suite with `--shards`; the first line says that no legacy map exists.
- When `.flowguard/conflicts.json` cannot be read (damaged, or left with git merge markers), `check`, `show` and `release` stop with one line that names the file and the step that restores it, exit 2. Recovery advice uses Git only for a tracked record; otherwise it asks for the project backup and preserves the damaged file. Any other unexpected error in these commands is one `internal error:` line, also exit 2: exit 1 always means a conflict.
- The v0.73 flow engine supports Linux only. Windows keeps the legacy commands; flow `check`, `show` and the flow part of `release` exit 2 with an explanation. `status` still shows stored conflicts and the limitation. Full Windows flow support follows in the next stage.
- A flow-model symlink that resolves outside the project currently exits 2 with `internal error: ValueError ... is not in the subpath` in `flow/jobs.py`. An otherwise in-project model can read a data file through an external symlink; the direct-read probe completes.
- Immutable request/change-record path handling rejects an external symlink with `immutable file must be inside the project` in `map/records.py`. An already-present request ID may instead be rejected earlier as `request_exists`.

## v0.72.0 - 2026-11-02 - A plain change flow, the owner's newest words and honest Git checks

- A normal change no longer needs the legacy map, models or target commands. Run `status`, store the owner's words with `req add`, find code with `where`, run your tests, and commit in your own words with a `Request: R<n>` line.
- The README's five-minute start, the skill and the adoption rules teach only this flow.
- `template adoption --write` writes the rules into a missing AGENTS.md and never edits an existing one. When an existing AGENTS.md already holds the current rules, it says so and asks for nothing, unless an earlier FlowGuard block between the `BEGIN`/`END FLOWGUARD PROJECT RULES` markers is still there: then it names that block by its line range for removal. Otherwise it prints the rules to put there in place of any earlier FlowGuard rules and names those lines: an earlier marked block whole by its line range, other lines that look like earlier rules by number (a FlowGuard heading only when such rules follow it). It no longer writes `docs/flowguard_agents_rules.md` or a CLAUDE.md whose `@AGENTS.md` names a missing file.
- The concept guide and the skill pages about the map, models and targets say at the top that they are legacy and optional.
- `map check`, `release` and `change --run` no longer fail because the legacy map is behind the code. Unowned files, stale or draft descriptions, dependency mismatches, unmodeled entrypoints and models edited in place are shown as information.
- Import cycles, layer violations, broken anchors and files with two owners are still errors.
- `status` shows the owner's three newest messages, lists older ones by ID, and names the change records and `Request: R<n>` commits that cite them.
- `status` no longer shows requests as open or done, and prints `NEXT` only when a step is pending.
- `req add --supersedes ID` marks an earlier message as replaced.
- `req retire ID --not-owner` records once that a stored text is not the owner's words. That text stays out of the owner's words in every copy, and linking or quoting it is refused.
- When a retire record cannot be checked, cannot be read, was edited or was deleted, `status` says so in one line and names the step that restores a damaged one. In a project with the legacy map, `map check` reports it too.
- Owner text, or the details stored beside it in `.flowguard/requests/<id>.json`, edited after it was stored is marked as edited in `status` and `where` with the step that restores it, never shown as the owner's words. Only a file that cannot be read is called unreadable.
- Without `--root`, every command works on the nearest folder at or above the current one that holds `.flowguard/`. A command run from a subdirectory no longer creates a `.flowguard/` folder there.
- In a Claude Code session, the first FlowGuard command shows `status` once, also through `python -m flowguard.map`.
- `status` warns when the installed skill names another FlowGuard version or none.
- A copy of a project without `.git`, or a moved folder, no longer reports unchanged requests or change records as edited. Files that cannot be checked there are listed once as information, and linking or quoting such a request is refused.
- Once a request or change record is committed, every clone checks it against its first commit and gives the same answer.
- In a folder without Git, fix advice no longer suggests Git commands, and `status`, `map check`, `where` and `change` work without Git installed.
- When Git fails inside a repository, FlowGuard stops with Git's own message instead of acting as if there were no Git, no history or no file. This covers a damaged index, a missing commit, tree or file object, a broken branch, a repository owned by another user and a checkout whose repository is set to bare.
- FlowGuard names the cause instead of guessing when Git is not installed for a repository, or when `map.json`, a change record, an open target, or the `pyproject.toml` a version-dated debt needs cannot be read.
- `release` saves no release snapshot while a change record cannot be read.
- Models run from a source checkout that cannot create a symbolic link stop with a plain error.
- Legacy targets: every changed rule needs a `changes:` line in PLAN.txt that quotes the owner's words or gives your reason.
- Legacy targets: with Git, only a change to one of a model's anchor functions closes its gap, and the gap line lists the other changed code in its anchor files. Without Git, the gap line says that only whole-file facts exist.
- Legacy targets: any change in an anchor file still runs the model's bound tests.
- Legacy targets: map-upkeep findings are information, as in `map check`. Promotion confirms the target's own component descriptions, so they are not stale or draft afterwards.
- Legacy targets: a target that only holds a component whose description went stale is promoted, not treated as empty. An empty target prints a step that drops it.
- Legacy targets: `target check`, `target promote` and `status` stop and name `base.json` when it cannot be read.
- Legacy targets: the `target check` summary no longer counts a NO GAP line as a warning. A target that only copied a model or component says it changes nothing yet and names the copy, instead of counting it as a changed node.
- Every next step that `status` and the legacy target commands print runs as printed. After following them from a new target to the commit, `map check` and `release` show none of the target's components as stale or draft.
- Promotion prints one staging command that includes new source files without an owner, and `status` repeats it until you commit. If Git cannot list the files, promotion stops before changing anything.
- A promotion refused because a model or test failed prints `target promote` again, not `target check`.
- Promotion no longer writes a commit message file; you commit in your own words. `#` notes in PLAN.txt are kept in the change record.
- `req add` points to `status` instead of starting a target.
- `where` prints its next steps as `next[where]: ...` lines. In every view, `where --json` lists them in `next` as the `{id, command}` objects the other commands use. The overview no longer shows placeholder commands.
- `where` prints the most relevant rows of each list and says how many it left out. `--all` prints every row, also with `--json`.
- `where` no longer prints fixed disclaimer lines, `--arch` lists the largest modules first, and a name query also finds equal string literals with their function.
- Repeating a `where` query is much faster: in a project with `.flowguard/`, parse results are cached by file content in the git-ignored `.flowguard/cache/`.
- `map lint` reports an accepted debt for a review suggestion that can no longer arise as `debt_stale`, so you can remove it.
- The installed package no longer contains the unreleased behavior engine (`python -m flowguard.behave`). It stays in the source repository.

## v0.71.1 - 2026-11-01 - Static source and original-text queries

- Add optional, read-only `where` queries for names, owners and callers, module overviews, static flows, architecture, shared state and file destinations. Queries do not run application code, models or tests; missing execution records remain explicit.
- Add compact text and source-reference summaries with file, original-passage, group and literal-phrase selectors. Preserve original text and available Git provenance, and inspect text and code at the same revision with `--at`. Literal and workflow matches remain candidates for review.
- Give executable next-query commands and show source-backed helper-boundary suggestions from resolved calls. Responsibility counts no longer stand in for cohesion; suggestions remain non-gating advice.
- Improve the shared source index for constant and annotated assignments, complete references, command-handler bindings and field lifecycle facts without creating a second index.
- Clean up owned child processes after an interrupted check while preserving the interrupt and leaving unrelated processes alone.
- Keep Python 3.11 support, the existing model workflow, 64 public exports and the current map format.
- This release added the `where` command, so by the project's own rule it should have been a minor version (v0.72.0). Its tag stays as published.

## v0.71.0 - 2026-10-31 - Model-linked plans, original requests and runnable next steps

- Add read-only static status for resuming open plans, viewing unclaimed requests with their original context, and following one absolute next command. Hook mode stays silent outside a project; the legacy runtime does not store verdicts or start jobs.
- Store requests byte for byte with req add, explicit or collision-resistant IDs, immutable sidecars and optional glossary/adoption kinds. Checks protect request, metadata and change-record bytes before their first commit, in fresh clones and when a plain folder becomes a Git worktree; deleted requests remain discoverable and their IDs cannot be reused.
- Link requests to targets with --request ID[:part]. Read and status derive request state from active worktrees and complete immutable promotion records without rewriting owner text or metadata; requests stored during a change retain their real origin.
- Require an explicit PLAN.txt request quote or reason for a changed existing rule that shows NO GAP. Quotes must match stored owner text and a rule term, including confirmed glossary mappings; planned function touches require a real code change.
- Write immutable promotion records with checked PLAN lines, model rule fingerprints and their owner or reason. Any printed owner block includes readable old and new rules and used glossary entries, and is preserved in the commit message and JSON output.
- Successful releases without Git preserve original-byte and release-boundary facts so deleting disposable cache does not erase protection or request history.
- Make next-step guidance executable from any directory with absolute project paths and stable next[<id>] advice IDs. Manual repair and model-binding instructions remain in notes; requests without a map first point to the real map scan command.
- Promotion prints an absolute staging command for reviewed code, models, map, requests, records and target deletions, followed by commit -F with the real message file. Without Git it keeps preservation guidance and an executable verification step.
- --json on map check, map lint, target check, target promote and release emits exactly one JSON object containing command, verdict, codes and next; map check and lint retain their counts and findings.
- Refresh adoption rules and the documented workflow to start and resume with status, inspect the task's existing owners and executable models, preserve requests as received, name PLAN touch points and the four legal target-check exits, and quote an actually printed owner block unchanged. The template adds CLAUDE.md with @AGENTS.md only when missing, preserves existing instructions even with --force, and the skill names the other Guard skills' scope.
- Target promotion rejects model failures caused by changed shared source, as release does, and names that source; only genuinely unchanged findings remain old warnings.
- A selected test without a command names the project's test_commands setting and gives a runnable promotion command after it is declared.
- Editing a current model or helper while its target copy exists is an error; promotion refuses to overwrite the edit and points to both files. New targets also protect helper additions and deletions; older targets with an unknown helper baseline ask you to preserve both versions and reopen safely.
- Strict checks and release reject committed targets that are already promoted and target files deleted without staging; open targets remain a release warning, and Gitless no-op targets only warn.
- Rewording a component responsibility is responsibility_reworded advice rather than owner_dropped.
- Accepted debts need a nonempty reason and an explicit date or project-version expiry. Expired debts restore their findings and review suggestions; strict checks and release reject them, and map lint --debts shows their deadlines.
- large_file, large_component, too_many_responsibilities and high_fan_out are info advice. An accepted debt for one of them now matches nothing and is reported debt_stale.
- Lint defers sequence-size debts to model execution instead of falsely calling them unused; models and release warn when an observed size debt no longer suppresses any finding.
- Model and bound-test subprocesses import the project's own packages first (the project root, import_roots and src/) and see FlowGuard's package without its repository root.
- Literal spelling hints state that no producer was found among statically recognized literal sites and ask readers to check indirect producers too.
- Release checks reuse the project inventory when verifying models instead of building it again.

## v0.70.14 - 2026-10-28 - Ports reach consumers, phase-aware checks and a complete read

- Projects using FlowGuard: release, map models, target check and target promote run models in parallel by default; --jobs 1 stays serial in the calling thread.
- Reuse read-only syntax, component file matches and model trees within a command; model subprocesses receive parsed ports and locations without rebuilding the project inventory.
- Projects using FlowGuard: a changed output that an escalated consumer never receives is an error, and target promotion refuses it.
- Projects using FlowGuard: after code changes, target check names open or closed gaps and runs the target models’ own bound tests; a missing anchor no longer claims conformance ran.
- Projects using FlowGuard: when a child adds a received parent value, target check names siblings that start from those states without reading the changed field.
- Projects using FlowGuard: changing the stored fingerprint formula without updating its format produces a warning; ordinary version bumps remain neutral.
- Check the model scheduler with one real fixture and group models above the timing advice in one counted line per advice value.
- Projects using FlowGuard: accepted debts are counted once and remain listed by map lint --debts; change --verbose shows exact test commands while normal change gives a counted summary.
- Projects using FlowGuard: read and map show print complete views without --budget; every component and model is named, with child models folded into their parent. Target component views show each related model once.
- Projects using FlowGuard: removed literals name code sites first; moved values stay quiet and settings-only map edits select only newly mapped tests.
- Projects using FlowGuard: a helper edit selects a flow model when the helper lies on the static path between its steps; direct callers remain selected.
- Projects using FlowGuard: replay_call_undeclared warns when a model replays an unanchored product function and prints the needed USES declaration. Storing callbacks in tuple assignments does not claim they ran.
- Rule identity follows the literal entries used by shared helpers, so adding an unused entry does not change an unrelated rule.
- Command help shows the real argparse options; word lookup prioritizes the model owning a matching symbol, and unowned code suggestions show each model’s full purpose.
- Projects using FlowGuard: template cases creates a named case table, a real-function replay and matching tests. Hub views show callers as well as lenders.
- Skip repeated path classification within each model audit while keeping every watched anchor checked.
- Projects using FlowGuard: model and test subprocesses preserve existing PYTHONPATH entries and project script namespaces when running from a source checkout.
- Check skill routes for duplicated paragraphs, broken links and missing command names; report text size without rejecting useful content.

## v0.70.13 - 2026-10-27 - Model ports and a smaller workflow

- Check finite values passed between models, exclusive stages, dispatch branches and shared consumers; name the parent or consumer that must handle a changed port.
- Keep current models intact while designing a target. Report real code gaps, moved rules and existing behavior separately; run bound tests in the complete promotion check and promote checked bytes safely.
- Select changed functions and their bound or directly calling tests. Explain removed literals and promises, preserve Git's timestamp checks and keep unrelated checks out of a small edit.
- Read owners by words, exact symbols, source locations or test locations; inspect field lifecycles, code coverage and model rules without importing a model.
- Show placement, composition and consumption separately, with coverage counts, shared-model hubs and the impact of port changes.
- Enforce model and test size limits while treating elapsed time as advice. Keep tests beside their model subtrees and balance complete release shards using verified test durations.
- Run fresh model checks with explicit concurrency and stable output order; passing proofs stay concise and failed checks retain their evidence, and nested runners keep separate control and receipt paths.
- Keep the public API to 64 supported names, remove unused modules and retain the complete shard toolchain, validator and UI-flow support.
- Organize the self-models and shelf example around real stages, alternatives and independently shared behavior, with real code and test bindings.
- Teach twelve concepts, one development loop and task-specific routes in the shorter skill; install matching project rules and focused node-kind recipes.
- Avoid repeated static trees, unused constructor scans and deep AST copies while preserving source facts, body fingerprints and rule diagnostics.
- Version-only changes no longer invalidate confirmed component fingerprints.
- Projects using FlowGuard: run `python -m flowguard map confirm <component>` once after upgrading (`fingerprint_migrate` names it); `fingerprint_migrate` is removed in 0.70.14.

## v0.70.12 - 2026-10-24 - The model shows the architecture

### New

- `python -m flowguard read --review` (also `map show --review`) shows per-component metrics, strengths, defects and a ranked list of what to optimise next, each with its recipe.
- `python -m flowguard read --budget N` sets the character budget, like `map show --budget`.
- `read --component` shows `relies on:` lines (the models and rules whose anchored code this component calls directly) and the flows the component takes part in, with each flow's model and rules.
- `change` also selects the models whose anchors a changed file calls directly, a flow's model when any step's file changes, and lists unexplained entrypoints and state writers in the files you changed (`UNEXPLAINED`).
- `python -m flowguard change --run` runs the tests and models that `change` selects and prints one PASS/FAIL line for each.
- A flow step can be written `component:Symbol reads <file>` for a command that reads a file an earlier step wrote; such steps are checked as command entrypoints instead of static call reach (`flow_handoff_invalid`, `flow_handoff_not_entrypoint`).
- `map lint` reports `flow_unmodeled` (info) for a flow that crosses modeled code without a model, warns `private_cross_component_use` when a component uses another component's `_private` name, and notes responsibilities that pack several duties (`responsibility_compound`, info).
- `target check` refuses a target that changes nothing (`target_noop`) and a new or changed entrypoint, state or side effect without a new or changed model rule or known-bad variant (`target_goal_untied`); it prints the target's goal rules.
- `target check` reports problems of related models that the target does not change and whose code is unchanged as `old_finding` warnings, and warns about accepted debts the target makes stale (`debt_stale`); `target promote` lists models, flows and tests to re-read.
- `read --find` matches common word forms (expire/expired, rotate/rotation) and, when nothing matches, names the three closest owners.
- `map models <id> --hazards` lists every open and closed hazard hint.
- `validator`: `execute_contract_features(..., rejects=...)` names the exception types that count as a rejection (default `ValueError`, `TypeError`).
- `examples/shelf/` shows a small model tree with a current model, a target and the code after the change.

### Changed

- `read --component` always shows the component you asked for; long lists inside it are shortened with `+N more` instead of hiding the whole component.
- `read` shows the real rule names and descriptions of models whose invariants live in a `_helper` module or are built by a small wrapper function, the rules, known-bad variants and defect/benign cases of feature-kit models, and known-bad variants built by loops or comprehensions; it no longer shows `TESTED_BY` keys as rules. A parent model shows the tests its child models bind.
- `read` lists components top-down by layer; `read --target` no longer repeats computed coverage text as a change.
- The coverage line counts explanations by model, test and `NOT_MODELED` reason; the tests facet suggests unbound tests that already mention a model's anchor.
- The `read` header counts size and test warnings and every accepted debt that covers one.
- `change` selects a child model that imports its parent inside a function (the documented split style) when the parent changes.
- Dependencies passed in through a constructor (a type-annotated parameter, or the same class passed at every call site) count as real dependencies: `dep_unused` no longer fires for them, `map deps --write` keeps them, and effect reach and `foreign_state_write` see through them.
- `map check` and `change` report `duplicate_owner` every day, not only `map lint` and `release`.
- Hazard hints match whole words, are deduplicated, show at most three open hints per model plus one summary line, and close themselves when a known-bad variant or an invariant already covers them.
- A target that drops a responsibility without a new owner or an explicit `responsibility:` retirement in `remove` fails `target check` with `owner_dropped`.
- With a target, only breakage of the field the target actually changes is reported as `moving to target`; other breakage of a copied component stays an error.
- `map models` fails a model whose invariant no known-bad variant breaks, like `release` and `target check`; the message no longer suggests an explanation mechanism that does not exist.
- `validator`: a bad case may have any name (it must be rejected unless a built-in default says otherwise); an exception other than the rejection types is reported as a crash.
- First-map and hint wording: the no-map error names `python -m flowguard map scan` and the first-map guide; `scan` hints splits for large one-directory drafts; `discover` says when it finds nothing; digests list overloads once; removal targets hint deletion for unowned files.
- The skill starts from the model (`## Start from the model`), states the real PARENT placement rule, lists tasks instead of former capability names and says that `release` and `map models --tests` need pytest.
- FlowGuard's own tree: 22 components (the map-analysis hub is split into map-check, map-read and map-impact; one present-tense duty per responsibility, at most seven per component), 18 release models including `system` (new domain models `tree_resolution`, `map_binding`, `discovery`, `target_findings`, `target_promotion`, `job_matching_example`), four model-under-model edges, five flows that are each one command's call chain, every entrypoint and state writer explained, `map lint` with no warning (four reasoned accepted debts). `len(flowguard.__all__)` stays 105.

### Removed

- Dead code: `flowguard/_hashing.py`, `model_files` / `model_id_of` in `flowguard.map.proof`, the dead `model-test` template alias.
- `release --shards` no longer writes `claim_boundary`, `capability_partition` or `symlink_probe`; the unused `flowguard_capability` pytest marker and `flowguard.symlink_capability` are removed.
- The unused adoption-log and model-notes template texts.

### Effects on projects that use FlowGuard

- `read --component` on a large component (for example PhysicsGuard `simulation`) now prints it.
- Rule counts in `read` may change; `(from TESTED_BY)` is gone; known-bad variants built by a loop or a tuple comprehension now show their names instead of `?`.
- Feature-kit models now show their counts in `read`.
- Projects may see more `entrypoint_unmodeled` / `foreign_state_write` warnings and fewer `dep_unused` errors.
- Command-chain flows (LogicWriting, ResearchGuard) can use `reads` steps to clear `flow_step_unreached`.
- New `private_cross_component_use` lint warnings at the current HEADs: PhysicsGuard 3, ResearchGuard 9, WorldGuard 10, LogicWriting 0.
- `map check` (and CI) fails when two components claim the same responsibility, state or side effect; no project has one today.
- Far fewer hazard lines per model (at most three open hints plus one summary line; no `+N more`).
- The coverage line format changes (tools that parse it must read the new form).
- The first `read` line now also prints a warning count.
- `map models` exits 1 for a model with an uncovered invariant (all four projects have none at their current HEADs).
- None of the four projects uses `flowguard.validator` today.
- None of the four projects uses the removed names (`flowguard._hashing`, `flowguard.symlink_capability`, the shard `claim_boundary` / `capability_partition` / `symlink_probe` keys, the `flowguard_capability` marker, the adoption-log and model-notes texts; checked by grep).
- `map lint` adds the `responsibility_compound` note (info, never blocks) for long or `;`-joined responsibilities: PhysicsGuard 24, ResearchGuard 25, WorldGuard 14, LogicWriting 15 at their current HEADs.
- A target that changes nothing now fails `target check`, and a target that changes an entrypoint, state or side effect must add or change a model rule or known-bad variant; name that rule in the target goal.

## v0.70.11 - 2026-10-24 - One model tree for current and target work

### New

- Plan changes beside the current tree with `target start`, `add`, `check`, `promote` and `drop`. Target checks use fresh code facts, model proofs and bound tests without writing project files or caches. Design mistakes are ERROR; code and tests still needed are TO-DO. Promotion requires a clean complete check and unchanged checked inputs, writes the prepared map and model bytes, and lists components to confirm.
- Read a target as an overlay with `read --target` or `read --mermaid --target`. Added, changed and removed nodes retain stable identities; focused views show previous values of changed facets. `read` names an unfinished target while current checks keep using the current tree.
- Project, component and model views share purpose, rules, known-bad cases, code and tests. Rule counts appear in overview and Mermaid labels; focused tests show bound, unbound and nonnested links. These views read static source without importing user models. `map models` and `release` also print real rule and known-bad names, abbreviating long text lists while preserving complete results.
- Components may name a same-layer `parent` sub-system. Views indent and roll up children, Mermaid nests them, and impact selection retains explicit old and new sub-system protections when a child moves. Direct file ownership and fingerprints are unchanged. Unknown parents, parent cycles and cross-layer parents are errors.
- Dependency views name the symbols actually used; Mermaid draws dependencies and ordered flows, marking flows without models. Coverage reports how much declared behaviour is explained by model anchors, matched tests or reasoned exclusions. Structural `hazard:` hints are derived automatically; hints and inference failures never change PASS/FAIL or release.
- FlowGuard's own tree now has 20 components, 14 release models including `system`, five modeled flows and two model-child relationships: `model_proof` → `test_binding`, and `target_life_cycle` → `target_findings`. Finite native conformance and bound tests cover tree placement, static read output, first-map source ownership, target promotion and finding classification.
- Focused validation, UI, structural hints, closure, test sharding and symlink-capability implementations total 3,417 lines, compared with 37,222 lines in the retired capability engines.

### Changed

- Model starters are `behaviour`, `validator`, `ui-journey` and `adoption`. With an active target, model starters write to `.flowguard/target/models/`; normal overwrite protection and explicit `--force` remain. The ordinary behaviour starter is packaged with the engine. The `ui-flow` and `contract-exhaustion` aliases select the corresponding new node kinds.
- Validators preserve finite bad-case generation, bounded combinations, stable case IDs and execution against the real function. Default input/payload mutations include old schema versions and conflicting identities. UI journeys preserve automatic failure recovery, destructive-action confirmation, dialog closure and usable reachability; eight groups of manual UI review questions remain in the recipe.
- Model nesting uses the map tree. `child_outside_parent`, `duplicate_child_owner` and `parent_import_mismatch` are errors. `child_start_gap` applies only when a child declares `project_parent_state`; independent checks grouped under a parent avoid the false warning. `flowguard.closure` supplies a parent `closure_invariant`, preserving token consumption, complete joins, reachable normal exits and loop-progress guards.
- Target removal protects every entrypoint, state and side effect with `owner_dropped`; explicit `entrypoint:`, `state:` and `side_effect:` removals record deliberate retirement. Removal intent does not delete extra content. Future child anchors inside their component's declared files remain code TO-DO. While a target exists, `change` reports its static work and marks only replaced-node breakage as `moving to target`; unplanned breakage stays an error, and `release` warns about the unfinished target while checking the current tree.
- A rule without a `TESTED_BY` key produces the informational `invariant_untested` warning. It neither gates release nor proves assertion strength. A binding may select an exact `test_name[param-id]`; a function binding still runs every parameter case. Failed bound tests, missed anchor reach, invalid design proofs and uncovered required known-bad invariants continue to block release.
- `release --shards N` runs the whole suite after normal checks and bound tests pass; failed prechecks skip it. Every collected ID runs exactly once within the shard-suite phase, whose tests may overlap the earlier bound-test phase. Without `--shards`, the whole suite remains optional. Shard JSON uses `scope`.
- The lazy top-level API contains 105 core names. Import node-kind classes, benchmark helpers and dedicated tools from their provider modules; the original 19 consumer import paths remain supported. `Explorer`, feature kits, projection helpers and `reachable_states` remain available. Change selection reads removed contracts from Git history without running old code, retaining surviving parents, importers and tests, supporting same-ID moves and rejecting dangling references.

### Removed

- Separate architecture-reduction, code-structure, field-lifecycle, behavior-commitment, primary-path, model-mesh, model-test-alignment, topology-hazard and contract-exhaustion engines, their duplicate review/coverage/confidence structures and retired starters. Their retained behaviour lives in tree operations, ordinary models, node kinds, computed facets and recipes. Duplicate partition-map reviews, out-of-scope rationale-only gates, the static assertion audit and the behavior ledger reader are gone.
- Alternative plan, runner, audit, risk and report frameworks: `flowguard.plan`, `flowguard.runner`, `flowguard.formal_runner`, `flowguard.summary_report`, `flowguard.audit`, `flowguard.risk`, `flowguard.risk_templates`, `flowguard.template_packs`, `flowguard._evidence_status`, `flowguard.model_path_quality`, `flowguard.state_closure` and `flowguard.step_contracts`. `map models` is the one model runner; loop, progress, contract, scenario, minimization and bounded exploration helpers remain usable in conformance or tests. `flowguard.kit.plan_explorer`, `review_invariant` and `PlanState` are removed; feature kits and reachable-state exploration remain.
- Planned-code fact exemptions are removed; code facts must inspect real source.
- Finding-ledger and maintenance-obligation memory APIs, including their report types, status/confidence constants and coercion/build helpers. Record planned work in a target and a known unfixed architecture issue in `accepted_debts` with a reason. Old integration guides, the acceptance report and completed roadmap are removed; mathematical examples, benchmarks, budgeted exploration and conformance documentation remain.

### Upgrade

- Follow [the upgrade guide](.agents/skills/flowguard/references/upgrade.md). Use one entry flow: read first, then target first for behaviour or structure changes, or edit directly for code-only changes. Recipes and node templates replace the old capability-specific protocols.
- Use target removal/merge or add/split operations to preserve public promises. Rename or retire fields with target model state and real `CodeFacts.absent` / `CodeFacts.present` checks, covering deletion, migration, rejection or reassignment, missing/null values, persisted readers and privacy. Do not infer that an old field is unused; retain the real code checks and explicit disposition.
- Rewrite legacy runner checks as ordinary contract models and delete retired files. Move unbuilt behaviour into target models and remove `DESIGN_ONLY` there too. Keep budget checkpoints and business-domain ledgers; they are unrelated to the retired proof/currentness mechanisms.

### Effects on projects that use FlowGuard

- Sharing the same responsibility, `state` or `side_effects` claim across owners produces `duplicate_owner` in lint, the system model and target checks, and makes release fail. Describe the actual state and effects owned by each component.
- Duplicate or wrong-file-owner entrypoints produce `entrypoint_owner` errors. Unexplained declared routes, commands, console scripts and handlers produce `entrypoint_unmodeled` warnings; argparse-derived subcommands are excluded and the existing dangerous-effect checks remain. Bind the entrypoint to a model or supply a reasoned `NOT_MODELED`.
- The three nesting mistakes above are hard errors. A current model declaring `DESIGN_ONLY` is an error even when its value is false or empty; target models also reject the declaration. Leftover runner locations, including `run_checks.py`, produce `runner_model` errors and are never executed.
- The old behavior ledger is not read; its presence produces `retired_file`. Existing ResearchGuard adopters should record the expected extra entrypoint warning, resolve it through a model or reasoned exclusion, and specialize the state/effect descriptions of `logicguard`, `sourceguard`, `traceguard` and `experimentguard` with their FlowGuard reference upgrade.
- Retired capability engines are no longer exported from `import flowguard`. Use the tree recipes and provider-module imports above; preserved core consumer paths do not change.

## v0.70.10 - 2026-10-22 - One model tree, real proof flows and simpler contracts

- Feature kits explore allowed feature sets, support `codes="first"`, and validate `requires` and `conflicts`. Clean inputs still receive a real conformance check when a feature universe has no clean-input invariant.
- `Workflow(..., mode="choice")` dispatches each input to its accepting block and preserves terminal, error and trace behavior. The default remains sequence composition.
- Code-structure, architecture-reduction and field-lifecycle plans can report future changes under `DESIGN_ONLY`. Current anchors and at least one real fact remain required; planned facts cannot silently pass as implemented code.
- Every capability starter writes one flat contract model with real known-bad variants and conformance. Starters create no `run_checks.py`; existing user-written runners remain supported. `model-test-alignment-full` and `model_test_alignment_full_template_files` were removed. `alignment_plan_from_model` derives declared code/test links and can consume real per-test statuses.
- Removed self-reported coverage links, including `ModelContractCoverageReceipt`, `contract_exhaustion_to_coverage_receipt_ids` and `FAMILY_EVIDENCE_PROVENANCE_CONTROLLER_RECEIPT_FOLDED`. Real finite case generation, execution limits and shard-completeness checks remain.
- Removed `BehaviorEvidenceBinding`, the `BCL_EVIDENCE_*` and `BCL_TEST_MESH_*` states, and the selected relation/path `evidence_current` flags. Old behavior ledgers still load after only known retired keys are ignored; unknown keys and noncanonical shapes still fail. Native test, source and artifact evidence checks remain active.
- Workflow step contracts now use `requires_tokens`, `produces_tokens`, `invalidates_tokens` and the `completion_tokens` property. `STEP_METADATA_PRODUCED_RECEIPTS` and `STEP_METADATA_INVALIDATED_RECEIPTS` became `STEP_METADATA_PRODUCED_TOKENS` and `STEP_METADATA_INVALIDATED_TOKENS`; finding/report fields use token names. No old aliases remain.
- Removed template-pack manifest sealing, selection/instance receipts and their registry. Bounded predicates and route-scoped seed validation, selection and closure remain. Topology review uses source labels and `TOPOLOGY_DISPOSITION_TEST_REQUIRED`, replacing `TOPOLOGY_DISPOSITION_LEDGER_REQUIRED`; `BusinessPathIdentity.evidence_ids` and `TopologyHazardCandidate.proof_evidence_ids` were removed.
- The skill, protocols and README describe one tree with five abilities. FlowGuard's own tree includes the real state-closure refinement and models of after-edit selection and native proof; independent review state domains remain component peers.
- An unknown `PARENT` or a parent loop is now an error. Other nesting findings stay warnings, and invalid parent declarations still have a readable default placement.

## v0.70.9 - 2026-10-22 - Check real model boundaries and bound tests

- `map check` reports dependency cycles with their full members and shortest real import paths, using the same rules and accepted debts as `read` and `map lint`.
- The built-in `system` model checks actual source ownership, dependencies, layers and accepted debts. Run it with `map models system`; `release` includes it.
- `release` runs each model's `TESTED_BY` tests. Each test call, including each parameter case, must pass and call an anchored Python body or explicitly read an anchored file. `map models --tests` provides the same check.
- New warnings identify tests outside their component (`test_not_nested`), unanchored writers of modeled state (`model_writer_unbound`), and child start states that miss the parent's bounded reachable states (`child_start_gap`).
- `flowguard.kit.reachable_states` collects initial and retained trace states, with optional projection. Short grow-a-model and split-a-model recipes explain how to extend existing models.
- Model-mesh can resolve real model IDs and derive static child facts from model files. Closure is required for actual handoffs between children. Receipt fields, evidence IDs, self-reported freshness and legacy classification were removed, including `LegacyModelRecord`, `LegacyModelClassification` and `classify_legacy_model`.
- Removed the unused portable state-table/refinement and system-composition API: `PORTABLE_MODEL_SCHEMA_VERSION`, `PORTABLE_REFINEMENT_SCHEMA_VERSION`, `PORTABLE_SYSTEM_REQUEST_SCHEMA_VERSION`, `PORTABLE_SYSTEM_SCHEMA_VERSION`, `PortableModel`, `PortableSystemDefinition`, `PortableSystemSlice`, `RefinementBinding`, `SystemCompositionReport`, `SystemCompositionRequest`, `check_composition`, `check_portable_model`, `check_refinement`, `check_system_composition`, `derive_system_slice`, `execute_portable_model`, `load_portable_model`, `load_portable_system`, `load_system_composition_request` and `validate_portable_model`.

## v0.70.8 - 2026-10-22 - Read and validate the model tree

- `scripts/install_skill.py --check` compares installed files byte by byte (changed in 0.70.7, not listed there).
- Models form a tree through `PARENT` and ordinary imports. Existing models keep working, and contract models no longer require a second registration in the map.
- `read` shows the project, components and model subtrees; `read --mermaid` exports the same tree, including a selected component's scope.
- `change` selects the importers and ancestors of an edited model or shared helper. REVIEW lines and `read --find` name the related models.
- Cycle debts cover their recorded members and report new members when a cycle grows. Type-checking imports and ordinary strings no longer create false dependency evidence.
- `release` fails when an invariant has no accepted, non-exhausted known-bad counterexample; `map models` keeps its diagnostic warning.
- Symbol searches prefer real definitions, dependency ordering is stable, and source comparisons handle LF and CRLF consistently.
- Closed output pipes exit quietly on Linux and Windows, scanning leaves the project's ignore file untouched, and grouped entrypoint hints are shorter.
- Installation instructions point to the maintainer's GitHub release assets rather than the unrelated PyPI package.

## v0.70.7 - 2026-10-20 - Models bound to the real code; slim/2026-10

- Done: FG-01, FG-02, FG-03, FG-04, FG-05, FG-06, FG-07, FG-08, FG-09, FG-10, FG-11, FG-12, FG-13, FG-14, FG-15, FG-16, FG-17, FG-18, FG-19, FG-20, FG-21, FG-22, FG-23, FG-24, FG-25, FG-26, FG-27, FG-28, FG-29, FG-30, FG-31, FG-32, FG-33, FG-34, FG-35, FG-36, FG-37, FG-38, FG-39, FG-40, FG-41, FG-42, FG-43, FG-44, FG-45, FG-46, FG-47, FG-48, FG-49, FG-50, FG-51, FG-52, FG-53, FG-54, FG-55, FG-56, FG-57, FG-58, FG-59, FG-60, FG-61, FG-62, FG-63, FG-64, FG-65, FG-66, FG-67, FG-68, FG-69, FG-70, FG-71, FG-72, FG-73, FG-74, FG-75, FG-76, FG-77, FG-78, FG-79, FG-80, FG-81, FG-82, FG-83, FG-84, FG-85, FG-86, FG-87, FG-88, FG-89, FG-90, FG-91, FG-92, FG-93, FG-94, FG-95, FG-96, FG-97, FG-98.
- Skipped: none.
- Normalize physical newlines before classifying comment-only edits, so unchanged CRLF checkouts and newline-only requests retain the full caller, test and model closure.
- Completed removals, merges and collapses no longer fail the candidate-exists check; code facts still require the removed symbol to be gone.
- Warn for each invariant that no accepted, completed known-bad variant violates; warnings do not change model exit rules.
- Generated masking variants require a reachable ordered pair that actually hides a code; shared or contained codes no longer produce an equivalent known-bad design.
- Every model, contract file or runner, names the real code it is about (`IMPLEMENTED_BY`, plus `TESTED_BY`)
  and consults it while it runs (called, or read as code facts). Missing, unresolved or `REPLACE_ME` anchors
  and a contract model without `conformance()` are check ERRORs; `DESIGN_ONLY = "<reason>"` is the only
  exemption. `change` selects models and runners by their anchored files and named tests.
- Model kits (`flowguard.kit`, `flowguard.map.facts`): the field-lifecycle (code facts), contract-exhaustion
  (generated bad cases run against the real function) and ui-flow (journeys plus code facts) templates write
  one contract model; runner templates ship placeholder anchors that fail until filled (the model-test runner
  also checks the owner code its plan names). Behavior commitments
  and module splits check their anchors when given a project root.
- FlowGuard's own self-models are contract models with anchors, known-bad variants and conformance.
- Feature-combination kit (`flowguard.kit`: `Feature`, `feature_explorer`, `feature_variants`,
  `feature_conformance`) replaces the case table: every single feature and every pair of an input is
  explored on the design and on the real code, with four kit invariants (clean input accepted, each defect
  rejected, every defect reported, benign features neutral), generated known-bad variants and counterexample
  traces. The contract-exhaustion kit and the self-models use it; it found two masking bugs, now fixed:
  model-test hid an internal-path-only test that was not bound to a code contract, and a topology plan that
  listed only an unanchored warning got no generated hazards.
- Code-structure and architecture-reduction kits: the `code-structure` and `architecture-reduction` templates
  write one contract model (the `code-structure-recommendation` runner template is gone). A module plan or a
  reduction plan grows by named edits with the existing reviews as invariants (a split also passes
  `review_structure_mesh`); a responsibility with two owners, a split that drops an entrypoint and deleting a
  symbol that another file still imports or names are counterexamples. Code facts compare the target plan with
  the code: module files, split children and entrypoints exist, owner files belong to the named map component,
  removed code is unreferenced (`CodeFacts.symbol_references`).
- Behavior-commitment kit: the `behavior-commitment` template writes the ledger and one contract model (the
  `behavior-commitment-ledger` and `primary-path-authority` runner templates are gone). The ledger and the
  primary-path plan grow or shrink by named edits (add or retire commitments and paths) with
  `review_behavior_commitment_ledger` and `review_primary_path_authority` as invariants; a commitment whose test
  never imports or calls its entrypoint is a counterexample. Code facts: entrypoints and tests exist and touch
  each other, the primary entrypoint exists, a delegating facade calls it, a deleted path is gone.
- The `ui-flow-structure-full` runner template is gone: the ui-flow kit template is the one UI starter, and the
  other UI reviews are called directly on its interaction model.
- Every kit template names its tests: `TESTED_BY` is a live `REPLACE_ME` test anchor (map check reports
  `model_test_broken` until it names a real test), as for the code anchors.
- Every model has the same five abilities (a state model of its concern, counterexamples, known-bad variants,
  code binding, test binding). Only the meta-capabilities (model-mesh, topology-hazard, model-test) keep runner
  templates: they inspect other models and tests, and the one binding rule still applies to them.
- Removed SkillGuard-era proof machinery (development-process engine, TestMesh plans and reuse tickets,
  receipts, proof artifacts, evidence ladders, assumption cards, shard result reuse) and the existing-model,
  model-miss, structure-mesh and development-process entries; their functions live in `read --find`,
  `change`/`release`, `references/model_recipes.md` and code-structure.

## v0.70.6 - 2026-10-18 - Preserve failure boundaries and current execution evidence

- Clean the owned POSIX process group after timeout or a leader exits with live
  descendants. Nested native process helpers share the same finite owner; an
  inner timeout terminates that leaf. Keep bounded Windows taskkill behavior.
- Reuse shard results only with exact current input bytes, interpreter, dependencies,
  environment, arguments and matching recorder input digests. Unknown legacy results
  run once again; final release checks never resume.
- Reject unknown field role, lifecycle and behavior-impact vocabulary through typed
  review blockers, while retaining legal scoped and delegated declarations.
- Preserve run_owner completion in the contract protocol and select actual registered
  behavior-ledger/primary-path runner ids. Preserve typed capability-metadata diagnostics.

## v0.70.5 - 2026-10-18 - Reuse native owners and execute selected checks once

- Align all 14 capability protocols with their actual direct-review, existing-owner
  and new reusable-boundary branches. Scaffold and runner registration are conditional;
  registered runners have one formal model execution for the current inputs.
- Keep ordinary pytest results sufficient for small changes, require same-class model-miss
  cases only for the applicable recurring/high-risk, UI or independent-path scope, and
  retain real business failure assertions and current-source evidence requirements.
- Use the complete caller closure for ordinary change selection; label depth-limited
  diagnostics as truncated. Correct architecture-cycle severity and dependency-write guidance.

## v0.70.4 - 2026-10-17 - Preserve surviving verification after ownership changes

- Keep affected historical tests and executable models that still exist when an owner
  or its bindings change; do not revive deliberately deleted checks. Surviving runners
  without current registration are blocked until their ownership is resolved.
- Resolve selected test commands from current declarations, then unambiguous historical
  mappings. Missing or ambiguous commands block impact/change instead of exiting successfully.
- Keep unsupported deletion scopes visible as `NO CHECKS`, while registered resources
  and surviving verification remain precisely scoped.

## v0.70.3 - 2026-10-17 - Focused native checks and simpler maintenance

- Keep the living code/model/test map, current pointers, executable models, known-bad
  behavior checks and runtime conformance. Exact registered schema/config/resource
  paths now share their owner's fingerprint and affected-check selection; ignored
  files and unregistered non-code globs do not broaden the inventory.
- Always print the actual selected test paths, including selections larger than 30.
  Focused default templates use native APIs; explicit full teaching variants remain.
  Planned target evidence stays `not_run` until a real test executes.
- Make companion capability routes conditional on the actual risk. Public-boundary
  parity, unique owners, retirement obligations, freshness and per-obligation test
  bindings remain; ordinary owner lookup does not require maturation/admission chains.
- Remove the retired canonical-receipt requirement, unreachable native promotion,
  unused author review layers, unconsumed wire projections and historic self-review
  examples. Preserve native hashes, result integrity and live code/model/test bindings.
- Run one complete Ubuntu Python 3.11 CI lane, with core path and packaging smoke on
  Ubuntu Python 3.13 and Windows Python 3.12. Publish the current stable version and
  all three assets only after the entire CI workflow succeeds for that exact source.

## v0.70.2 - 2026-10-14 - Honest checks, precise selection and portable operation

- Models always execute. Remove the PASS cache and its self-model; move the impact self-model's
  exit-status protection into ordinary tests. The release registry contains 32 models.
- Runner models must complete actual checks through `run_owner(main)`; empty runners fail.
  Contract models need a real Explorer, a nonempty explored boundary, and known-bad variants.
  Python implementation anchors must actually run; crashes or unrelated bad rules do not count.
- Connect optional `TESTED_BY` invariant/test anchors in both directions. Missing bindings,
  undeclared owner runners and deleted test symbols are visible failures. Dangerous entries
  without modeled anchors receive a warning unless `NOT_MODELED` gives an explicit reason.
- Resolve literal lazy facade exports to their real owner. Keep package initialization in test
  reachability. Select importing tests, helpers and conftest consumers; test/model-only edits
  stay narrow. Explicit product paths override test-like names. Report configuration/doc changes,
  unsupported test commands and unowned source. Confirm alone no longer requests another review.
- Show architecture drift on change, with import sites. Cycles gate release unless already accepted;
  near duplicates ignore local variable renaming. Correct the transition-coverage owner instead
  of prescribing a large refactor; four concrete accepted debts remain and stale debts are visible.
- Discover console scripts and local imports; improve callback reach and remove constructor noise.
  Scan groups deep directories into at most 40 draft components and guesses tests from imports.
- Read the whole self map and four flows within 8,000 characters; preserve detail through
  `read --component`. Add 0.69 upgrade guidance and six adoptable AGENTS/CLAUDE rules.
- Bind pytest outcomes, identities and input snapshots from the same recorder run. Missing,
  skipped, failed, renamed and stale rows cannot support execution claims. Accept common raises,
  class and src-layout tests; reject tautologies, mocked targets and shadowed names.
- Keep all 14 capabilities; add focused detection regressions, strict mesh parent/scope checks,
  capability template aliases, honest topology template exit statuses and single-writer handling.
- Move generated shard/checkpoint/example output into disposable cache. Remove old receipt assets,
  the unused runtime_test_evidence module and redundant test/model work; label abstract runners.
- Fix Windows/newline/encoding handling, Chinese paths, BOM and coding cookies. CI covers Ubuntu
  Python 3.11/3.13 and Windows Python 3.12 using current actions. Wheels install only flowguard,
  and the skill installer expands Windows/environment paths with clear errors for missing values.

### Upgrade notes

- This release increments only the patch number (0.70.1 to 0.70.2), as requested; these deliberate
  behavior changes still require updating older generated runners and project bindings.
- End runners with `from flowguard.map.runner import run_owner` and
  `raise SystemExit(run_owner(main))`. An exit code alone is not a completed check.
- `map models --force` and PASS reuse are removed. Every selected model executes; discard old
  `.flowguard/cache/models.json`. Contract models must declare `broken_variants()`.
- `dep_unused` is now an error: support dependencies with imports, module literals or a narrowly
  justified existing debt; `deps --write` removes unsupported declarations. Do not declare cycles
  just to clear another error. Register standard owner runners to fix `model_unbound`.
- `TESTED_BY` is optional, but its invariant names and test anchors must exist. `NOT_MODELED`
  records negative scope and grants no real-code proof. Review warnings instead of hiding them.
- `runtime_test_evidence` and its unused public exports are removed. Use same-run pytest binding
  with the recorder, outside models. `test_commands` routes non-Python test patterns explicitly.
- Capability names have template aliases; architecture-reduction points to its protocol snippet.
- Components with non-ASCII names or previously excluded test-like product files become STALE
  once after upgrading. Re-read them and confirm. For 0.69 projects see `upgrade_from_0_69.md`.
- Release checks map, lint and models only; execute pytest separately. No model launches pytest.

## v0.70.1 - 2026-10-14 - Scoped impact, model registry, PASS cache, pytest result binding

- `change` and `map impact` follow the full reverse caller closure by default; an explicit
  `--depth N` cuts it and prints TRUNCATED.
- `change` also selects the tests, models and runners bound to the affected components, and
  map.json edits to verification fields (files, entrypoints, depends_on, tests, models, state,
  side_effects) re-select their components.
- One executable model registry (`mapfile.model_registry`) is shared by check, `map models` and
  release. Unknown or duplicate model ids, empty broken_variants(), invalid conformance results
  and model files that do not parse now fail; release prints declared and executed counts.
- A PASS cache for contract models in `.flowguard/cache/models.json`; runners are never cached.
- Model-test alignment can bind real pytest results: `bind_pytest_execution` in
  `flowguard/model_test_alignment.py`; the source audit rejects same-name calls on the wrong
  receiver and assertions that are always true.
- New self-model `.flowguard/models/change_impact.py`; release runs 34 models.
- Known issue: on Windows, `tests/test_flowguard_map.py::test_fingerprint_ignores_crlf_line_endings`
  fails (a bug in the test, not in the product), so the Windows CI job is red.

## v0.70.0 - 2026-10-13 - Map, capabilities kept, ledger retired

- New: `.flowguard/map.json`, a living, code-anchored map of the software (components,
  responsibilities, state, side effects, files, entrypoints, dependencies, tests, models),
  verified against the code by `python -m flowguard map check`.
- New: discovery (reverse wrap). `map scan` and `map discover` find HTTP routes, CLI commands,
  side effects, how far each entrypoint reaches and which functions write each state attribute;
  `map lint` reports unlisted entrypoints and undeclared side effects.
- New: daily verbs `python -m flowguard read | change | release`; `change` lists only the tests
  and models a change affects. `python -m flowguard template` writes starter files for every
  capability again.
- Kept: the modeling engine and all 14 capabilities (existing-model, behavior-commitment,
  architecture-reduction, code-structure, contract-exhaustion, development-process,
  field-lifecycle, model-mesh, model-miss, model-test, topology-hazard, structure-mesh,
  test-mesh, ui-flow), each with a short protocol in the skill.
- Retired: the stored authority/evidence machinery (model authority snapshots and revision
  sets, evidence receipts, validation owners, native case rows, blueprints, SkillGuard
  projections, maturation receipts, the risk evidence ledger, route registries) and its
  generated JSON. Capability modules no longer import it. The full history stays in git
  (the legacy version is commit `2999a09`, v0.69.9).
- FlowGuard maps itself: 37 components; 31 self-models plus 2 map models run in about 20 s;
  the full test suite runs in about 30 s.
- `import flowguard` loads only the facade (a plain name table).

## v0.69.9 - 2026-10-06

- Start selected software reads with current/target/gap/temporary-compromise/unknown understanding and actual nullable task denominators.
- Expose genuine first-gap details and next owner while preserving the original functional scope and stopping decision.
- Preserve complete cursor/batch transport, the 8192-byte page limit and one projection/one final drift guard.

## v0.69.8 - 2026-10-02

- Reduce repeated model input scans, raw evidence hashing, and native case
  projection work inside bounded validation runs.
- Reuse exact-current successful owner receipts without changing required
  obligation coverage or cleanup safety.
- Bind cached completion readiness to the current full owner plan; preserve
  immutable evidence when source, test, or toolchain identity changes.
- Audit the complete declared model graph, including branch, state, guard,
  output, and implementation bindings; incomplete declarations cannot support
  a faithful graph or whole-software coverage claim.
- Compare responsibility relations across applicable contexts and propose
  finite architecture changes from explicit goals or verified duplicate
  boundaries. Matching content hashes alone do not prove a shared mechanism.
- Bind typed architecture objectives to the admitted intent sources and expose
  facts, goals, findings, suggestions, observation gaps, and improvement gaps
  through bounded read pages. Consumers follow the cursor to the terminal page.
- Keep faithful Current observation separate from improvement completion;
  required architecture gaps block their declared completion claim. This
  finite review does not establish a globally optimal architecture.
- Close a requested function only when current implementation bindings,
  native evidence and verified maturation prove every requested outcome;
  unrelated functions do not expand that task's evidence scope.
- Preserve unmodeled implementation writers, context remainders and current
  temporary compromises in actionable architecture pointers. Invalid model
  ownership or wholly unassigned goal scope blocks rather than hiding debt.
- Share source bytes and identity projections within one read, while each new
  invocation observes current bytes. Ordinary task completion has no default
  cost ceiling; explicit cost goals require independent measurement evidence.
- Keep the efficiency change scoped to its affected models and workflows.
  A complete reverse implementation semantic inventory remains a separate
  authoring task and is not claimed by this release.
- Retain the public read/change/release lifecycle and source-only release
  boundary. Overall PlanningTool runtime speedup has not been measured.

## v0.69.7 - 2026-09-22

- Retired the legacy FlowGuard command parser and route-reference entry so the
  executable surface is only `read`, `change`, and `release`.
- Bound selected reads to the accepted projection shards and kept unchanged
  changes side-effect free while preserving the evolving current information
  map.
- Published the compact source-only patch with direct-current evidence and no
  compatibility or fallback path.

## v0.69.6 - 2026-09-22

- Closed the compact one-skill route boundary: the public `flowguard` entry remains the sole installable skill, while domain material is loaded on demand through typed route projections.
- Re-authored the current reverse-surface map against the fresh discovery fingerprint, repaired the behavior ledger and current author registry, and verified all 51 native model owners with fresh parent evidence.
- Kept release and installation claims separate: this patch carries source, model, consumer-projection, and targeted/full-test evidence only; publication is established by the immutable tag and GitHub release.

## v0.69.5 - 2026-09-21

- Published the compact current lifecycle: `read`, `change`, and `release`.
  `read` returns a bounded selected map, `change` executes the declared
  affected owners with explicit bootstrap/CAS evidence, and `release` performs
  local qualification without installing or publishing.
- Kept the accepted FlowGuard map as the evolving information map, with
  independent connection-owner evidence and strict input snapshots.
- Removed the former public command aliases and fallback routes. This source
  release is cumulative from the last public GitHub release `v0.69.0`; the
  intermediate `0.69.1`–`0.69.4` entries describe source milestones only.

## v0.69.4 - 2026-09-20

- Contracted the public FlowGuard distribution to one installable `flowguard`
  skill; former route copies now live as on-demand domain references under the
  core skill and are no longer discoverable satellites.
- Replaced the public execution-profile surface with the fixed `read`,
  `change`, and `release` lifecycle and kept selected-only domain loading and
  bounded summaries visible in the documentation and manifests.
- Preserved the existing model/evidence boundary while separating source,
  installed consumer projection, GitHub branch state, and release/tag claims.

## v0.69.3 - 2026-09-20

- Bound affected blueprint projections to one closure read, selected-only
  materialization, and an explicit request-boundary close; unknown changed
  paths and unresolved activation placeholders now fail closed.
- Preserved all 54 authorized model-obligation identities, runners, tiers,
  inputs, and protected failures while tightening current pytest leaf
  ownership, duplicate execution, and compact route-reference loading.
- Prepared the joint-audit author and CI boundary without changing consumer
  installation state or introducing a compatibility route.

## v0.69.2 - 2026-09-20

- Make native skill checks fail closed before execution, share one bounded
  suite/input observation per invocation, and preserve interpreter/cleanup
  evidence in terminal failures.
- Add bounded project-audit JSON, immediate unknown-submodule failures, and
  explicit same-schema patch-update warnings without automatic upgrades.
- Add lazy canonical projection lookup caches for affected reads, owner-local
  native registry projections, bounded exploration metadata, and compact
  kernel route prompt materials.

## v0.69.1 - 2026-09-19

- Preserve exhaustive reachability truth while bounding compact exploration
  witnesses, and reject empty or invalid exploration domains.
- Bind native-check inputs to tracked source, selector membership, component
  identity, and supervised process-tree cleanup evidence.
- Add a lazy public package facade, parameterize template CLI checks in-process,
  and repair CI's self-maintenance entry point and pytest denominator.

## v0.69.0 - 2026-09-04

- Added recursive multi-level model and TestMesh closure with exact parent,
  child, cross-child, finite-product, and terminal-receipt bindings.
- Hardened model execution evidence so completed leaves are derived from native
  execution receipts rather than caller-supplied case lists.
- Added a frozen completion-readiness gate and exact parent-receipt reuse path,
  preventing freshness checks from causing repeated full validation loops.
- Kept architecture-reduction candidates fail-closed until observable
  equivalence or complete retirement evidence exists.

## v0.68.16 - 2026-08-26

- Added direct-current reverse implementation-surface discovery with exact
  lexical/import identity, bidirectional model-to-surface closure, and
  full-versus-merged call-graph conservation.
- Reorganized current FlowGuard artifacts into explicit behavior, models,
  structure, verification, evidence, and history roles while keeping runtime
  evidence out of the source-only release boundary.
- Preserved fail-closed currentness: stale or former artifacts require a
  direct latest-schema rewrite and never become a compatibility or fallback
  authority.

## v0.68.15 - 2026-08-13

- Remove product-specific Planning Tool and KhaosBrain owner mappings from the
  public FlowGuard engine.
- Require each target repository to declare its exact native owner bindings;
  FlowGuard validates the declaration and never selects a hidden product profile
  or falls back to FlowGuard's own models.
- Add a current-only atomic authority rebuild command for direct replacement;
  retired revisions are opaque CAS inputs and are never parsed or migrated.

## v0.68.14 - 2026-08-12

- Repair the package-owned consumer-suite authority so its embedded FlowGuard
  version matches the published package identity.
- Add release-identity coverage for stale authority metadata while preserving
  the existing fifteen-member clean consumer projection.

## v0.68.13 - 2026-08-12

- Keep the repository directory as FlowGuard's native DNA: models, code/test
  bindings, and current evidence remain the source authority without a
  standalone self-DNA package.
- Remove the last self-export terminology and keep readiness focused on the
  current native model, its bindings, and visible evidence gaps.
- Refresh the self-model and release identities for the patch version.

## v0.68.12 - 2026-08-11

- Keep the native model directory as the only DNA carrier and publish its
  model, code/test binding, and current evidence files as ordinary source.
- Refresh the behavior-commitment source inventory after the self-model and
  prompt changes; stale fingerprints now fail visibly instead of being reused.
- Raise the foreground native-check budget for the model-revision owner so the
  complete regression set has enough time to finish without a retry path.

## v0.68.11 - 2026-08-11

- Made the native model directory the only DNA carrier. Models, parent/child
  interfaces, code/test bindings, and current evidence remain in place beside
  the software they describe.
- Retired standalone DNA export files, copied-directory materialization,
  transport bundles, and isolated reconstruction routes. Former command names
  now return the typed `native_directory_only` result.
- Tightened self-architecture reduction so an audit cannot claim that a
  simplification was applied without explicit application and verification
  evidence.

## v0.68.10 - 2026-08-10

- Added provider-neutral DNA qualification for software, workflows, services,
  agents, pipelines, and mixed systems without assuming Python as the target.
- Bound FlowGuard's self-blueprint, code/test evidence, and architecture
  reduction decisions to the same current qualification and ownership chain.
- Kept ordinary use lightweight: deep simulation and reconstruction remain
  explicit operations, while stale or incomplete model evidence stays visible.

## v0.68.9 - 2026-08-09

- Added a direct, current-model-gated export of FlowGuard's own portable DNA
  bundle. It reuses the canonical project blueprint already built by the
  self-audit path, writes one provider-neutral envelope, and leaves
  reconstruction, source execution, and test execution outside the export.
- Added persistent prompt-context accounting so route reports measure the
  context that is always loaded separately from detail that is only triggered
  when needed. Tightened ArchitectureReduction and DevelopmentProcessFlow
  routing so large protocol material is loaded only for its declared branch.
- Kept model authority direct-current: source changes must pass the native
  model-revision chain before a portable self-bundle can be written.

## v0.68.8 - 2026-08-08

- Added a provider-neutral portable blueprint envelope over the existing
  canonical projection, with isolated fingerprint verification and bounded
  compact views that keep static, portable, and execution status separate.
- Bound the new portable export and verification paths to the existing
  model/code/test ownership; compact output preserves denominators,
  fingerprints, unresolved ids, and `not_run` gaps without creating a second
  DNA authority.
- Consolidated strict duplicate-key JSON parsing under one current reader
  owner and tightened ArchitectureReduction, StructureMesh, Model-Test
  Alignment, TestMesh, and DevelopmentProcessFlow guidance around
  equivalence-backed contraction and one final release gate.
- Kept independent reconstruction and translation out of this release; the
  bundle is an exchangeable model projection, not an implementation runner.

## v0.68.7 - 2026-08-07

- **Breaking:** retired fourteen historical, task-local, or completed construction current-model routes whose useful
  protections are now owned by the canonical DNA path: Model Angle
  Deliberation, Maintenance Scan Router, standalone Model Similarity
  Consolidation, Legacy Compatibility Cleanup, and the dedicated Template
  Harvest Closure self-model, plus OpenSpec Archive Cleanup, README Positioning
  20260602, Release Visibility Process, Risk Purpose Header, AI Surface
  Streamlining, Reduce Architecture Surface, Simplify FlowGuard Structure,
  Structure Surface Simplification, and Simplify Field Schema. Their old
  module, template, route, and public identities fail visibly; no alias,
  compatibility reader, or fallback was added. Historical changelog, archive,
  snapshot, and receipt evidence remains immutable.
- Made current-goal necessity a first-class Architecture Reduction decision.
  Ordinary contraction still requires observable equivalence, while an
  intentional behavior retirement now requires an exact responsibility,
  consumer, negative-case, replacement-owner, and validation disposition
  before deletion is authorized.
- Extended Architecture Reduction inside retained routes. Internal scans,
  builders, reflections, projections, fingerprints, and other steps now receive
  an exact retain/merge/delegate/remove/explicit-on-demand/unresolved decision
  from the same caller and responsibility inventory. Measured operations,
  invocations, payload bytes, and estimated tokens rank cleanup priority only;
  they cannot authorize removal of a unique safety or final-evidence owner.
- Consolidated post-green bug back-propagation into one bounded path: exact
  commitment and behavior-block gap, canonical affected relations, finite
  ContractExhaustion cases, ModelMaturation, then current model/code/test and
  affected-topology replay. The independent open-ended analogous-scan and
  model-angle completion paths are no longer current authorities.
- Replaced the standalone similarity-planning engine with a small immutable
  CanonicalRelation handoff consumed directly by preflight, contract
  exhaustion, code-structure, model-test alignment, and architecture
  reduction owners.
- Rebased FlowGuard's semantic self-model on the exact 51-owner current
  manifest rather than a historical snapshot plus additions. The semantic
  mesh now rejects missing, foreign, duplicate, or retired owners and records
  the exact fourteen-owner contraction from the observed 65-owner baseline.
- Added a provider-neutral per-model path-quality decision to current DNA.
  Ordinary models receive one compact lightweight result; finite deep review
  runs only for explicit or evidence-derived triggers. Hard semantics precede
  cost comparison, cost remains multi-dimensional, retained elements require
  necessity witnesses, and only bounded conclusions are licensed—never an
  unrestricted global-optimum claim or routine reconstruction exercise.
- Added a read-only model-revision preview that derives the exact
  base-to-live-candidate diff, affected closure, and required native evidence
  owners without creating snapshots, receipts, locks, leases, or authority.
- Added cumulative current-effective-intent authority to v5 model revisions.
  Each accepted revision now keeps its local change delta separate from the
  complete current intent view, reverifies every active source, binds every
  independently derived current model owner exactly once, and records explicit
  retain, supersede, or retire transitions. One ancestry-audited
  `model-revision-intent-bootstrap` creates the first v5 view; later revisions
  refine the accepted view directly. The corresponding stable Python API
  exposes the typed view, transitions, owner bindings, bootstrap receipt,
  validators, accepted-revision loader, and read-only revision preview without
  exporting private ancestry helpers.
- Added a strict self-blueprint-definition compiler. Check mode is read-only;
  explicit write mode may refresh only mechanical source identities and
  preserves every authored behavior, interface, state, effect, resource, and
  claim-boundary field.
- Added one ownership-safe `author-sync` path for the explicit author shadow.
  It stages and verifies the complete managed member set, preserves peer-owned
  surrounding files, and rolls back an incomplete activation instead of
  copying an entire dirty repository. Consumer installation remains the
  separate `install` projection, and `parity` compares source, formal author,
  author shadow, and installed consumer identities without converting one role
  into another.
- Retired the unowned whole-repository `sync_shadow_workspace.py` helper. It
  had no current caller, preserved stale files by design, and duplicated the
  author-shadow responsibility without the current 15-member ownership and
  atomic-activation boundary. Historical release records remain unchanged.
- Measured the cleanup against `fa8a9a4`: current runtime plus executable
  self-model files fell from 303 to 283 (-20, or 6.600660%) and current owners
  from 65 to 51 (-14, or 21.538462%). The
  former standalone similarity engine contracted from 16,359 to 1,174 Python
  lexical tokens, while necessary DNA and evidence work increased the combined
  runtime/self-model token count from 867,087 to 1,055,846 (+188,759, or
  21.769326%); this release therefore claims
  fewer duplicate authorities, not a fictitious whole-codebase shrink. The
  recorded pre-finalization read-only revision report rendered from 364,497
  characters in full form to 2,604 in compact form (-99.285591%) with
  identical report identities and no writes or model execution.

- Added one strict portable project document and deterministic canonical
  export. The document now carries its exact intent inventory, and the export
  preserves twenty content-addressed layers covering target/provider identity,
  behavior and cases, parent/child interfaces, code and test bindings,
  resources, intent, affected indexes, and every depth/readiness gap.
- Added the provider-neutral `target-system-blueprint-export` entry for
  non-Python software and non-code workflows. It preserves the exact descriptor,
  frozen provider evidence and layer plan, complete native report set, and
  compiler-owned readiness through the same projection envelope, shard writer,
  and verifier used by the Python-project convenience export.
- Added one strict current-schema loader for that canonical projection. It
  rejects extra files or directories, missing shards, symlinks, Windows
  junctions and other reparse points, content-address drift, and changes during
  verification; target and project exports then rebind the materialized tree to
  their exact compiler inputs instead of treating internal self-consistency as
  proof of the intended target.
- Made projection replacement failure-atomic on Windows. The writer rechecks
  both the staged and existing trees immediately before activation, restores
  the complete prior tree after an interrupted swap, preserves recovery
  material when rollback is incomplete, and reports post-commit backup cleanup
  failure without falsely relabeling a successful activation as failed.
- Separated export completion from model completeness. An explicitly requested
  checkpoint can preserve a growing model with `incomplete`, `stale`,
  `blocked`, or `not_run` findings without relabeling those gaps as sufficient
  whole-target understanding.
- Retired the raw-manifest check/export authority and the separate empirical
  reconstruction status, receipt, readiness, API, and lifecycle branch.
  Blueprint sufficiency now has one direct current representation: ordered
  layers, deepest proven depth, and exact gaps.
- Strengthened the provider-neutral target blueprint into a typed, layered
  software/workflow DNA: frozen target identity, parent/child topology,
  interfaces, state transitions, effects, errors, resources, intent, code or
  workflow bindings, and test obligations now stay connected by exact
  fingerprints instead of descriptive labels.
- Made native target qualification derive its own detailed member evidence
  from the observed target. Caller-authored downstream pass rows, gap lists,
  or an exported public assembler can no longer manufacture a ready result.
- Replaced the formerly public static qualification result with an internal,
  compiler-derived manifest-consistency child report. It has no generic `ok`
  or whole-blueprint claim, cannot be directly constructed by callers, and is
  excluded from the root API; sufficient understanding remains a mechanical
  result of the canonical target ledger and every required native layer.
- Added typed affected-topology propagation across ancestors, children,
  siblings, realization owners, and realization members, while keeping the
  requested seeds, propagated neighborhood, and actually loaded objects
  separately visible.
- Bound accepted intent to independently fingerprinted user objectives,
  OpenSpec, Spark, OpenSpark, changelog/history, and target-contract sources,
  including explicit revision, conflict, and unresolved-authority evidence.
- Upgraded native code/workflow, interface, test, resource, and intent members
  from label-only summaries to exact payloads with source identity,
  structure, checker/oracle, lifecycle, currentness, and evidence ownership.
- Kept ordinary maintenance lightweight with a content-addressed affected
  reader that loads only the exact referenced neighborhood. Its readiness
  ledger is bound outside the normalized projection, closing the circular
  fingerprint path without turning ordinary work into a whole-target scan.
- Rebuilt self-cleanup around an independently observed reduction-signal
  inventory and exact proof registry. Declared candidates can no longer prove
  their own denominator or equivalence; only proof-ready candidates may enter
  behavior-preserving reduction, and unproved surfaces remain visible.
- Made self-cleanup evidence linear in the unique evidence it actually owns.
  Candidates that share the same tests, coverage rows, dimensions, and current
  receipts now bind one content-addressed neighborhood instead of repeating the
  complete evidence per candidate; missing, stale, foreign, duplicate,
  fingerprint-mismatched, or inline-fallback references fail closed while proof
  receipts remain self-contained.
- Removed a quadratic affected-index integrity loop. Every base object still
  receives an independent real fingerprint check and every affected or topology
  edge is still validated, but all edges now reuse one exact validated object-id
  denominator instead of reconstructing the complete set for each edge.
- Made model-revision acceptance reload native-owner receipts from the
  canonical store and independently rederive current contract, input,
  command, toolchain, environment, proof, result, and child-receipt
  verification. Aggregate and child evidence must remain present through
  revision publication; caller-authored passing verification projections no
  longer create accepted model authority.
- Made every later model-system audit reload and revalidate the exact accepted
  revision instead of trusting its historical label. Distinct native owners
  must have distinct exact leaf receipt identities, while an invalid accepted
  artifact and a separately stale live model remain visible as two findings
  until a new current revision is built and activated.
- Replaced the recomputable model-parent wrapper as execution authority with a
  canonical child-bound composition receipt. A scoped run cannot become full
  model evidence by rewriting and rehashing its wrapper labels.
- Made self-reduction consume the exact current typed self-blueprint and
  explicit evidence-bound retain, contract, or unresolved dispositions.
  Owned singleton signals may close as typed retain, but signals that form one
  contraction relation require candidate-specific distinct-commitment evidence
  or real contraction proof. Unknown members can no longer be rewritten
  automatically as retained.
- Replaced caller-authored self-reduction leaf passes with supervised candidate
  test and caller/state/effect/error parity owners composed through one
  child-bound canonical receipt. Alternate receipt roots, unrelated tests,
  missing parity children, stale inputs, failed or unclean process trees, and
  proof reuse across candidates remain blocked; governed inputs are rechecked
  immediately before the review result is published.
- Tightened supervised validation publication so a passing owner receipt can
  be created only from the exact frozen command, working directory, current
  inputs, producer-attested result, and confirmed clean process tree; the old
  public pass-receipt saver was removed.
- Corrected Python implementation discovery so function parameters, locals,
  built-ins, and exception class names are not misclassified as persistent
  state while real attribute, subscript, global, and nonlocal state remains
  visible.
- Tightened FlowGuard's own self-blueprint and release-facing prompts around
  the same provider-neutral route, while keeping the six affected skill
  entrypoints compact and delegating detailed rules to their native
  protocols.
- Bound project qualification to a freshly rederived current provider result
  for every capability. A counterfeit payload can no longer pass merely by
  rebuilding an internally consistent provider snapshot around itself.
- Rebound project export across definition, inventory, bindings, behavior,
  topology, tests, resources, intent, readiness, affected index, normalized
  shared objects, and all canonical child fingerprints. A self-consistently
  rewritten shard, target object, logical fingerprint, or invalidation edge
  can no longer survive by updating only its neighboring hashes.
- Made the software manifest's semantic-mesh fingerprint derive from the
  reviewed topology report instead of accepting a caller-selected content
  fingerprint.
- Required every child validation/runtime evidence id to exist in the current
  owner-bound evidence registry with its exact current fingerprint; repeating
  the same ghost or cross-owner id across child, relation, and reattachment
  records no longer creates topology closure.
- Extended affected reading beyond parent/child edges so producer-consumer,
  delegation, and support dependencies enter the exact invalidation closure
  together with the relation that caused the propagation.
- Corrected FlowGuard's self-DNA so one model owner may contain many exact
  behavior blocks without lending the primary block's fields, cases, checker
  identities, or coverage to its siblings. Every block now carries its own
  portable input/output/state mapping and good, boundary, and protected-failure
  cases while preserving the shared model-level source-case lineage.
- Kept the complete implementation map while separating real behavior surfaces
  from structural and supporting surfaces. Public callables and observed
  state/effect/dynamic/entry behavior receive independent blocks; modules,
  classes, nested functions, and pure private helpers remain fingerprinted and
  owner-bound without fabricated business cases.
- Removed quadratic self-audit expansion by making dimension applicability
  surface-local and pre-indexing owner bindings, cases, intent targets, calls,
  coverage, reduction signals, and candidate neighborhoods. Added 1x/2x/4x
  structural scale regressions and exact real-self materialization invariants.
- Gave normalized coverage payloads one complete physical owner. Native typed
  readiness remains self-contained, while normalized reports, affected shards,
  and canonical behavior exports carry only exact fingerprints and strict
  object references; legacy full-payload shards are rejected without fallback.
- Replaced the second whole self-blueprint construction at architecture-review
  publication with an independently recomputed build-input identity over model
  authority, accepted intent, observed snapshot, all classified source/test
  files, the semantic mesh, and provider contracts. Any input drift still
  blocks publication, but an unchanged audit no longer rematerializes the full
  behavior and coverage graph.

## v0.68.6 - 2026-08-03

- Added one provider-neutral target-system blueprint kernel for software,
  workflows, services, agents, pipelines, and mixed systems. Whole-target
  claims now require a frozen provider registry and target snapshot, and every
  claimed capability binds its exact observed inputs and payloads.
- Bound each independently declared behavior owner to its exact code/workflow
  surfaces, input/state/output/effect/error/decision/order/retry/timeout/
  completion contracts, source-independent semantics, resources, and accepted
  intent without promoting every discovered helper into a fake model.
- Added an independently re-audited project-test inventory with exact files,
  nodes, parameterization, assertions, source fingerprints, and bounded native
  checker artifacts; broad parent evidence can no longer fabricate child test
  coverage or certify stale source.
- Added content-addressed intent contributions from declared project inputs,
  including bounded Spark, OpenSpark, and changelog/history profiles, and bound
  accepted intent to the existing WorkContext and ModelRevisionSet lineage with
  explicit conflict, supersession, rejection, deferral, and unresolved-gap
  handling.
- Added exact parent/child interface mappings: every topology relation records
  which producer output becomes which consumer input, and disconnected,
  missing, or surface-mismatched model owners block static readiness.
- Added a real ModelTestAlignmentReport with its own fingerprint, model
  obligations, owner code contracts, checker designs, execution state, and
  visible gaps. A binding-report fingerprint can no longer impersonate it.
- Split checker design by behavior case and dimension so one assertion or
  native check cannot silently claim contradictory good/boundary/bad cases or
  all behavior dimensions. Parameter-case identity stays explicit and planned
  checks remain distinct from receipt-backed execution.
- Required project owners to declare their concrete cases and accepted checker
  designs. The generic builder no longer manufactures canonical cases or
  checker identities from observed source, while `not_run` remains an honest
  execution status for a complete static test design.
- Replaced FlowGuard's self-only blueprint compiler with a thin preset over the
  generic builder, removed unknown-owner fallback, classified helpers as exact
  supporting relationships, and deduplicated repeated per-surface semantics and
  oracles into stable model-owner obligations.
- Added independently reported qualification layers and an honest deepest
  proven layer plus the first incomplete layer. The static blueprint completion, user
  execution choice, implementation admission, and receipt-backed execution
  remain separate.
- Added a normalized shared-object projection and exact affected-neighborhood
  loader so ordinary work reuses owners, contracts, semantics, oracles, tests,
  resources, and intent without loading the whole blueprint or changing its
  logical identity when shard layout changes.
- Made affected loading validate only referenced objects and added per-model
  topology and model-test indexes, so unrelated shared objects are no longer a
  hidden whole-blueprint input to lightweight work.
- Added exact interrupted-owner settlement and separate standalone/child/parent
  evidence authority so a dead validation process can be closed without
  touching unrelated leases or treating progress as a terminal result.
- Updated the affected FlowGuard skill prompts and protocols so explicit
  whole-software work can reach blueprint depth while ordinary maintenance stays
  affected-only and lightweight.
- Used the current self-blueprint to perform a finite read-only,
  behavior-preserving architecture contraction audit. The current denominator
  is complete; all 11 size or repeated-shape signals remain `risky_keep`, with
  zero unproved automatic deletions or merges.
- Contracted the release-facing self-blueprint and architecture-reduction
  validators into one ten-owner `self_maintenance_review` producer, reused one
  exact in-memory blueprint, and replaced per-candidate full-surface caller
  scans with one deterministic reverse call index. Both validation obligations
  remain explicit; no cache or fallback was added.
- Made compact self-maintenance output a direct bounded projection instead of
  expanding a multi-gigabyte full graph and immediately discarding it.
- Reused the exact canonical fingerprint of immutable large behavior evidence
  across self-blueprint qualification and architecture reduction.
- Streamed canonical fingerprint and byte-count calculation for large normalized
  blueprint payloads, removing simultaneous multi-copy JSON amplification before
  physical projection construction.

## v0.68.5 - 2026-08-02

- Made task facts independently observable by source plane and kept unknown,
  omitted, contradictory, unmapped, and scoped facts visible in the coverage
  denominator.
- Added one canonical owner-resolution identity across task coverage, model
  maturation, receipt verification, and readiness; caller-authored `passed`
  flags no longer substitute for command, result, time, subject, and content
  evidence.
- Added a read-only `model-understanding-status` API and CLI that reports model
  understanding, user execution choice, and FlowGuard implementation admission
  as three independent answers without running or writing anything.
- Replaced raw model-count activation with semantic topology and classified the
  complete 64-model observed universe into 7 parent domains with 189 explicit
  parent/consumer relations before whole-system closure.
- Contracted duplicate route, owner-result, Closure scoring, and count-based
  paths while preserving current public behavior, and updated the affected
  FlowGuard skills, contracts, tests, documentation, and release governance.
- Added an independent implementation and reconstruction-resource inventory,
  bidirectional model/code closure, source-independent semantics and oracles,
  and deterministic content-addressed blueprint projection. Static completion
  remains separate from optional empirical reconstruction, ordinary work stays
  affected-only, and no blueprint command launches reconstruction automatically.
- Added model-driven pre-release architecture reduction guidance that permits
  removal or collapse only with current equivalence evidence and keeps public
  delegation facades only when their exact owner and primary-path delegation
  evidence is current.
- Preserved content-addressed validation evidence under deep Windows worktrees
  by using extended-path reads and atomic writes.
- Removed user-specific absolute paths from the public model fixtures and
  archived coordination baseline before publication.

## v0.68.4 - 2026-08-02

- Added an independently derived TaskCoverageDemand so task facts determine
  the minimum modeling owners and depth while callers may only add coverage.
- Added canonical maturation receipt publication and verification, then bound
  implementation admission, risk confidence, closure, and code structure to
  the same exact verified model identity.
- Materialized the upgraded understanding path in FlowGuard's own executable
  models, behavior commitments, affected topology, and model/test alignment.
- Simplified the ordinary AI route into a short facts-to-demand workflow while
  keeping deeper ModelMesh, Model-Test Alignment, TestMesh, and release rules
  reachable through explicit conditional protocols.

## v0.68.3 - 2026-08-01

- Added task-local model-maturation intake that combines independently owned
  coverage and accepts resolved model angles only with exact current proof.
- Separated model sufficiency from implementation authorization: read-only
  work remains no-code, normal implementation requires closed current
  maturation, and explicitly bounded work can use a scoped authorization.
- Bound risk, closure, and code-structure readiness to the same maturation and
  admission identities so a complete-looking diagram cannot certify code by
  itself.
- Updated FlowGuard entry guidance and specialist protocols to report model
  depth and implementation admission separately while preserving lightweight
  use and target-software roles.

## v0.68.2 - 2026-08-01

- Narrowed the ordinary FlowGuard entry to route selection and a minimum
  valuable model, while loading deeper modeling guidance only when the chosen
  route or an observed gap requires it.
- Replaced order-based route fallback with explicit positive, forbidden, and
  conflict conditions, and completed the public route table without changing
  the existing route ownership boundaries.
- Made prompt-budget checks derive the real local reference load graph and
  require usable headroom instead of treating an incomplete declared bundle as
  proof that the entry is lightweight.
- Tightened existing-model ownership projection to exact logical identity,
  normalized path identity, or matching fingerprints rather than basename-like
  guesses.
- Added a pointer-free `model-revision-build` handoff that accepts only an
  exact-current terminal-pass full model-regression parent receipt and emits
  typed content-addressed candidate/revision artifacts for the existing atomic
  activation command.

## v0.68.1 - 2026-07-31

- Closed the clean-clone project-audit gap by keeping the adopted package
  version and generated project rules aligned with the released package.
- Kept every FlowGuard skill inside its frozen prompt budget by compressing the
  shared generated rules while preserving the protected behavioral guidance.
- Restored strict-validation parity with the CI-pinned OpenSpec `1.3.1` parser
  without weakening the current requirement semantics.

## v0.68.0 - 2026-07-31

- Replaced the permissive model-maturation reader with one strict current-only
  task, coverage, probe, candidate, receipt, gap-lineage, and predecessor
  contract; former payload shapes now fail visibly.
- Made caller-authored resolution and self-reported understanding powerless:
  only exact current target-native producer receipts can resolve a gap.
- Added multi-iteration progress, stall, oscillation, limit, external-boundary,
  and non-vacuous closure checks plus executable positive and negative tests.
- Bound every maintained FlowGuard skill to an explicit target-owned
  `model_deepening_check_id` for SkillGuard supervision.

## v0.67.0 - 2026-07-31

- Added task-local iterative model maturation with prediction, falsifier,
  gap-transition, progress, and explicit terminal records.
- Added a native CLI review route and regression coverage; matching local
  perturbations no longer close a task while addressable model gaps remain.

## v0.66.0 - 2026-07-30

- Added a read-only model-miss diagnostic projection that derives
  deterministic deletion-minimal conflicts from exact observation, model,
  code/test, and failure-boundary atoms while preserving the existing
  Model-Miss Review owner decision.
- Made bounded incompleteness explicit when oracle budgets expire and attached
  per-atom necessity witnesses, stable ordering, and the diagnostic algorithm
  version instead of overclaiming a global or unique minimum.
- Added positive non-vacuity witnesses and repair-candidate checks that reject
  obligation deletion, unpreserved positive behavior, and missing intended
  rejection reasons before routing an accepted candidate to Model-Test
  Alignment.
- Extended the public API, model-miss skill guidance, executable native runner,
  focused tests, model-purpose closure, and observed model-system authority for
  the new evidence surface.
- Kept the release source-only: the immutable annotated tag is the release
  authority and the GitHub Release has zero uploaded assets.

## v0.65.1 - 2026-07-28

- Restored strict-validation parity between the CI-pinned OpenSpec `1.3.1`
  parser and the current `1.6.0` parser for four wrapped requirement openings
  across three canonical specs without changing their requirement semantics.
- Preserved immutable `v0.65.0` history and published this correction as a
  source-only patch release after both parsers passed all 99 current specs.

## v0.65.0 - 2026-07-28

- Replaced broad, self-reported freshness with a frozen validation-owner DAG,
  resource-wide single-flight leases, supervised child processes, exact child
  receipts, and one independently verified full parent receipt.
- Made model authority inventory-complete and revision transactions
  independently derived, closure-complete, live-rechecked, CAS-protected, and
  rollback-replayable.
- Reconciled all 77 historical OpenSpec changes against current product
  direction, restored still-current requirements, retired obsolete topology
  and compatibility authority, and added byte-exact semantic sync checks.
- Added explicit complete/scoped UI evidence claims, package-authority shadow
  verification, behavior-bearing callable fingerprints, and StructureMesh
  child ownership for process supervision and the package API registry.
- Folded in the unreleased 0.64.2 validator-toolchain parity repair so current
  requirements parse under both the CI-pinned and current OpenSpec parsers.
- Kept the release source-only: the immutable annotated tag is the release
  authority and the GitHub Release has zero uploaded assets.

## v0.64.2 - 2026-07-28

- Made the affected OpenSpec requirement statements valid under both the CI-
  pinned OpenSpec `1.3.1` parser and the current local `1.6.0` parser by
  placing the normative `SHALL` clause in each requirement's opening line.
- Kept the v0.64.1 runtime and release-authority behavior unchanged; this
  patch closes only the validator-toolchain parity gap exposed by GitHub CI.
- Preserved immutable `v0.64.0` and `v0.64.1` history; v0.65.0 incorporates
  this unreleased patch intent without moving either immutable tag.

## v0.64.1 - 2026-07-28

- Closed a clean-clone authority gap by requiring the selected observed
  snapshot and every resolved model input to be Git-tracked before local
  release confidence.
- Added the 49 model and runner inputs that v0.64.0 referenced from the ignored
  local `.flowguard/` tree but did not include in its committed source tree.
- Added observed missing-model and same-class missing-runner regressions and
  made published annotated-tag lookup safe across Windows command wrappers.
- Preserved immutable `v0.64.0` history and published the correction as a
  source-only patch release after clean-clone project audit; CI later exposed
  the OpenSpec `1.3.1` parsing gap corrected in v0.64.2.

## v0.64.0 - 2026-07-28

- Replaced unconditional full validation with a deterministic native owner
  plan whose rows are `execute`, `reuse_current`, or `blocked`, backed by
  immutable independently verified child receipts and single-flight leases.
- Preserved successful child evidence across parent failures so later runs
  execute only missing, failed, or stale owners and cheaply recompose the
  exact parent receipt.
- Split model-local identity from the global model-system snapshot revision and
  Git release provenance, preventing an unrelated model change or commit from
  invalidating unchanged sibling models.
- Added the v3 model regression impact map with explicit local/shared/
  snapshot-only ownership and zero-producer fail-closed behavior for unknown,
  conflicting, malformed, or tampered inputs and receipts.
- Replaced mtime release freshness with separate content-addressed
  `ValidationInputManifest` and `ReleaseTreeManifest` identities, exact parent
  receipt verification, and immutable local-tag/published release checks.
- Direct-migrated the maintained FlowGuard skills, OpenSpec lifecycle, model
  authority, and source-only fifteen-skill consumer projection to the current
  contracts without compatibility readers or fallback execution paths.

## v0.63.0 - 2026-07-27

- Made Existing Model Preflight select the same-plane owner closure before
  materializing model bodies, with distinct light/full projections and an
  explicit broad-authority mode.
- Added combined first-read prompt-bundle budgets and reduced the always-loaded
  project guidance while preserving each consumer skill's independent hard
  gates and route ownership.
- Added artifact-backed compact terminal envelopes for model and skill
  validation so successful child payloads and stream tails are not repeated,
  while failed, blocked, skipped, and not-run children remain visible.
- Required explicit behavior-source admission for WorkContext coverage, made
  Behavior Commitment Ledger discovery breadth follow its change mode, and
  prevented ordinary existing-ledger work from silently becoming bootstrap.
- Strengthened test-result reuse with independent producer terminal receipts,
  execution-owner matching, and exact producer/current fingerprints for
  command, source, artifact, dependencies, environment, result, and scope.
- Updated the existing FlowGuard models and maintained skill routes in place,
  retained source-only immutable release authority, and synchronized the clean
  fifteen-skill consumer projection.

## v0.62.0 - 2026-07-26

- Replaced the OpenSpec-specific `SpecContext` surface with a provider-neutral,
  content-addressed, project-bounded read-only `WorkContext` registry and peer
  adapters for OpenSpec and explicitly declared files such as Spec Kit,
  Superpowers, custom skills, and ordinary planning documents.
- Added an independently derived exact expected-coverage inventory that joins
  WorkContext, observed UI, and field discovery before the Behavior Commitment
  Ledger assigns exactly one modeled, delegated, or scoped disposition.
- Strengthened UI and field completeness with immutable inventory revisions,
  discovery evidence, content fingerprints, exact ownership, field default /
  absence / serialization / privacy semantics, and conflicting-disposition
  rejection.
- Made TestMesh distinguish executed, delegated, and scoped coverage without
  treating provider status as test evidence, and made model-authority audits
  compare the selected snapshot with the current live manifest and exact
  owner/source inventories.
- Extended whole-system revision sets to account exact changed source-surface
  ids and every owner-artifact coverage dimension before atomic activation.
- Upgraded the existing FlowGuard skill routes and SkillGuard contracts in
  place, removed provider execution/session/cache/receipt bridges and retired
  SpecContext aliases, and retained source-only immutable release authority.

## v0.61.0 - 2026-07-23

- Added one durable authoritative observed-model system snapshot with explicit
  separation between observed implementation, normative target, and isolated
  counterfactual experiment lanes.
- Added content-addressed model instances, typed cross-model relations, six
  coverage dimensions, exact subject revisions, and authority-first existing
  model preflight so discovery evidence can no longer masquerade as current
  authority.
- Added whole-revision-set activation and operational rollback with shared
  compare-and-swap locking, pointer-last persistence, affected-closure
  fingerprints, prediction/replay evidence, and required effect restoration or
  forward repair for irreversible changes.
- Integrated model authority into project audit, regression receipts, the
  command line, public API, behavior commitment ownership, and the existing
  FlowGuard skill routes without creating a parallel workflow.
- Split the former oversized authority implementation into schema, revision,
  persistence, and inventory owners; centralized the fixed skill-suite
  inventory; and removed the absent lightweight model-miss-review ghost route.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.60.0 - 2026-07-22

- Added strict `flowguard.portable_system.v1` system definitions, verification
  requests, and exact declared-graph slices with separate canonical identities.
- Added bounded joint-system compilation and a stage-aware composition report
  that distinguishes `pass`, `fail`, `blocked`, `invalid`, and `not_run`, maps
  counterexamples back to components, and invokes the canonical system checker
  at most once.
- Added `portable-system-check`, Python API exports, and three benchmark
  families covering retry identity, permission revocation, and deletion
  propagation with bad, repaired, missing-semantics, and truncated variants.
- Extended the existing portable-composition behavior commitment, executable
  model evidence, regression manifest, tests, and affected FlowGuard skill
  guidance without adding a second runtime owner or a new satellite skill.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.59.0 - 2026-07-22

- Added one manifest-backed `python -m flowguard simulator` surface for model
  listing and explicit selected/all-model execution while preserving every
  model's native runner as its sole domain-result owner.
- Replaced full stdout/parsed-payload replication in model and unified release
  validation with deterministic compressed content objects, bounded
  diagnostics, hashes, and artifact references.
- Added terminal run manifests, atomic scoped current heads, read-only evidence
  audit/GC planning, exact quarantine/restore, and separately authorized purge;
  ordinary validation never silently cleans persistent evidence.
- Registered two previously unaccounted checkout-local models as
  `optional_local`, refreshed one stale model-purpose fingerprint, and extended
  the existing structure-surface model with simulator-takeover, duplicate-
  payload, and automatic-purge known-bad cases.
- Clarified that executable model source is small and distinct from generated
  evidence, build products, installed consumer skills, and extra local
  worktrees.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.58.5 - 2026-07-19

- Refreshed every FlowGuard skill's private author-side SkillGuard contract
  with the current affected-only validation ownership and provenance model.
- Kept graduated consumer skills clean: author contracts and receipts remain
  excluded from the installed projection, with no fallback or compatibility
  runtime.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.58.4 - 2026-07-19

- Corrected the v0.58.3 artifact-ownership model miss: a numeric
  `schema_version`, producer label, FlowGuard-looking prefix, scan path, or
  partial ledger shape no longer grants FlowGuard write authority.
- Added an exact current-only registry for real FlowGuard `report` and `trace`
  envelopes. Current shapes remain byte-identical; malformed, old, future, and
  unsupported versions block without writing because no evidence-bound
  migrator exists.
- Retained one repository-history-backed behavior-ledger writer, bounded to
  the exact complete bare producer shape from commit `56083c1e`. It
  materializes the full current canonical envelope at the upgrade boundary;
  target-only extra fields and old/future BCL envelopes never enter it.
- Required explicit upgrade-AI plane/actor dispositions in legacy row metadata;
  actor, owner, label, trigger, and commitment-kind text are never used to
  guess new current semantics.
- Migrated historical `primary_path_ids` explicitly at that boundary: zero or
  one value becomes the current singular field, while multiple values block
  for an evidence-bound disposition. No generic version-field writer,
  fallback, dual reader, or compatibility parser was added.
- Removed the normal-runtime plural path reader and its
  `legacy_plural_migrated` / `primary_path_migration_ambiguous` state. The BCL
  loader now requires the exact current envelope field set, current schema and
  format versions, and a canonical current payload.
- Updated the bundled public BCL template to emit that complete current
  canonical payload directly; template loading never fills omitted fields or
  consults a compatibility reader.
- Added a real non-editable-package regression that migrates a historical
  FlowGuard behavior ledger while proving a Khaos-style target fixture remains
  byte- and SHA-256-identical in the same `project-upgrade` run.
- Extended both public upgrade models with target-owned JSON, full
  legacy-lookalike extra-field, and unsupported-envelope known-bad cases.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.58.3 - 2026-07-19

- Corrected the v0.58.2 deployment-topology miss: ordinary project audit and
  upgrade no longer look for the author-only suite map through an editable
  package layout.
- Added one deterministic package-owned clean-consumer authority containing
  the exact 15 member ids and complete projected file fingerprints, including
  generated consumer-release manifests.
- Made ordinary project writes require exact package-authority parity with the
  global `$CODEX_HOME/skills/` projection and its ownership manifest. Missing,
  modified, reserved-extra, or author-control-polluted consumers block visibly.
- Added a real non-editable package regression that installs into an isolated
  target directory, upgrades a genuinely empty ordinary project, verifies the
  expected writes, and passes the subsequent project audit.
- Kept author suite maps, SkillGuard contracts, receipts, and check execution
  outside the installed consumer and ordinary project runtime. No fallback,
  alternate reader, compatibility path, or project-local shadow suite was
  added.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.58.2 - 2026-07-18

- Repaired an ordinary-project authority regression: generated minimum
  revalidation now invokes only the installed package audit and no longer
  requires the author-repository `verify_skill_suite_markers.py` script.
- Made the one clean consumer projection under `$CODEX_HOME/skills/` the sole
  FlowGuard skill authority for ordinary projects; adopted projects do not
  receive a second `.agents/skills` tree or suite map.
- Added executable temporary-project regressions proving project adoption,
  audit, and minimum revalidation work without local `scripts`,
  `.agents/skills`, or `.skillguard` directories.
- Preserved the author-maintenance boundary: the canonical suite map, full
  fifteen-member SkillGuard validation, and generated author contracts remain
  owned by the FlowGuard source repository.
- Kept one direct current path only; no alias, fallback, compatibility reader,
  or shadow-suite authority was added.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.58.1 - 2026-07-18

- Corrected a v0.58.0 model miss in project audit and upgrade: suite
  reconciliation now uses the canonical map from the current FlowGuard package
  source and the clean consumer projection from the current installed Codex
  skills root.
- Added a regression proving ordinary projects need no `.skillguard` directory
  or local FlowGuard skill suite, while missing or mismatched installed
  consumer skills still block before mutation.
- Retained one direct current path only; no target-local compatibility reader,
  alias, or fallback was added.
- Removed the Python 3.10 hand-written TOML parser fallback and made Python
  3.11+ with the standard-library `tomllib` parser the sole current runtime
  path.
- Removed the unused `run_flowguard_self_governance.py` forwarding alias; the
  sole current command is `check_flowguard_self_governance.py`.
- Removed stale regression-manifest registrations for the already retired
  SpecContext and task-local replay models and refreshed the changed
  ModelMissReview purpose identity.
- Made CI materialize the current clean consumer skill projection before the
  project-adoption audit, so a clean runner follows the same declared install
  path instead of depending on undeclared machine state.

## v0.58.0 - 2026-07-18

- Renamed the canonical kernel skill directly from
  `model-first-function-flow` to `flowguard`; no alias, forwarding stub,
  compatibility reader, or fallback path remains.
- Reduced the public Codex surface from seventeen to fifteen skills by moving
  plan detailing and agent-workflow rehearsal into two explicit internal
  routes owned by `flowguard-development-process-flow`.
- Consolidated all fifteen author sources into the single
  `unit:flowguard-suite` SkillGuard maintenance unit while preserving each
  public satellite's native route and check authority.
- Made source tags the sole release authority: v0.58.0 releases contain no
  wheel, source-distribution, or downloadable package assets.
- Added explicit author-source and consumer-distribution parity roles so
  consumer projections are compared without author-only SkillGuard material.

## v0.57.0 - 2026-07-16

Portable compositional-verification kernel release.

- Added a strict, versioned, JSON-serializable finite model IR with canonical
  identities, explicit invariants and temporal obligations, and fail-closed
  rejection of unknown or dangling schema content.
- Added a code-independent reference checker for nondeterministic traces,
  safety, terminal progress, universal and bounded eventuality, weak fairness,
  visible truncation, and smallest counterexample preservation.
- Added explicit child-to-parent refinement and assume/guarantee composition
  checks, including state/transition mappings, stutter declarations,
  assumption weakening, guarantee strengthening, provider closure, and
  conflict detection.
- Exposed one narrow Python API and CLI cohort, registered the kernel in the
  model-regression manifest, and updated ModelMesh, topology-hazard, and
  model-first skill contracts without adding a duplicate public route.
- Revalidated the project artifacts with official OpenSpec 1.6.0. This local
  release deliberately excludes GitHub push, remote tag, and GitHub Release
  evidence.

## v0.56.0 - 2026-07-15

Guard-purpose closure and generic declared-check supervision release.

- Added executable model-purpose contracts so every FlowGuard model declares
  the concrete bad behavior it is intended to block for the current modeling
  task, the accepted boundary, observable evidence, and the safe claim that a
  passing model licenses.
- Propagated purpose evidence through model review, model/test alignment,
  TestMesh, development-process closure, and the complete seventeen-skill
  agent suite without turning SkillGuard into a domain-semantics owner.
- Replaced former SkillGuard authorities with the sole current generic
  declared-check contract shape: exact target-owned checks, one execution
  owner per check, current immutable receipts, fixed `enforced` closure, and no
  selectable quality or integration mode.
- Hardened multi-skill validation ownership, installation projection,
  OpenSpec receipt reuse, stale-evidence rejection, interrupted-process
  cleanup, and source/toolchain identity binding.
- Updated models, contracts, templates, documentation, examples, fixtures,
  OpenSpec work packages, and regression coverage for the direct-current
  release boundary.

## v0.55.0 - 2026-07-12

FlowGuard product-language, behavior-plane, and validated-path reuse hardening.

- Partitioned behavior commitment lookup by execution plane while preserving
  typed actor/relationship bindings and canonical ledger I/O, so plane-aware
  discovery composes with existing commitment ownership instead of replacing
  it.
- Added stable exact business-intent identity, one active commitment per exact
  external promise, one singular selected primary path, deterministic one-item
  legacy plural migration, complete affected-surface/candidate inventories, and
  material current runtime/proof requirements.
- Extended the existing UI Flow Structure owner with product-scope typography,
  component, navigation, interaction, feedback, recovery, and transition
  consistency; repeated business surfaces bind the same commitment/path, while
  pure UI interactions stay local.
- Kept UI content admission exactly `user_visible`, `user_on_demand`, or
  `internal`; internal intent, commitment, path, audit, evidence, and diagnostic
  ids remain outside ordinary UI.
- Hardened RuntimePathEvidence, ObligationFamily, Model-Test Alignment,
  Architecture Reduction, ContractExhaustionMesh, TestMesh, and
  DevelopmentProcessFlow against omitted inventories, opaque handoff ids,
  sibling-obligation evidence, parallel facade success, stale proofs,
  progress-only background runs, cross-domain sync overclaims, and peer-write
  rollback.
- Updated OpenSpec requirements, existing FlowGuard models, tests, templates,
  public API guidance, skill prompts/contracts, local installation parity, and
  non-destructive shadow/formal/Git synchronization evidence without adding a
  product-language route, path-reuse route, intent ledger, or evidence engine.
  Added the read-only `behavior-commitment-query` command under the existing
  Behavior Commitment Ledger / Existing Model Preflight owners; it is not a new
  FlowGuard route and does not execute the retrieved commitment.
- Migrated all seventeen bundled skills to `skillguard.contract_source.v2`
  with existing-owner model projections, generated V2 contracts/manifests, and
  `contract_mapped` depth profiles. Static contract-depth certification remains
  distinct from actual execution-depth receipts and adds no parallel executor.

## v0.54.1 - 2026-07-10

FlowGuard published-release verification compatibility patch.

- Resolve external commands through the operating system executable search so
  Windows `PATHEXT` shims such as `git.CMD` work in published verification.
- Convert missing external commands into structured failed checks instead of
  terminating the verifier with an unhandled process-launch exception.
- Correct annotated-tag verification by comparing the local release commit
  with the remote tag's peeled commit while retaining lightweight-tag support.

## v0.54.0 - 2026-07-10

FlowGuard skill-suite governance and verified distribution release.

- Rebuilt the canonical seventeen-skill agent suite around concise,
  route-specific prompts, typed ownership, deterministic contract sources,
  generated native-integrated SkillGuard records, and 17/17 deep checks.
- Added immutable evidence receipts whose freshness, covered obligations,
  producer/checker context, child consumption, and proof-artifact bindings are
  independently recomputed instead of accepted from caller-supplied flags.
- Hardened FlowGuard self-governance so broad success requires current exact
  child passes, a complete parent receipt, and visible blocked/scoped/stale or
  skipped states; synthetic in-memory green reports no longer satisfy closure.
- Added a typed route topology with unique owners, bounded cycles, route-parity
  checks, and explicit delegated/internal/public handoffs.
- Productized local model validation with a checked-in inventory, fast,
  focused, and full tiers, filters, shards, bounded parallelism, per-runner
  timeouts, mutation detection, progress events, isolated artifacts, and
  terminal receipts.
- Added safe, idempotent skill install/check/uninstall/parity commands with
  ownership manifests, explicit legacy adoption, user-change conflict
  protection, temporary-home tests, and complete source/shadow/installed tree
  comparison.
- Repaired project adoption integrity, stable rule identities, dry-run
  guarantees, concise validation output, bilingual documentation, and
  OpenSpec verification contracts for the complete upgrade program.

## v0.53.1 - 2026-07-09

FlowGuard self-maintenance gate hardening.

- Added strict Behavior Commitment Ledger self-maintenance checks so FlowGuard
  workflow changes must keep behavior registration, DCAR coverage,
  TestMesh routing, and model-miss backfeed connected before broad confidence.
- Extended behavior commitment records with source freshness, replacement
  synchronization, TestMesh alignment, model-miss status, and change-mode
  handling for new, changed, replacement, discovery, and model-miss work.
- Updated FlowGuard agent skills, templates, public APIs, CLI rendering, and
  tests so missing ledger coverage blocks immediately instead of leaving an
  alternate success path.

## v0.53.0 - 2026-07-08

Behavior Commitment Ledger, Primary Path Authority, and no-fallback coverage.

- Added `behavior_commitment` as the upstream Behavior Commitment Ledger route
  so broad work inventories every external, verifiable behavior commitment
  before assigning one primary owner model and downstream evidence.
- Connected path-sensitive behavior commitments to `primary_path_authority`, so
  the ledger owns full behavior registration while PPA owns single primary path
  authority and rejects alternate success after primary failure.
- Added `primary_path_authority` as a first-class FlowGuard route so each
  path-sensitive business intent declares one primary runtime authority and
  rejects automatic alternate success after primary failure.
- Wired no-fallback evidence through RuntimePath observations,
  RiskEvidenceLedger gates, public API/CLI/template surfaces, AGENTS guidance,
  and installed FlowGuard skill shells.
- Added model-scoped Cartesian coverage for the primary-path boundary with
  actionable oracle binding, TestMesh shard ownership, and downstream risk
  evidence consumption.
- Published the previously untagged OpenSpec readiness verification commit and
  included validated OpenSpec records for ContractExhaustionMesh,
  hierarchical Cartesian coverage, and helper control-plane consolidation.

## v0.52.6 - 2026-07-07

Guard-family simulation readiness patch.

- Restored route-specific diagram intent guidance in the model-first kernel so downstream Guard skills are not flattened into generic flowcharts.
- Hardened FlowGuard SkillGuard work contracts so duplicate SkillGuard-owned execution paths are invalid while native FlowGuard checks remain authoritative.
- Added OpenSpec release tracking and source-side regression coverage for the prompt contract.

## v0.52.5 - 2026-07-06

Model-code-test closure hardening.

- Added first-class optional source-audit gating to Model-Test Alignment for
  real-code claims, including missing, failed, and unrelated-audit blockers.
- Expanded `ModelCodeTestBindingRow` into a behavior closure summary with owner
  code, path/symbol, tests, boundary/runtime/payload ids, source-audit decision,
  and open gap codes.
- Added target-aware counterexample and known-bad replay closure through
  external owner-code-bound `TestEvidence`.
- Added structured runtime writer-inventory evidence for Runtime Gateway
  Adoption and updated public docs, templates, skills, and tests.

## v0.52.4 - 2026-07-03

FlowGuard skill-suite distribution.

- Reframed public onboarding around `.agents/skills/` as the primary AI-agent
  skill-suite surface, with `model-first-function-flow` as the default
  entrypoint and sibling FlowGuard skills kept visible.
- Clarified that the Python `flowguard` module and CLI are executable
  check-engine support, not the AI-agent skill installation surface.
- Added skill-suite marker verification and updated project adoption templates,
  docs, and tests so repository, installed Codex skills, and generated AGENTS
  guidance stay aligned.
- Archived the `reframe-flowguard-as-skill-suite` OpenSpec change into the main
  specs and refreshed release-scope evidence.

## v0.52.3 - 2026-06-27

- Added SkillGuard runtime-contract governance for the installed FlowGuard Codex skill materials.
- Synchronized installed skill copies with accepted source material and local git evidence.
- Recorded release-scope validation so route selection, evidence gates, quality floors, and closure boundaries remain visible before completion claims.

## v0.52.2 - 2026-06-25

FlowGuard current-situation visibility.

- Added lightweight current-situation guidance so non-trivial FlowGuard work
  tells users what is being checked, why it matters, current evidence or gaps,
  and the next step before or with Mermaid snapshots.
- Updated the shared agent snippet, model-first kernel, and direct FlowGuard
  satellite skills with concise status-note wording while preserving hot-path
  prompt budgets and existing route ownership.
- Archived the OpenSpec change into `flowguard-model-visibility` and
  `user-facing-model-diagrams`, and refreshed local model checks so diagram-only
  prompt rollouts without current-situation notes are rejected.

## v0.52.1 - 2026-06-20

FlowGuard self-maintenance and release hygiene.

- Archived the completed ContractExhaustionMesh OpenSpec changes into the main
  specs so the active change list is clean before publication.
- Re-ran FlowGuard self-maintenance, DevelopmentProcessFlow, Model/Test/Code
  alignment, TestMesh, and StructureMesh checks and kept the current route
  structure unchanged because no model-backed split or field deletion was
  required.
- Prepared a source-only patch release that aligns public version metadata,
  project adoption records, changelog, README, Git tag, and GitHub Release.

## v0.52.0 - 2026-06-20

Contract coverage universe and observed-problem backfeed.

- Added `ContractCoverageUniverse`, scoped exclusions, and broad-claim gates so
  ContractExhaustionMesh can prove the declared coverage universe is present
  instead of only proving the generated matrix is internally consistent.
- Added generic `ContractFaultProfile` and `ObservedProblemBackfeed` helpers so
  downstream systems can rehearse bad contract submissions and map real misses
  back to generated, same-class, and coverage-receipt evidence without a
  FlowPilot-specific fake-AI API.
- Updated route profiles, skills, docs, templates, OpenSpec change records, API
  exports, and regression tests for actionable oracle feedback and universe
  completeness.

## v0.51.0 - 2026-06-16

Hierarchical Cartesian contract-exhaustion coverage.

- Added model-scoped axes, interaction groups, generated combination cases,
  coverage shards, and coverage receipts so ContractExhaustionMesh can produce
  finite bad-case matrices per model instead of relying on hand-written
  representative examples.
- Wired generated combination obligations into Model-Test Alignment, TestMesh,
  ModelMesh, RiskEvidenceLedger, bug-family records, and model-miss review so
  a green single-point matrix cannot be mistaken for a closed parent/child
  model chain.
- Updated FlowGuard route profiles, skills, templates, OpenSpec tasks, docs,
  topology, and regression tests so future AI agents see the Cartesian
  coverage checklist and required handoffs before claiming completion.

## v0.50.0 - 2026-06-15

Helper control-plane consolidation.

- Added first-class route-role metadata to `RouteProfile` so public owner
  routes, delegated modes, internal feeders, data helpers, and cleanup
  dispositions are machine-checkable instead of prompt-only guidance.
- Split public route discovery from advanced/internal helper inventories so
  `FLOWGUARD_ROUTE_API` and `ROUTE_STARTER_API` expose owner routes while
  simulator, model-angle, similarity, maintenance-scan, closure, and
  state-closure helpers remain owner-consumed evidence.
- Updated FlowGuard skills, AGENTS guidance, API docs, topology docs, project
  adoption generation, self-maintenance models, and regression tests so
  DevelopmentProcessFlow, ExistingModelPreflight, ContractExhaustionMesh,
  ArchitectureReduction, and RiskEvidenceLedger own the single hot path without
  helper-first fallback routes.

## v0.49.0 - 2026-06-15

Development-process simulator entry consolidation.

- Added `development_process_simulator` helpers so rough-plan discussion,
  multi-skill workflow setup, staged execution, install/sync, release/archive,
  publish, and final process claims enter `flowguard-development-process-flow`
  first with ordered `plan_detailing`, `agent_workflow`, and
  `execution_freshness` modes.
- Reframed PlanDetailing Compiler and AgentWorkflowRehearsal as explicit or
  simulator-delegated mode owners instead of competing generic first entries.
- Updated Codex skill prompts, OpenAI metadata, AGENTS guidance, README, API
  docs, current OpenSpec specs, and active plan-discussion change notes to
  remove stale direct/peer route wording.
- Added routing/model/API/docs regression coverage so old rough-plan and
  multi-skill hot-path wording is rejected.

## v0.48.0 - 2026-06-15

Single formal FlowGuard model entry.

- Added structured `KnownBadProof` review so new or deepened models must prove
  representative broken cases are caught before broad FlowGuard claims.
- Hardened `RiskIntent`, `MinimumModelContract`, template reuse/no-match, and
  runner summary gates so missing protected errors, completion evidence,
  known-bad proof, or template closure blocks instead of silently passing.
- Removed direct `Explorer` from the agent-default API, migrated public
  templates and model-first skills to `FlowGuardCheckPlan` +
  `run_model_first_checks(...)`, and added adoption audit warnings for
  direct-Explorer-only current models.

## v0.47.3 - 2026-06-15

ModelMesh closure and retry/rejection liveness hardening.

- Made parent/child ModelMesh confidence require closure modeling whenever child
  outputs, reattachment contracts, or runtime path evidence are present.
- Added repeated-input retry/rejection closure fields, repair-feedback and
  blocker/progress checks, ModelMesh closure transition projection into
  Model-Test Alignment/TestMesh, and regression tests for stuck-loop hazards.
- Updated skills, templates, docs, OpenSpec coverage, field inventory, public API
  exports, and template/CLI known-bad proof wiring so current evidence, tests,
  and installed skills agree on the strengthened contract.

## v0.47.2 - 2026-06-13

UI functional capability coverage.

- Added UI functional capability inventories, capability/output contracts,
  capability bindings, and coverage review so required user-visible UI
  functions cannot disappear before broad UI completion claims.
- Wired capability coverage into implementation validation, human-operability,
  PlanDetailing, Model-Miss Review, DevelopmentProcessFlow, RiskEvidenceLedger,
  AgentWorkflowRehearsal, and ClosureContract without creating a parallel UI
  route.
- Updated UI skills, public templates, docs, API/field inventory, OpenSpec
  artifacts, and regression tests so greenfield, source-based, and mixed UI
  work use the same generic capability layer.

## v0.47.1 - 2026-06-13

Plan discussion handoff hardening.

- Promoted PlanDetailing as the direct FlowGuard route for non-trivial plan,
  acceptance, rough-outline, and AI-generated workflow discussions before
  execution routes consume the plan.
- Added AgentWorkflowRehearsal completion-ledger report fields for planned,
  completed, blocked, skipped, required-recheck, handoff, and final-claim
  boundaries.
- Updated skill routing docs, public templates, OpenSpec coverage, API/field
  docs, and regression tests so long prose plans no longer count as completion
  or release evidence.

## v0.47.0 - 2026-06-13

Generic UI source-baseline validation.

- Added generic `greenfield`, `source_based`, and `mixed` UI work-mode modeling
  plus source baseline, target mapping, approved difference, observed-source
  alignment, and source interaction review helpers.
- Replaced source-specific UI migration wording, APIs, process/risk gates,
  closure evidence, agent-workflow roles, public templates, docs, and active
  OpenSpec changes with generic source-baseline terminology.
- Added regression coverage so active skills, templates, docs, and OpenSpec
  guidance do not hard-code a specific source UI technology while still
  allowing historical archive records.

## v0.46.0 - 2026-06-12

Mandatory template harvest closure.

- Added `TemplateHarvestReview`, accepted harvest dispositions, not-harvestable
  reasons, and `review_template_harvest_closure(...)`.
- Extended check plans, audit, runner summaries, CLI, public API exports, and
  starter templates so new or materially deepened models must close template
  harvest as written, merged, duplicate-linked, or accepted not-harvestable.
- Updated FlowGuard skills, AGENTS snippet, modeling protocol, README, API docs,
  OpenSpec coverage, and self-model evidence so template absorption is a hard
  completion gate rather than optional "when useful" guidance.

## v0.45.0 - 2026-06-12

UI human-operability gate.

- Added user task coverage, region semantics, affordance contracts, action
  grammar, dialog/window return contracts, keyboard/focus contracts, human
  walkthroughs, and `review_ui_human_operability(...)`.
- Extended UI Flow Structure, Model Miss Review, PlanDetailing,
  DevelopmentProcessFlow, RiskEvidenceLedger, ClosureContract, and
  AgentWorkflowRehearsal so broad UI done/release confidence requires
  human-operability evidence, not only labels, routes, or click wiring.
- Updated public templates, API docs, UI docs, README, OpenSpec artifacts, and
  skill guidance so supported UI tasks must connect to function model features,
  UI journeys, primary controls, functional chains, feedback, cancel/error,
  keyboard/focus, native dialogs, and walkthrough evidence.

## v0.44.0 - 2026-06-12

Minimum valuable model entry and risk-template reuse.

- Added packaged public risk templates plus a portable per-machine local risk
  template library with search, review, merge, and harvest helpers.
- Raised the default AI model-first entry from a thin starter to a minimum
  valuable model that names protected errors, state/side effects, completion
  evidence, and known-bad cases.
- Updated RiskIntent, CheckPlan, audit, runner, model similarity, CLI,
  templates, skills, docs, and OpenSpec coverage so template reuse and local
  candidate absorption become part of normal model creation.

## v0.43.3 - 2026-06-12

UI real-surface validation hardening.

- Added observed real UI inventory, enabled-control functional chain, MATLAB
  baseline callback semantics, and UI model-miss review helpers.
- Added PlanDetailing, DevelopmentProcessFlow, RiskEvidenceLedger,
  ClosureContract, and AgentWorkflowRehearsal gates so UI completion requires
  typed current evidence and final done-claim review.
- Updated OpenSpec specs, FlowGuard skills, docs, templates, and API surface so
  labels, routes, planned evidence, and API existence cannot stand in for real
  UI click-through behavior.

## v0.43.2 - 2026-06-11

Artifact payload real-flow evidence tightening.

- Tightened Model-Test Alignment artifact payload validation so current
  external passing payload evidence must include an execution proof reference
  or proof artifact for the real payload surface.
- Updated FlowGuard skills, protocols, docs, and templates to describe
  synthetic payload cases as inputs for real import/export/save/load/generate
  or AI work-package surfaces, not standalone payload-only paths.
- Added regression coverage for declaration-only payload evidence and refreshed
  local sync guidance for repository, Gate, and installed Codex skill surfaces.

## v0.43.1 - 2026-06-11

Agent workflow rehearsal completion ledger upgrade.

- Added `planned_steps`, `completed_steps`, `blocked_steps`, `skipped_steps`,
  `required_rechecks`, `handoff_points`, and `final_claim_boundary` to
  `AgentWorkflowRehearsalReport`.
- Updated the AgentWorkflowRehearsal skill and protocol so multi-skill plans
  expose what is planned, what is blocked, what was skipped, which evidence is
  handed off, and why rehearsal is not execution proof.
- Added focused regression coverage for the new report fields.

## v0.43.0 - 2026-06-09

Writing quality-gate process upgrade.

- Added DevelopmentProcessFlow guidance for thesis and source-backed writing
  quality-gate evidence, including literature/technology progression,
  method-depth, figure/table treatment, citation/footnote support,
  source/trace handoff, AI-style integration, final prose, and revision-report
  freshness.
- Updated PlanDetailing and AgentWorkflowRehearsal skills so large writing
  plans and multi-skill workflows expose these quality gates before execution
  or done/release confidence.
- Updated public release metadata for the new process-surface guidance.

## v0.42.0 - 2026-06-08

Validation evidence gate upgrade for UI and artifact payload claims.

- Added Model-Test Alignment artifact payload helpers for file import/export,
  generated artifact, save/load, and AI work-package validation cases.
- Integrated payload contracts/evidence into `ModelTestAlignmentPlan` and the
  public API surface so missing, stale, internal-only, manual prose-only, or
  mismatched payload evidence blocks broad alignment claims.
- Added Risk Evidence Ledger gates for UI implementation evidence and artifact
  payload validation before done/release/full-confidence claims.
- Strengthened UI, Model-Test Alignment, TestMesh, DevelopmentProcessFlow,
  PlanDetailing, AgentWorkflowRehearsal, kernel guidance, docs, and templates
  so runnable UI claims require reachable control click-through evidence and
  payload/work-package claims require synthetic payload packs.

## v0.41.8 - 2026-06-07

AI-entry surface reduction for thinner default FlowGuard authoring.

- Added `ROUTE_STARTER_API`, `ROUTE_ADVANCED_API`,
  `PLAN_INTAKE_STARTER_API`, and `PLAN_INTAKE_ADVANCED_API` so agents can read
  compact route-specific entry points before full helper inventories.
- Made model-miss, model-test-alignment, and UI-flow template commands emit
  compact runnable defaults while adding explicit full-template commands for
  deep scaffolds.
- Added AI surface tier and route-owner metadata to the generated field
  lifecycle inventory so later field deletion can start from starter,
  advanced, and internal exposure evidence.
- Added a FlowGuard self-check model for AI-entry reduction and updated docs,
  skills, and tests to keep starter surfaces compact without hiding full
  escalation paths.

## v0.41.7 - 2026-06-07

Breaking field-schema cleanup for thinner AI-authored route inputs.

- Replaced route-specific `RiskEvidenceRow` gate columns with a compact
  `RiskEvidenceGate` list and updated ledger checks, docs, templates, tests,
  and local FlowGuard models to reject old field shapes.
- Removed AutoSplit metric fields from `ProcessEvidence`; split review now
  stays in AutoSplit, ModelMesh, or TestMesh evidence instead of being copied
  into development-process rows.
- Removed duplicate PlanIntake mapping/source evidence shapes and adapter
  fixture flags from normal mapping rows.
- Merged duplicate UI blindspot helper classes into `UIBlindspot` and reused
  `ProcessArtifact` in PlanDetail instead of maintaining a duplicate
  `PlanDetailArtifact` class.

## v0.41.6 - 2026-06-07

FieldLifecycleMesh route-evidence handoff binding.

- Added minimal `gate:`, `test:`, and `replay:` evidence-route checks for
  broad behavior-bearing field lifecycle claims while keeping bounded plans
  backward compatible.
- Updated the default replacement field-lifecycle model so full replacement
  claims require a route-bound field projection before disposal can close.
- Updated public templates, docs, tests, and installed skill guidance to make
  field models behave like route tracking instead of a field dictionary.

## v0.41.5 - 2026-06-07

Deep CI portability repair after v0.41.4.

- Fixed the shadow workspace sync helper so ignored project directories are
  evaluated relative to the source set instead of treating Linux system `/tmp`
  as a project `tmp` directory.
- Made the local closure-contract model-runner test skip gracefully when a
  GitHub checkout does not include ignored local `.flowguard` model artifacts.
- Kept the v0.41.4 maintenance hardening release intact and superseded it with
  this clean patch release instead of moving a public tag.

## v0.41.4 - 2026-06-07

Complete FlowGuard maintenance hardening.

- Added `AGENT_DEFAULT_API` as a compact first-read surface for agents while
  preserving the full route and helper API registry.
- Added tracked maintenance helpers for aggregate local `.flowguard` model
  regression and no-delete shadow workspace synchronization.
- Added a generated field lifecycle inventory so field reduction can start
  from ownership and lifecycle clues instead of text-search deletion.
- Split Model-Test Alignment Python source-audit execution into a dedicated
  module while preserving the original public imports.
- Split GitHub CI into fast push checks and scheduled/manual deep checks that
  include full unit and aggregate model regression.

## v0.41.3 - 2026-06-07

GitHub CI portability fix.

- Fixed artifact upgrade scanning so repository-relative ignored folders such
  as `tmp` are skipped without accidentally skipping Linux system temp roots.
- Kept public template privacy checks focused on real private markers while
  avoiding GitHub Actions' generic `runner` home directory false positive.
- Added regression coverage for the temp-root scan behavior exposed by CI.

## v0.41.2 - 2026-06-07

Post-release maintenance hygiene.

- Archived completed OpenSpec changes into the durable archive and kept the
  active change list focused on current work.
- Added a compact `default_flowguard_self_maintenance_plan()` helper so agents
  can start FlowGuard self-maintenance with route, API, AI-entry, and field
  defaults instead of manually filling the common plan fields.
- Added a minimal GitHub Actions CI gate for install, project audit, OpenSpec
  strict validation, the self-maintenance model, and focused unit tests.

## v0.41.1 - 2026-06-07

FlowGuard self-maintenance optimization.

- Added a route-first FlowGuard self-maintenance mesh with compact route
  profiles, AI entry profiles, field layer profiles, and child closure reports
  so agents can maintain FlowGuard without starting from the full helper list.
- Expanded public route grouping and API-surface tests so installed satellite
  routes are discoverable through stable route entries instead of scattered
  flat fields.
- Added OpenSpec coverage, a self-maintenance model, skill/docs updates,
  focused regression evidence, and shadow-workspace sync checks for the new
  maintenance path.

## v0.41.0 - 2026-06-07

Open-ended model-angle deliberation.

- Added `ModelAngleDeliberation`, `ModelAngleReviewReport`, and
  `review_model_angle_deliberations()` so agents must record what a current
  model sees, what it misses, what fails if ignored, and whether to reuse,
  extend, add a child model, create a new model, scope/defer, or ask for human
  review.
- Connected unresolved model-angle gaps to Existing Model Preflight,
  Maintenance Scan, Risk Evidence Ledger, and Closure Contract so broad
  confidence cannot hide a missing model viewpoint.
- Added `model-angle-template`, API/docs/skill guidance, OpenSpec coverage,
  focused tests, and FlowGuard self-model evidence for the new route.

## v0.40.12 - 2026-06-07

Guard-family closure contract upgrade.

- Added a reusable Guard closure contract checker for child Guard skills so
  passing claims cannot hide hard findings, missing inputs, stale evidence, or
  skipped checks.
- Updated the model-first skill guidance so SourceGuard, TraceGuard,
  LogicGuard, PhysicsGuard, research, and thesis workflows can hand AI agents
  structured next actions instead of relying on prose-only reminders.
- Added OpenSpec and FlowGuard self-model evidence for the closure-report
  maintenance path.

## v0.40.11 - 2026-06-06

Default replacement and field lifecycle hardening.

- Added FieldLifecycleMesh helpers, route-scoped API discovery, a public
  `field-lifecycle-template`, and a Codex skill route for complete leaf-level
  field accounting.
- Connected behavior-bearing field projections and old-field disposition to
  existing model preflight, code structure, architecture reduction,
  Model-Test Alignment, Model-Miss Review, DevelopmentProcessFlow, legacy path
  disposition, and Closure Contract.
- Updated project AGENTS guidance, docs, public templates, OpenSpec coverage,
  skill protocols, and FlowGuard self-model checks so replacement work cleans
  up old paths/fields by default unless compatibility is explicit and evidenced.

## v0.40.10 - 2026-06-05

AI route handoff optimization.

- Added structured owner-route, action, proof-gap, required-input, and claim
  boundary fields to SummaryReport findings, maintenance obligations,
  maintenance scan actions, and DevelopmentProcessFlow revalidation guidance.
- Added `maintenance_scan_plan_from_summary_report(...)` and
  `existing_model_preflight_from_project(...)` so agents can continue through
  existing FlowGuard routes instead of inventing a parallel session runner.
- Refreshed templates, compact skill guidance, API docs, OpenSpec artifacts,
  tests, and FlowGuard self-model evidence for the SummaryReport ->
  MaintenanceScan -> specialist-route handoff.

## v0.40.9 - 2026-06-04

Bug repair closure hardening.

- Broadened Model-Miss Review so non-trivial bug repairs use the existing
  model-miss route instead of falling back to implementation-only patches.
- Added root-cause backpropagation, owner code-contract binding, same-class
  evidence, legacy path disposition, DevelopmentProcessFlow freshness, and
  Risk Evidence Ledger closure requirements to the bug repair loop.
- Refreshed the public model-miss template, self-model, OpenSpec change,
  focused tests, and docs so model, code, and tests stay tied to the same
  repaired behavior before broad confidence.

## v0.40.8 - 2026-06-03

Soft UI typography hierarchy guidance.

- Clarified that UI text hierarchy blueprints are semantic handoff artifacts,
  not instructions to create one visual font size per hierarchy level.
- Updated FlowGuard UI Flow Structure guidance, templates, docs, and focused
  tests so typography noise is treated as a design smell with intentional
  exceptions rather than a hard numeric rule.
- Synced first-pass design, implementation review, and design iteration skills
  with calm hierarchy, reusable text treatment, and clear-rationale guidance.

## v0.40.5 - 2026-06-02

Maintenance obligation memory.

- Added route-owned `MaintenanceObligation` memory helpers so unresolved
  structure, evidence, model, and risk gaps can stay visible without creating a
  standalone technical-debt scanner.
- Extended summary reports, maintenance scans, model maturation, and Risk
  Evidence Ledger reviews so anchored open obligations reopen owner routes and
  broad confidence is blocked or scoped until obligations are resolved.
- Updated public templates, OpenSpec coverage, FlowGuard skills, docs, version
  records, and self-model checks for the maintenance-obligation memory flow.

## v0.40.4 - 2026-06-01

Model topology hazard review.

- Added `review_topology_hazards()` with `UsageIntent`, topology digests,
  anchored hazard candidates, confidence decisions, runner integration, and
  route-scoped API discovery.
- Added automatic `topology_hazard` summary sections to
  `run_model_first_checks(...)` so model-shape future-use hazards stay visible
  before broad done, release, publish, archive, or full-confidence claims.
- Connected topology hazard gaps to maintenance scan, Risk Evidence Ledger,
  public templates, OpenSpec artifacts, docs, Codex skill guidance, and
  FlowGuard self-model checks.

## v0.40.3 - 2026-06-01

Latest-schema-first upgrade policy.

- Added deterministic artifact upgrade scanning for old FlowGuard artifacts,
  model/test evidence, docs, scripts, and skill guidance.
- Extended `project-upgrade` so older adopted repositories upgrade known old
  artifacts by default, with `--records-only` for narrow record refreshes.
- Added the `artifact-upgrade` CLI, public report helpers, OpenSpec coverage,
  self-model checks, focused tests, and updated agent guidance.

## v0.40.2 - 2026-06-01

Automatic state/input closure gate.

- Added `review_state_closure()` with typed closure dimensions, representative
  unknown cases, safe handling policies, reports, and route-scoped API
  discovery.
- Added automatic `state_closure` summary sections to
  `run_model_first_checks(...)` so inferred unknown/other cases scope
  confidence by default and unsafe handling blocks confidence.
- Routed state closure maintenance gaps to `model_maturation_loop` and updated
  docs, skill guidance, OpenSpec artifacts, tests, and the FlowGuard self-model.

## v0.40.1 - 2026-06-01

FlowGuard field prompt reduction.

- Collapsed Model-Test Alignment, DevelopmentProcessFlow, TestMesh, ModelMesh,
  and adoption-log prompt fields into grouped field families.
- Preserved required evidence, freshness, boundary, skipped/not-run, release,
  and scoped-gap fields while moving rare details behind expand-when-applicable
  guidance.
- Added skill documentation tests and a FlowGuard self-model to prevent long
  blank field lists or evidence-dropping reductions from returning.

## v0.40.0 - 2026-06-01

FlowGuard maintenance scan router.

- Added `review_maintenance_scan()` with typed changed-artifact, evidence,
  signal, skipped-route, action, plan, and report rows.
- Added route-scoped `maintenance_scan_router` API discovery plus a
  `maintenance-scan-template` CLI scaffold.
- Added a FlowGuard self-model and tests that catch missing model/test
  alignment, missing StructureMesh routing, skipped-route drops, and broad
  claims without owner-route evidence.
- Updated docs and AGENTS guidance so non-trivial FlowGuard-managed work can
  route model/code/test drift, stale evidence, split pressure, and skipped
  routes to the owning maintenance skill without turning the scan into a heavy
  universal gate.

## v0.39.4 - 2026-06-01

FlowGuard guidance surface fold-down.

- Folded model-first satellite trigger detail into a compact handoff table.
- Replaced duplicate kernel reference protocol copies with satellite-owned
  handoff stubs.
- Moved long ModelMesh and Model-Test Alignment delegation prompts into
  lazy-loaded template files.
- Added skill documentation tests and guidance-compression model checks to keep
  duplicate reference bodies and eager long templates from returning.

## v0.39.3 - 2026-05-31

Codex skill diagram semantics sync.

- Added route-specific diagram intent guidance to installed FlowGuard skill surfaces.
- Clarified diagram edge meanings for development process, UI flow, model-test alignment, code-structure recommendation, and model mesh routes.
- Kept package runtime behavior unchanged.

## v0.39.2 - 2026-05-31

- Added `TestResultReuseTicket` so previous test results can be reused only
  with current command, source, tested artifact, dependency, environment,
  result fingerprint, and coverage-scope proof.
- Extended Model-Test Alignment and TestMesh to reject reused test evidence
  unless it has both a current reuse ticket and current proof artifact.
- Updated public templates, docs, OpenSpec artifacts, and FlowGuard skill
  guidance for model/test result reuse and background evidence boundaries.

## v0.39.1 - 2026-05-30

- Refreshed FlowGuard source-only release metadata after confirming the
  publication target.
- Updated package, README, and project adoption version surfaces to `0.39.1`.
- No runtime behavior, helper API, schema, or model semantics changed from
  `v0.39.0`.

## v0.39.0 - 2026-05-30

- Added Plan Detailing Compiler so rough ideas, short plans, and AI-generated
  outlines can be reviewed as typed `PlanDetail` rows before downstream
  FlowGuard routes run.
- Added projection helpers from PlanDetail to PlanIntake, Workflow Step
  Contracts, DevelopmentProcessFlow, and AgentWorkflowRehearsal.
- Added `python -m flowguard plan-detailing-template`, executable examples,
  public docs, API exports, and the `flowguard-plan-detailing-compiler`
  satellite skill.

## v0.38.0 - 2026-05-29

- Removed compatibility-only public aliases that no current FlowGuard route
  should teach agents to use: `FunctionResult.state` and the old Plan Intake
  alias exports `PlanIntakeSurface`, `PlanIntakeCompletenessFinding`,
  `FalseNegativeBackpropagationCase`, `FlowGuardClaimFinding`, and
  `review_plan_mutation_results`.
- Added a legacy compatibility cleanup FlowGuard self-model that rejects done
  claims when agents delete safety classifiers or skip installed Codex skill
  content parity.
- Updated API/check-plan docs to describe core API semantic stability and
  route-first usage without preserving obsolete compatibility-only wording.
- Added tests that keep the removed aliases out of the public API while
  preserving `SimilarityHandoff`, route-scoped discovery, and
  compatibility-surface safety classifiers.

## v0.37.0 - 2026-05-29

- Streamlined the AI-facing model-similarity surface: ordinary A/B/C
  maintenance reviews can now use `model_signature_minimal()`,
  `model_signature_maintenance()`, and
  `model_similarity_plan_for_changed_member()` before opening the full schema.
- Added `SimilarityHandoff` and `ModelSimilarityReport.to_handoff()` so
  downstream routes consume one typed handoff instead of repeated scalar
  relation/group/test/code obligation fields.
- Breaking cleanup: removed the old repeated similarity id fields from Existing
  Model Preflight, Code Structure Recommendation, Model-Test Alignment, and
  Architecture Reduction in favor of `similarity_handoff`.
- Updated route-first API docs and model-similarity templates so
  `MODELING_HELPER_API` is treated as the full index, not the first-read AI
  workflow.

## v0.36.0 - 2026-05-29

- Split public template bodies into route-scoped internal modules while
  preserving the `flowguard.templates` facade and all template CLI commands.
- Added route-scoped API registry groups so callers can discover helper families
  without scanning only the flat `MODELING_HELPER_API` list.
- Added lightweight evidence gate/detail structures for gradual contraction of
  overloaded risk and development-process evidence fields while preserving
  skipped, stale, not-run, and progress-only visibility.
- Expanded Model Similarity Consolidation into a maintenance-oriented review:
  signatures can carry code/test paths, public behaviors, shared-kernel ids,
  adapters, maintenance tags, and changed refs; reports now derive maintenance
  groups, changed-sibling impacts, shared/variant test obligations, and code
  obligations without creating a separate audit route.
- Refactored public template/API tests toward table-driven coverage and added a
  FlowGuard structure-surface simplification model for template/API/evidence
  contraction hazards.

## v0.35.0 - 2026-05-29

- Compressed FlowGuard AI-facing guidance so the kernel, satellite skills, and
  reusable AGENTS snippet now present a shorter first-read route: task triage,
  hard gates, the thin default model/check loop, compact route selection, and
  reference handoffs.
- Converted directly invokable FlowGuard satellite `SKILL.md` files into
  concise route shells while preserving standalone package verification,
  AGENTS/version adoption checks, evidence honesty, Mermaid snapshot guidance,
  and non-goals.
- Added guidance-compression FlowGuard checks that reject prompt-only
  completion claims until prompt budgets, validation, editable install,
  installed skills, shadow workspace, and local git evidence are aligned.
- Added prompt-budget tests for the kernel, satellite skills, and AGENTS
  snippet to prevent the hot path from regrowing into long protocol text.

## v0.34.0 - 2026-05-29

- Added Model Similarity Consolidation so structured model signatures can be
  compared before agents create parallel model boundaries or shared code. The
  new route classifies same-workflow, family-variant, symmetric-flow,
  shared-kernel, duplicate-boundary, overlapping-ownership, parent/child,
  sibling-overlap, adapter-only, evidence-duplicate, false-friend, unrelated,
  and manual-review relations.
- Added `ModelSignature`, `ModelSimilarityEvidence`,
  `ModelSimilarityRelation`, `ModelSimilarityPlan`,
  `ModelSimilarityReport`, and `review_model_similarity_consolidation()` with
  evidence-gated recommendations and downstream handoffs to Existing Model
  Preflight, ModelMesh, Architecture Reduction, Code Structure Recommendation,
  StructureMesh, Model-Test Alignment, or manual review.
- Integrated model-similarity evidence into Existing Model Preflight,
  Architecture Reduction, Code Structure Recommendation, and Model-Test
  Alignment, plus CLI/template support through
  `python -m flowguard model-similarity-template`.
- Added Runtime Path Evidence so real code and tests can emit ordered runtime
  node observations that name their matching FlowGuard model ids, node ids,
  child model ids, proof artifacts, inputs, outputs, state, and behavior
  boundaries.
- Added `RuntimeNodeContract`, `RuntimePathObservation`,
  `RuntimePathAlignmentPlan`, `RuntimePathAlignmentReport`,
  `RuntimePathRecorder`, and `review_runtime_path_alignment()` with checks for
  missing, extra, stale, non-passing, out-of-order, model-binding, proof
  artifact, and boundary gaps.
- Integrated runtime path evidence into Model-Test Alignment, layered boundary
  proof, hierarchical ModelMesh child reattachment, Runtime Gateway Adoption,
  Closure Contract, workflow step contracts, CLI templates, docs, and Codex
  skill guidance so agents can compare code execution traces with parent and
  child FlowGuard model structure.
- Added Architecture Reduction compatibility-surface classification for old
  aliases, public facades, boundary adapters, archive-only surfaces, negative
  legacy tests, prune candidates, and evidence-needed compatibility surfaces
  before contraction is reported as ready.
- Archived the compatibility-surface and runtime-path OpenSpec changes into the
  main specs. Schema remains `1.0`; runtime dependencies remain Python
  standard library only.

## v0.33.0 - 2026-05-28

- Added AgentWorkflowRehearsal so AI agents can take a fresh current-machine
  skill inventory before non-trivial multi-skill work, then rehearse selected
  skills, skipped candidate skills, ordering, continue/rework gates,
  validation gaps, side effects, and final evidence claims before execution.
- Added `SkillInventorySnapshot`, `SkillCapability`, `AgentWorkflowPlan`,
  `AgentWorkflowStep`, `SkippedSkill`, `AgentWorkflowRehearsalReport`, and
  `review_agent_workflow_rehearsal()` with pass, needs-revision, scoped, and
  blocked outcomes.
- Added the `flowguard-agent-workflow-rehearsal` Codex satellite skill as a
  peer route beside the existing FlowGuard satellites, plus executable example
  scenarios for stale snapshots, skipped required skills, wrong order, weak
  validation, missing rework gates, overbroad claims, and trivial over-trigger.
- Archived the project-adoption and agent-workflow OpenSpec changes into the
  main specs. Schema remains `1.0`; runtime dependencies remain Python
  standard library only.

## v0.32.0 - 2026-05-28

- Added project adoption/version gate helpers so target repositories can carry
  a managed FlowGuard `AGENTS.md` block, `.flowguard/project.toml`, and
  adoption logs that name the FlowGuard GitHub repository and current
  package/schema versions.
- Added `project-audit`, `project-adopt`, `project-upgrade`, and
  `project-adoption-template` CLI/template entry points.
- Updated kernel and satellite Skill guidance so real target-project FlowGuard
  use checks or records the project AGENTS/version adoption state instead of
  relying on unstated machine-local knowledge.
- Updated project integration docs, README, API docs, OpenSpec artifacts, and
  focused tests. Schema remains `1.0`; runtime dependencies remain Python
  standard library only.

## v0.31.0 - 2026-05-28

- Added obligation-family parity helpers so related obligations must carry
  member-by-member mechanism evidence before a family-level confidence claim.
- Added `ObligationFamily`, `ObligationFamilyMember`,
  `ObligationFamilyEvidence`, `FamilyBadCaseSeed`,
  `derive_same_class_bad_cases()`, and
  `review_obligation_family_parity()` with provenance-aware coverage matrices.
- Added `AnalogousDefectCandidate`,
  `review_analogous_defect_scan()`, scan-radius constants, and disposition
  states so post-miss reviews ask where the same failure shape may recur before
  broad closure.
- Integrated family parity into Model-Test Alignment and the Risk Evidence
  Ledger, and added analogous-scan gates to the Risk Evidence Ledger, so wrong
  provenance, missing sibling coverage, stale/non-passing family evidence,
  open analogous candidates, and scoped gates cannot be silently promoted to
  full confidence.
- Updated OpenSpec, README, docs, skill guidance, and focused tests for the
  new generic FlowGuard gate. Schema remains `1.0`; runtime dependencies
  remain Python standard library only.

## v0.30.0 - 2026-05-28

- Added executable Closure Contract review helpers so broad done, release,
  publish, and production-confidence claims can be classified as full, scoped,
  or blocked from current route evidence.
- Added `FlowGuardClosureContractPlan`, `ClosureEvidenceReport`,
  `RuntimeTraceMapping`, `ArtifactInvalidation`, `ModelQualitySignal`,
  `SameClassMissClosure`, `RuntimeGatewayInventoryClosure`, and
  `review_flowguard_closure_contract()`.
- Added the public `closure-contract-template` CLI/template scaffold plus
  README, API, closure-contract docs, and archived OpenSpec coverage for the
  final claim boundary.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.29.0 - 2026-05-28

- Added Runtime Gateway Adoption helpers so projects can distinguish
  design-only, test-aligned, and runtime-gateway FlowGuard adoption.
- Added `RuntimeStateSurface`, `RuntimeGatewayContract`,
  `RuntimeWriteObservation`, `RuntimeGatewayAdoptionPlan`,
  `RuntimeGatewayAdoptionReport`, and `review_runtime_gateway_adoption()` to
  block runtime protection claims when critical state writes can still bypass
  declared gateways.
- Updated OpenSpec, README, API docs, Model-Test Alignment guidance, and the
  closure contract so code-boundary evidence does not get overclaimed as full
  runtime state-write protection.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.28.1 - 2026-05-27

- Added lifecycle disposition support to Architecture Reduction candidates so
  completed or historical reductions remain visible as evidence without being
  re-reported as active ready work.
- Refreshed the structure simplification and public facade maintenance boundary
  so completed CLI/template and export-surface reductions close cleanly while
  shadow-only `.flowguard` duplicate cleanup stays a local sync concern.
- Updated OpenSpec, API-surface docs, agent guidance, and focused tests for the
  completed-candidate queue semantics.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.28.0 - 2026-05-27

- Added workflow step contracts so staged process plans can declare required,
  produced, and invalidated receipts and map them into DevelopmentProcessFlow
  validation gates.
- Connected workflow step contracts to claim readiness so done/release
  confidence can reject missing or stale step receipts instead of relying on
  prose-only process order.
- Updated public docs, examples, OpenSpec artifacts, and tests for the new
  workflow-step contract helper path.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.27.0 - 2026-05-27

- Added the FlowGuard model maturation loop with `ModelMaturationSignal`,
  `ModelMaturationPlan`, `ModelMaturationReport`, and
  `review_model_maturation_loop()` so post-code, post-miss, model-test, mesh,
  code-boundary, and freshness signals become explicit model-upgrade or
  scoped-claim decisions.
- Updated README, API docs, modeling protocol, closure contract, Risk Evidence
  Ledger guidance, DevelopmentProcessFlow, Model-Test Alignment, ModelMesh, and
  installed skill-source guidance so later evidence can force model refinement
  before broad confidence is claimed.
- Added focused unit tests for current, upgrade-required, scoped, blocked,
  mesh-driven, and caller-specified model maturation decisions.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.26.0 - 2026-05-27

- Defined the FlowGuard closure contract as intrinsic to complete FlowGuard
  use: plan/risk intake, model ownership, same-class model-miss evidence,
  model-test/code alignment, mesh or boundary proof when required, evidence
  freshness, Risk Evidence Ledger, and typed claim-chain support must be
  current before full done/release/publish/production-confidence claims.
- Updated README, AGENTS snippet, model-first skill guidance, modeling
  protocol, OpenSpec artifacts, and local self-review docs so partial model or
  test evidence is reported as partial/scoped FlowGuard evidence rather than
  complete FlowGuard use.
- Added a local executable closure-contract model and focused skill-doc tests
  that reject optional-mode framing and block completion without closure gates.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.25.1 - 2026-05-27

- Added `ProofArtifactRef` and legacy path disposition helpers so strict
  FlowGuard confidence checks can reject declaration-only `passed/current`
  evidence rows.
- Updated layered boundary proof, Risk Evidence Ledger, recurring model-miss
  defect-family gates, Model-Test Alignment, and DevelopmentProcessFlow with
  `require_proof_artifacts` gates that require result paths, fingerprints,
  current route evidence, and matching obligation coverage.
- Updated docs, skills, and templates so full confidence routes consume
  proof-artifact-bound evidence and explicit old-path disposition before
  closure.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.25.0 - 2026-05-27

- Added adversarial scenario synthesis on the existing Scenario Sandbox and
  model-first runner path so Explorer counterexamples, dead branches, exception
  branches, repeated state visits, and risk semantics can become candidate
  challenge routes without creating a parallel testing workflow.
- Updated retry, deduplication, cache, and side-effect packs to reuse the
  bounded input-shape fallback builder while preserving generated scenarios as
  `needs_human_review` candidate evidence until a domain oracle is supplied.
- Updated Scenario Sandbox, helper docs, README, OpenSpec artifacts, and focused
  tests for model-derived challenge-route evidence.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.24.0 - 2026-05-27

- Added model-impact freshness helper APIs so FlowGuard framework upgrades
  classify existing `.flowguard` models before broad freshness claims.
- Added `ModelFreshnessRecord`, `UpgradeImpact`, `ModelImpactAssessment`,
  `ModelReuseTicket`, `ModelRerunEvidence`, `ModelImpactFreshnessPlan`,
  `ModelImpactFreshnessReport`, and `review_model_impact_freshness()`.
- Added an executable `.flowguard/model_impact_freshness_gate` model that
  rejects missing classification, blind reuse of old evidence, and affected
  models accepted without current rerun evidence.
- Updated framework-upgrade, DevelopmentProcessFlow, modeling protocol, helper
  layer, README, API surface docs, OpenSpec artifacts, and focused tests.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.23.1 - 2026-05-27

- Added plan-intake and typed claim-chain helper APIs so broad FlowGuard
  confidence cannot be promoted from under-declared plan inputs, lossy evidence
  adapter mappings, unbackpropagated false negatives, or known-bad mutations
  that still pass.
- Added `PlanIntakeRiskSurface`, `EvidenceAdapterMapping`,
  `FalseNegativeCase`, `PlanMutationCase`, `FlowGuardClaimDependency`, their
  review plans/reports, and the corresponding public review helpers.
- Updated public docs, model-first skill guidance, API surface exports, and
  focused tests for the new plan/adapter/miss/mutation/claim boundary.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.23.0 - 2026-05-27

- Added automatic model/test split diagnostics with `AutoSplitCandidate`,
  `AutoSplitPolicy`, `AutoSplitPlan`, `AutoSplitReport`, and
  `review_auto_mesh_splits()` so oversized, incomplete, slow, broad,
  progress-only, or release-only direct evidence routes to ModelMesh or
  TestMesh before broad parent confidence.
- Connected automatic split evidence to DevelopmentProcessFlow so done,
  release, archive, and publish claims stay blocked or scoped until current
  ModelMesh/TestMesh split gates exist.
- Added model/test split gate fields to Risk Evidence Ledger rows so final
  confidence can consume or reject required split evidence at the FlowGuard
  layer.
- Updated public templates, README, API docs, ModelMesh/TestMesh docs,
  DevelopmentProcessFlow guidance, installed skill protocols, and OpenSpec
  artifacts so automatic split is an existing-route evidence gate rather than
  a new first-class skill.
- OpenSpec validation, focused auto-split route tests, ModelMesh/TestMesh
  tests, public template tests, skill-doc tests, model examples, and full
  unittest discovery passed locally.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.22.2 - 2026-05-27

- Added model-miss closure roles to Model-Test Alignment so repaired misses can
  require both observed-regression evidence and same-class generalized test
  evidence before closure.
- Added recurring defect-family gate helpers so repeated or high-risk
  same-class model misses must name a promoted family, model obligation,
  authority boundary, observed failure, generalized case, historical holdout,
  and current external proof before full closure.
- Connected required defect-family gate status to the Risk Evidence Ledger so
  final confidence is blocked, scoped, or full at the FlowGuard layer instead
  of depending on a downstream product reminder.
- Blocked observed-bug-only, wrong-target, internal-path-only, and overclaimed
  evidence from satisfying same-class model-miss closure.
- Updated model-miss examples, public templates, FlowGuard skill protocols,
  README, API notes, check-plan guidance, and TestMesh handoff rules so tests
  must generalize with the upgraded model.
- OpenSpec validation, FlowGuard model-miss example checks, focused route tests,
  full pytest, and unittest discovery passed locally.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.22.1 - 2026-05-22

- Clarified the public README positioning: FlowGuard is a universal AI-agent
  skill layer and lightweight Python toolkit, while Codex support is an
  integration path rather than the boundary of the project.
- Updated the English and Chinese README intro so the first screen presents
  FlowGuard as a general AI-agent skill.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.22.0 - 2026-05-22

- Added explicit model-test evidence roles for primary evidence, primary
  `edge_path` evidence, leaf matrix-cell evidence, supporting contract
  evidence, and integration smoke evidence.
- Model-Test Alignment now treats multiple current primary `edge_path` proofs
  for the same obligation as a `child_model_split_required` blocker instead of
  allowing a label-only downgrade.
- Strengthened leaf boundary matrices with optional input/state axes,
  Cartesian completeness checks, unexpected-cell checks, missing observed
  behavior checks, and external-contract assertion-scope checks.
- Extended TestMesh so parent gates can require current passing evidence for
  exact leaf matrix-cell ids.
- Extended Existing Model Preflight so full parent/child preflight records
  layered proof evidence, parent coverage, child disjointness, child
  reattachment, and leaf boundary-matrix status before claiming the existing
  boundary is understood.
- Updated FlowGuard skills, docs, templates, and focused tests for the stronger
  leaf-boundary evidence path.
- Added a thin default AI entry path across the FlowGuard kernel, AGENTS
  snippet, README, API surface docs, and product architecture docs:
  model the risky boundary as `Input x State -> Set(Output x State)`, add one
  invariant or scenario, run checks, inspect counterexamples, and escalate only
  when a named risk requires it.
- Reframed advanced satellites, helper APIs, meshes, ledgers, and framework
  suites as escalation paths rather than default reading for every FlowGuard
  task.
- Updated the skill-kernel FlowGuard model and skill-doc tests to catch a
  buried default path, advanced-route over-triggering, public/internal surface
  mixing, and stale satellite-count topology.
- Corrected the local satellite topology rollout model from the obsolete
  seven-satellite wording to the current ten-satellite topology.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.21.0 - 2026-05-22

- Added layered boundary proof helpers:
  `ParentCoverageItem`, `ChildProofContract`, `ChildReattachmentProof`,
  `LeafBoundaryMatrix`, `LeafBoundaryMatrixCell`,
  `LayeredBoundaryProofPlan`, and `review_layered_boundary_proof(...)`.
- Added a four-table parent confidence gate for parent coverage, child
  disjointness, child reattachment, and leaf
  `Input x State -> Set(Output x State)` boundary-matrix evidence.
- Added `python -m flowguard layered-boundary-proof-template`, public docs, and
  focused tests for green proof, coverage gaps, illegal overlap, stale
  reattachment, missing leaf cells, output overflow, progress-only evidence,
  and too-large leaf split-required cases.
- Updated the FlowGuard kernel, ModelMesh, Model-Test Alignment, TestMesh,
  Existing Model Preflight, DevelopmentProcessFlow, Code Structure
  Recommendation, StructureMesh, Architecture Reduction, and Model-Miss Review
  guidance so parent/child model confidence now has an explicit leaf-boundary
  proof chain.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.20.0 - 2026-05-21

- Added code-boundary conformance helpers: `CodeBoundaryContract`,
  `CodeBoundaryObservation`, `CodeBoundaryConformanceReport`, and
  `review_code_boundary_conformance(...)`.
- Extended Model-Test Alignment so a plan can include runtime boundary
  observations and block green alignment when real code accepts forbidden
  inputs or emits undeclared outputs, error paths, state writes, or side
  effects.
- Updated the model-test-alignment template, public docs, AGENTS snippet, and
  FlowGuard satellite skills so finite model-backed code boundaries require
  current boundary evidence before code conformance is claimed.
- Added an executable FlowGuard rollout model and focused tests for accepted
  inputs, rejected input gates, extra outputs, extra side effects, stale or
  internal-path-only observations, and alignment integration.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.19.1 - 2026-05-21

- Added Risk Evidence Ledger public APIs: `RiskEvidenceRow`,
  `RiskEvidenceProof`, `RiskEvidenceLedgerPlan`,
  `RiskEvidenceLedgerReport`, and `review_risk_evidence_ledger(...)`.
- Added `risk-evidence-ledger-template`, public docs, and an executable rollout
  model that catches internal-path-only and progress-only final confidence
  claims.
- Updated FlowGuard kernel and satellite skill guidance so final done, release,
  publish, and full-confidence claims must connect user risks to model
  obligations, optional public code contracts, and current proof evidence.
- Extended adoption logging with `risk_evidence_summary` so scoped or blocked
  confidence boundaries are recorded alongside commands, skipped steps, and
  findings.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.19.0 - 2026-05-21

- Added Architecture Reduction as a FlowGuard route for using existing models to
  find behavior-preserving code contraction opportunities before implementation.
- Added public helper APIs `ObservableArchitectureContract`,
  `ArchitectureReductionCandidate`, `ArchitectureReductionPlan`, and
  `review_architecture_reduction(...)`.
- Added candidate types, proof statuses, target actions, public-entrypoint
  StructureMesh gates, and target-structure handoff checks so risky shrinkage
  stays visible instead of becoming a silent rewrite.
- Added the `flowguard-architecture-reduction` Codex skill and updated
  companion FlowGuard skills so development, existing-model preflight,
  structure, mesh, model-test, and UI routes know when to invoke it.
- Added OpenSpec artifacts, local FlowGuard route-safety model checks, API
  docs, README coverage, and focused regression tests for the new route.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.18.6 - 2026-05-20

- Added validation-failure triage to DevelopmentProcessFlow so failed, stale,
  oversized, progress-only, or parent/child-sensitive validation is classified
  before agents keep patching or claim done.
- Added handoff guidance from DevelopmentProcessFlow to ModelMesh, TestMesh,
  and Model-Test Alignment for model-too-thick, test-too-thick, model-test
  mismatch, stale-evidence, and parent/child reattachment cases.
- Added Existing Model Preflight as a FlowGuard companion route for grounding
  discussion, proposals, bug fixes, feature work, refactors, prompts, skills,
  UI, test, and process changes in current FlowGuard model ownership before a
  new boundary is proposed.
- Added public helper APIs `ExistingModelPreflight`, `ModelContextHit`,
  `ExistingOwnershipSnapshot`, `DuplicateBoundaryRisk`, and
  `review_existing_model_preflight(...)`.
- Added `python -m flowguard existing-model-preflight-template`, a Codex skill,
  OpenSpec artifacts, local FlowGuard model checks, README/API docs, and route
  trigger coverage for the new preflight path.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.18.5 - 2026-05-20

- Refined FlowGuard diagram guidance so agents choose route-specific diagram
  semantics before drawing: behavior/state, development process, UI state,
  model-test coverage, code structure, or mesh.
- Clarified that FlowGuard diagrams are standalone FlowGuard guidance and do
  not require LogicGuard or a shared cross-family protocol.
- Kept diagrams explanatory only; executable checks, evidence freshness, and
  route-specific validation remain the confidence source.

## v0.18.4 - 2026-05-20

- Strengthened user-facing FlowGuard model visibility: non-trivial FlowGuard
  work now defaults to a Mermaid model snapshot during the work once the route
  or model shape is stable enough to explain.
- Extended route-specific diagram guidance across all installed FlowGuard
  satellite skills, while preserving concise output for tiny, obvious,
  direct-command, formatting-only, or user-suppressed tasks.
- Standardized global FlowGuard routing so clear staged-development, UI,
  structure, test, mesh, alignment, and model-miss work can select direct
  satellite skills instead of treating the model-first kernel as a universal
  first stop.
- Added OpenSpec artifacts and a local FlowGuard prompt-behavior model for the
  visibility rollout; diagrams remain explanation aids and do not count as
  validation evidence.
- Schema remains `1.0`; runtime dependencies and public Python APIs are
  unchanged.

## v0.18.3 - 2026-05-19

- Added lightweight user-facing Mermaid diagram guidance to the FlowGuard skill
  kernel so non-trivial model value can be explained when prose alone would hide
  the states, branches, gates, evidence, or claim boundary.
- Added route-specific optional diagram guidance for UI Flow Structure,
  ModelMesh, and DevelopmentProcessFlow while keeping diagrams as explanation
  aids, not validation evidence.
- Added OpenSpec artifacts and used a local FlowGuard self-model for the prompt
  behavior so the rollout rejects overbroad mandatory diagrams, shallow diagram
  guidance, and missing selected-route coverage.
- Schema remains `1.0`; runtime dependencies and public Python APIs are
  unchanged.

## v0.18.2 - 2026-05-19

- Added UI implementation validation for implemented/runnable UI completion
  claims, aligning user-visible feature contracts, reviewed UI journey
  coverage, and browser, desktop, or manual click-through evidence.
- Added public helper APIs `UIFeatureContract`, `UIImplementationValidation`,
  `UIImplementationJourneyRun`, `UIImplementationStepEvidence`,
  `UIImplementationBlindspot`, `UIImplementationValidationReport`, and
  `review_ui_implementation_validation(...)`.
- Updated the UI Flow Structure template so generated scaffolds now demonstrate
  feature contracts, implementation journey runs, model revision/freshness, pure
  UI actions, residual implementation blindspots, and known-bad missing
  implementation evidence.
- Updated the UI Flow Structure skill, Skill Kernel route guidance, AGENTS
  snippet, API docs, UI docs, README, OpenSpec artifacts, and focused tests so
  "model-complete UI" is not confused with "running UI clicked through."
- Broadened DevelopmentProcessFlow routing guidance so staged implementation,
  validation freshness, archive readiness, and release confidence checks are
  selected earlier for non-trivial development work.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.18.1 - 2026-05-19

- Added ModelMesh mesh-closure meta-models so parent/child model handoffs can be
  checked as executable FlowGuard-style obligations before whole-flow parent
  confidence is claimed.
- Added public helper APIs `MeshClosureModel`, `MeshClosureTransition`,
  `MeshClosureJoin`, `MeshClosureTerminal`, `MeshClosureReport`,
  `MeshClosureFinding`, and `review_mesh_closure_model(...)`.
- Updated `review_hierarchical_mesh(...)` so a declared closure model must pass
  before `mesh_green_can_continue`; closure blockers include missing root
  entries, unknown output references, unconsumed child outputs, incomplete joins,
  terminal leaks, missing out-of-scope rationale, and loop-like handoffs without
  progress evidence.
- Updated OpenSpec artifacts, ModelMesh docs, API docs, README, hierarchical
  examples, skill guidance, and focused tests for the new whole-flow closure
  gate.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.18.0 - 2026-05-19

- Added app-level UI journey coverage for complete UI claims, including launch
  state, top-level entry points, feature journeys, success terminals,
  failure/recovery/cancel/exit handling, terminal action allowances, and
  residual blindspots.
- Added public helper APIs `UIJourneyCoverage`, `UIJourneyEntryPoint`,
  `UIFeatureJourney`, `UITerminalActionAllowance`, `UIResidualBlindspot`,
  `UIJourneyCoverageReport`, and `review_ui_journey_coverage(...)`.
- Updated the UI Flow Structure template so generated scaffolds now model
  launch, new-project, load-existing, failure, cancel, export, exit, terminal,
  and residual-blindspot coverage before structure and text hierarchy handoff.
- Updated the UI Flow Structure skill, Skill Kernel route guidance, AGENTS
  snippet, API docs, UI protocol docs, README, OpenSpec artifacts, and focused
  tests so "complete app UI" is not claimed from layout/text evidence alone.
- Added known-bad coverage cases for missing launch entries, unreachable path
  states, unknown path events, missing success terminals, unhandled failures,
  visible controls without modeled events, reachable events outside all
  journeys, terminal forward actions, misclassified terminal exports, and
  blindspots without validation boundaries.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.17.1 - 2026-05-19

- Added ModelMesh boundary-diff propagation so repaired child models can report
  `unaffected`, `reattach_only`, `parent_rerun_required`,
  `sibling_rerun_required`, or `split_review_required` before parent
  confidence is claimed.
- Added public helper API `ChildBoundaryChangeSummary` and
  `summarize_child_boundary_change(...)`, and extended `ChildModelEvidence`
  with function, invariant, risk-class, and validation-evidence ownership
  fields.
- Updated ModelMesh review to expose boundary change decisions, reject
  point-fix-only bug-instance targets, and mark affected parent or sibling
  evidence stale when a child boundary changes.
- Hardened the public `model-miss-template` so generated review models now
  distinguish the observed issue, a same-class generalized bad case, and the
  known bug's holdout validation role before a repair can be finalized.
- Added generated negative scenarios that reject point-fix-only validation and
  validation that forgets to record the known bug as holdout evidence.
- Updated focused ModelMesh, public-template, Skill-doc, and OpenSpec artifacts
  for the boundary propagation and template hardening release.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.17.0 - 2026-05-18

- Added the ModelMesh child reattachment gate for local child model repairs:
  parent mesh confidence now requires current child evidence consumption plus
  stable input, output, state ownership, side-effect ownership, and outgoing
  contract handoffs.
- Added public helper API `ChildReattachmentContract` and extended
  `ChildModelEvidence` with evidence id, accepted inputs, emitted outputs, and
  incoming contract fields.
- Updated post-runtime model-miss review so a miss repaired inside a child model
  under a parent mesh remains open until the affected parent reattachment gate
  passes or records a blocker.
- Updated OpenSpec artifacts, Skill docs, public docs, examples, README, and
  focused tests to make "child-local green is not parent green" explicit.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.16.0 - 2026-05-18

- Added the UI Text Hierarchy Blueprint capability as the next public UI route.
  It reviews visible and assistive UI text by state, region, role, semantic
  key, owner, priority, duplication rationale, and warning/error escalation
  before copy, layout, or implementation flatten everything into equal prose.
- Added UI text hierarchy helper APIs:
  `UITypographyToken`, `UITextElement`, `UITextHierarchyBlueprint`,
  `UITextHierarchyReport`, and `review_ui_text_hierarchy(...)`.
- Updated `ui-flow-structure-template` so generated UI models now run the full
  three-stage review: interaction model, structure derivation, and text
  hierarchy blueprint, including known-bad text hierarchy hazards.
- Positioned UI Text Hierarchy Blueprint as a sibling to UI Flow Structure:
  UI Flow Structure derives controls, regions, overlays, and stable placement
  from modeled interaction behavior, while UI Text Hierarchy Blueprint derives
  which headings, labels, helper text, status text, empty/loading/success/
  failure text, CTA text, warnings, and errors should dominate or stay local in
  each state.
- Added OpenSpec artifacts under
  `openspec/changes/add-ui-text-hierarchy/` covering proposal, design, tasks,
  and requirements for text inventory, primary/secondary hierarchy, duplicate
  semantic text, state-specific copy, blocking warnings, assistive rationale,
  and handoff boundaries.
- Updated README and product architecture docs to foreground the new capability
  while preserving the `v0.15.0` UI Flow Structure material.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.15.0 - 2026-05-18

- Added the UI Flow Structure route for model-first interface design. The new
  helper first reviews a UI interaction model covering initial states, controls,
  events, state nodes, transitions, failures, recovery paths, terminal states,
  and control availability before deriving layout structure.
- Added UI flow structure helper APIs:
  `UIControl`, `UIDisplayElement`, `UIStateNode`, `UITransition`,
  `UIInteractionModel`, `UIRegionRecommendation`, `UIStructureDerivation`,
  `UIFlowStructureFinding`, `UIInteractionModelReport`,
  `UIStructureDerivationReport`, `review_ui_interaction_model(...)`, and
  `review_ui_structure_derivation(...)`.
- Added findings for missing initial states, missing availability matrices,
  unmodeled controls, failures without recovery, destructive primary/global
  controls, duplicate information in one state, same-level controls that
  trigger the same modeled function without a rationale, structure derivation
  before reviewed interaction evidence, missing parent surfaces, missing region
  maps, duplicate region ownership, duplicate information in one region,
  contextual controls placed globally, and overlays without origin or return
  paths.
- Added a `ui-flow-structure-template` CLI scaffold and public documentation
  for deriving first-level persistent areas, second-level contextual regions,
  third-level local actions, overlays, navigation ownership, and stable control
  placement from modeled UI behavior.
- Added the `flowguard-ui-flow-structure` Codex satellite skill and updated the
  Skill Kernel route map, AGENTS snippet, modeling protocol docs, API surface,
  product architecture docs, README, OpenSpec artifacts, and focused tests.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.14.0 - 2026-05-18

- Upgraded the Codex-facing skill architecture to one FlowGuard Skill Kernel
  plus seven directly invokable satellite skills:
  `flowguard-model-test-alignment`, `flowguard-development-process-flow`,
  `flowguard-model-miss-review`, `flowguard-code-structure-recommendation`,
  `flowguard-model-mesh`, `flowguard-test-mesh`, and
  `flowguard-structure-mesh`.
- Updated the global AGENTS snippet, README, product architecture docs, release
  checklist, OpenSpec artifacts, and skill-doc tests so the first-batch
  satellite topology is explicit while helper APIs and CLI templates remain
  package helpers rather than Codex skills.
- Added DevelopmentProcessFlow helper APIs:
  `ProcessArtifact`, `ActionEffect`, `ProcessAction`, `ProcessEvidence`,
  `FreshnessRule`, `ValidationRequirement`, `DevelopmentProcessPlan`,
  `RevalidationRecommendation`, `ProcessFlowFinding`,
  `DevelopmentProcessFlowReport`, `review_development_process_flow(...)`, and
  `derive_revalidation_plan(...)`.
- Added lifecycle findings for stale evidence after artifact changes, verifier
  changes after validation, model-test alignment evidence after model changes,
  requirement freshness propagation, unknown peer writes, ambiguous freshness
  policy, progress-only evidence, hidden skipped validation, failed/not-run
  evidence, missing V-style validation pairs, and release overclaims.
- Added a `development-process-flow-template` CLI scaffold and public docs for
  modeling development lifecycle ordering, artifact overwrite, evidence
  freshness, and minimum revalidation as a sibling route.
- Updated the model-first Skill Kernel, AGENTS snippet, API surface, README,
  OpenSpec artifacts, focused tests, and FlowGuard rollout model.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.13.0 - 2026-05-18

- Added conservative Python source-audit helpers for Model-Test Alignment:
  `PythonCodeContractEvidence`, `PythonTestAssertionEvidence`,
  `ContractSourceAuditFinding`, `ContractSourceAuditReport`,
  `audit_python_code_contracts(...)`, `audit_python_test_assertions(...)`, and
  `review_python_contract_source_audit(...)`.
- The source audit checks real Python functions for declared symbols, external
  inputs, return values for external outputs, state writes, declared side
  effects, and side-effect-looking extra calls before trusting `CodeContract`
  rows.
- The test audit checks real Python tests for target code-contract calls and
  assertions before trusting `TestEvidence` rows that claim external-contract
  proof.
- Added source-level findings such as `source_contract_missing_symbol`,
  `source_contract_missing_input`, `source_contract_missing_output`,
  `source_contract_missing_state_write`, `source_contract_extra_side_effect`,
  `source_test_missing_code_contract_call`,
  `source_test_missing_external_assertion`, and
  `source_test_internal_path_only`.
- Updated templates, docs, Skill guidance, OpenSpec artifacts, focused tests,
  and a FlowGuard rollout model for source-audit hazards.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.12.0 - 2026-05-18

- Upgraded Model-Test Alignment so `review_model_test_alignment(...)` can
  compare FlowGuard model obligations, optional code external contracts, and
  ordinary test evidence in one direct review.
- Added `CodeContract`, code-contract role constants, test assertion-scope
  constants, and optional external-contract fields on `ModelObligation`,
  `TestEvidence`, and `ModelTestAlignmentPlan`.
- Added findings for missing code contract owners, code contracts that miss
  model-declared external behavior, exact contracts that add extra external
  behavior, missing code-contract test evidence, tests that bind only model
  obligations when code contracts are in scope, internal-path-only tests,
  unknown code contract references, duplicate code contract owners, and
  model-code-test binding mismatches.
- Kept model-test-only reviews backward compatible: code contracts are optional
  unless a plan explicitly requires them.
- Updated the Model-Test Alignment template, CLI help, public documentation,
  README, API surface docs, Skill Kernel route guidance, AGENTS snippet,
  OpenSpec artifacts, focused tests, and a FlowGuard rollout model for the new
  contract-alignment hazards.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.11.0 - 2026-05-17

- Added Code Structure Recommendation helper APIs:
  `TargetModuleRecommendation`, `CodeStructureRecommendation`,
  `CodeStructureFinding`, `CodeStructureRecommendationReport`, and
  `review_code_structure_recommendation(...)`.
- Added review checks for missing source FlowGuard model evidence, missing
  parent boundary, missing target modules, missing FunctionBlock maps, missing
  validation plans, missing module rationales, unregistered owners, and
  duplicate FunctionBlock/state/side-effect/config ownership.
- Added a `code-structure-recommendation-template` CLI scaffold, public
  documentation, Skill Kernel route guidance, OpenSpec artifacts, focused
  tests, and a StructureMesh rollout model that catches target structures that
  are not model-derived or do not map model boundaries.
- Upgraded StructureMesh so existing large-script or large-module splits must
  include model-derived target code structure evidence inside the
  `StructureMeshPlan`; missing or mismatched target structure now blocks
  refactor confidence.
- Upgraded ModelMesh and TestMesh parent confidence checks to require
  FlowGuard-derived target split derivations before trusting child model or
  child suite/script ownership.
- Added `ModelTargetSplitDerivation` and `TestTargetSplitDerivation` helper
  records, protocol guidance, focused tests, and a FlowGuard rollout model for
  target split derivation coverage.
- Kept ordinary model-first work flexible: Code Structure Recommendation is a
  parallel route for direct architecture/file-split recommendations, not a hard
  gate for every FlowGuard model.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.10.0 - 2026-05-17

- Added standalone Model-Test Alignment helper APIs:
  `ModelObligation`, `TestEvidence`, `ModelTestAlignmentPlan`,
  `ModelTestAlignmentFinding`, `ModelTestAlignmentReport`, and
  `review_model_test_alignment(...)`.
- Added coverage checks for missing model obligations, missing required test
  kinds, orphan or unknown test evidence, duplicate evidence ownership,
  stale/non-passing evidence, overclaimed confidence, and duplicate model
  obligation IDs.
- Added a `model-test-alignment-template` CLI scaffold, public documentation,
  Skill Kernel route guidance, OpenSpec artifacts, focused tests, and a
  FlowGuard rollout model that catches missing route visibility and accidental
  dependency on TestMesh, StructureMesh, or ModelMesh.
- Kept Model-Test Alignment independent from mesh split helpers: it compares
  explicit model obligations with explicit test evidence and does not split
  tests, refactor code, or read mesh reports.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.9.0 - 2026-05-17

- Added StructureMesh helper APIs for parent/child structure refactor
  governance: `StructureMeshPlan`, `StructurePartitionItem`,
  `ModuleStructureEvidence`, `PublicEntrypointEvidence`,
  `StructureMeshFinding`, `StructureMeshReport`, and
  `review_structure_mesh(...)`.
- Added checks for missing or unregistered partition owners, duplicate
  partition owners, duplicate state/side-effect/config ownership, removed
  public entrypoints, missing facades, unsafe dependency cycles, config/default
  drift, missing or stale behavior parity, insufficient evidence tiers, and
  release-required parity gaps.
- Split routine and release refactor scopes so release-only structure evidence
  can remain visible as deferred obligations during routine work while still
  blocking release confidence when missing.
- Added a `structure-mesh-template` CLI scaffold, StructureMesh documentation,
  OpenSpec artifacts, Skill guidance, reusable AGENTS guidance, focused tests,
  and a FlowGuard rollout model for large script/module split governance.
- Modularized the `model-first-function-flow` Skill into a compact FlowGuard
  Skill Kernel plus dedicated sub-protocol references for core modeling,
  ModelMesh, TestMesh, StructureMesh, post-runtime model misses,
  conformance/adoption, long-check observability, and FlowGuard framework
  upgrades.
- Added a Skill Kernel rollout model that catches missing hard gates, route
  gaps, duplicate rule ownership, helper APIs mislabeled as sub-skills,
  standalone FlowGuard regressions, heavy-check over-triggering, and missing
  release/install sync routes.
- Clarified TestMesh as the test-side sibling of ModelMesh and StructureMesh:
  large test scripts, suites, or validation flows split into parent/child test
  hierarchy layers while parent gates consume child ownership and evidence
  contracts instead of expanded child internals.
- Added a soft oversize hint to the Skill Kernel so agents consider
  parent/child splits for large, slow, or hard-to-follow models, tests, scripts,
  modules, and commands without adding fixed thresholds or external planner
  dependencies.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.8.0 - 2026-05-17

- Added TestMesh helper APIs for layered validation governance:
  `TestMeshPlan`, `TestPartitionItem`, `TestSuiteEvidence`,
  `TestMeshFinding`, `TestMeshReport`, and `review_test_mesh(...)`.
- Added parent/child test partition checks for missing owners, unregistered
  owners, duplicate partition ownership, duplicate state-write ownership, and
  duplicate side-effect ownership.
- Added evidence checks for stale results, hidden skipped tests, failed suites,
  timeout suites, insufficient evidence tiers, and background progress without
  final exit/result artifacts.
- Split routine and release validation scopes so release-only suites can remain
  visible as deferred obligations during routine work while still blocking
  release confidence when missing.
- Added a `test-mesh-template` CLI scaffold, TestMesh documentation, OpenSpec
  artifacts, Skill guidance, reusable AGENTS guidance, focused tests, and a
  FlowGuard rollout model that catches flat slow gates, missing/unregistered
  owners, duplicate owners, stale/hidden/timeout evidence, background
  progress-only overclaims, missing release evidence, and direct-test-runner
  scope creep.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.7.3 - 2026-05-16

- Added hierarchical model-mesh helper APIs for parent partition maps, child
  model evidence summaries, mesh findings, and mesh decisions.
- Added `review_hierarchical_mesh(...)` to check parent coverage gaps, unsafe
  sibling overlap, duplicate state-write ownership, duplicate side-effect
  ownership, stale/skipped child evidence, large-model split triggers, and
  legacy compatibility boundaries.
- Added `classify_legacy_model(...)` so existing model scripts can be
  registered and wrapped before they are trusted as strong child evidence.
- Extended model-mesh guidance to trigger from both model count and single-model
  scale, including estimated/observed state counts above 10,000, incomplete
  budgeted model groups, and models with unrelated functional areas.
- Added a nested hierarchy example, OpenSpec artifacts, focused tests, and a
  FlowGuard rollout model that catches missing scale triggers, coverage gaps,
  hidden overlap, duplicate ownership, legacy direct trust, child-graph
  expansion, background-check overclaims, and release-sync omissions.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.7.2 - 2026-05-15

- Simplified post-runtime model-miss review in the `model-first-function-flow`
  Skill to five practical miss types: `boundary_missing`,
  `state_too_coarse`, `input_branch_missing`, `invariant_too_weak`, and
  `evidence_overclaimed`.
- Required in-scope model misses to represent the observed issue plus one
  same-class generalized bad case when practical, so repairs do not stop at the
  exact bug that was just found.
- Kept the model-miss workflow lightweight: ordinary model misses do not add a
  default hazard registry, upgrade reviewer, model mesh, full coverage matrix,
  or evidence-level field.
- Updated OpenSpec artifacts, the reusable AGENTS snippet, modeling protocol,
  focused docs tests, and a FlowGuard rollout model for the revised workflow.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.7.1 - 2026-05-15

- Added a pre-implementation model-hardening gate to the
  `model-first-function-flow` Skill for complex optimizations, repeated bug
  repairs, stateful refactors, and model-miss-sensitive work.
- Required agents to write a change inventory, risk catalog, and risk-to-model
  coverage matrix before complex FlowGuard-backed edits.
- Clarified that representative known-bad hazards must fail before a model is
  trusted for the target bug class; happy-path checks alone are not enough.
- Added tiered handling for expensive project-specific model groups without
  hard-coding local model names as universally heavy or skippable.
- Updated the reusable AGENTS snippet, OpenSpec artifacts, focused tests, and a
  FlowGuard rollout model that catches code-first, happy-path-only, hard-coded
  heavy-model, peer-change, touched-heavy-skip, and premature-release variants.
- Ignored `tmp/` so background check logs and template smoke outputs do not
  appear as release candidates.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.7.0 - 2026-05-14

- Added budgeted model-group execution for large reachable graph models via
  `BudgetedGraphConfig` and `run_budgeted_graph_checks()`.
- Added a SQLite ledger that records seen, pending, processed, labels, failure
  samples, and shard summaries so repeated runs continue from pending work
  instead of starting over.
- Added fingerprinted run directories so changed model inputs, budgets,
  invariants, required labels, or caller-provided fingerprint parts do not reuse
  stale model evidence.
- Added whole-group reporting that distinguishes `complete`, `incomplete`, and
  `failed`; `ok` is true only when no pending states, failures, or missing
  required labels remain.
- Added shard-local progress plus model-group processed/pending totals on
  `stderr`, while preserving existing `Explorer` progress behavior.
- Added OpenSpec artifacts, a FlowGuard rollout self-model, focused tests,
  documentation, and a FlowPilot-style example for budgeted graph checks.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.6.1 - 2026-05-14

- Added a standard background-log contract for long-running FlowGuard checks:
  `tmp/flowguard_background/` with stdout, stderr, combined output, exit-code,
  and metadata artifacts.
- Updated the `model-first-function-flow` Skill and reusable AGENTS snippet so
  agents must inspect actual log and exit artifacts before reporting long checks
  as complete.
- Clarified that direct `Explorer(...)` progress and legacy/custom runner final
  reports are different evidence types; final summaries are not live progress.
- Added OpenSpec change artifacts and doc tests that pin the log root, artifact
  names, completion evidence, and proof-reuse reporting expectations.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.6.0 - 2026-05-14

- Added an optional spec/SPAC-style skill-orchestrator collaboration model that
  keeps FlowGuard standalone while allowing upstream planning tools to hand off
  structured plans for risk review.
- Added `docs/skill_orchestrator_collaboration.md` with the three operating
  modes, the handoff contract, the upgrade sequence, known hazards, validation
  order, and non-goals.
- Updated the `model-first-function-flow` Skill, reusable AGENTS snippet, and
  project integration docs so upstream planner handoffs are optional context,
  not a FlowGuard dependency.
- Added tests that prove complete handoffs pass, missing upstream planners fall
  back to standalone FlowGuard, incomplete handoffs block collaboration only,
  and broken variants are caught for hard dependencies, hidden side effects,
  missing parallel ownership, skip-without-reason, ignored counterexamples,
  over-triggering trivial work, and completion without evidence.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.5 - 2026-05-13

- Added default ten-step progress output for `Explorer.explore()` so long
  serial model runs emit start and progress lines on `stderr` while preserving
  `stdout` for reports and JSON pipelines.
- Counted progress by top-level `initial_state x input_sequence` work units and
  kept the run serial and deterministic.
- Added `progress_steps=0` and `FLOWGUARD_PROGRESS=0` opt-outs for strict CI or
  callers that need silent runs.
- Added a FlowGuard rollout model plus focused tests for stderr routing,
  bounded output, small totals, opt-outs, runner inheritance, and report
  stability.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.4 - 2026-05-12

- Added Risk Purpose Headers to generated FlowGuard model templates so future
  agents can see the FlowGuard source repository, modeled workflow, guarded
  failure modes, use-before-editing guidance, and companion run command.
- Updated the `model-first-function-flow` Skill and reusable AGENTS snippet so
  AI-created or AI-updated FlowGuard model files carry the same lightweight
  header instead of only saying that they are FlowGuard artifacts.
- Used a local FlowGuard rollout model for this release that catches generic
  link-only headers, partial template coverage, missing Skill/AGENTS guidance,
  missing tests, manifest-style scope creep, and premature publication.
- Added focused tests for generated model template headers and Skill/AGENTS
  header guidance.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.3 - 2026-05-12

- Added a local model mesh protocol for projects with three or more FlowGuard
  models, including inventory fields, evidence tiers, required hazards, a prompt
  template, and a completion standard.
- Updated the `model-first-function-flow` Skill so multi-model FlowGuard
  projects must inventory and connect existing models before broad continue,
  release, completion, or production-confidence claims.
- Extended the FlowGuard Skill trigger self-review with a multi-model
  maintenance scenario and a broken variant that catches omitted model-mesh
  checks.
- Updated the reusable AGENTS snippet and modeling protocol docs with the
  model-of-models trigger.
- Schema remains `1.0`; runtime dependencies and CLI templates are unchanged.

## v0.5.2 - 2026-05-10

- Clarified the `model-first-function-flow` Skill around three broad FlowGuard
  scopes: Behavior Flow, Argument Flow, and Decision Flow.
- Added concise modeling hints for behavior state, reader/argument state, and
  decision/commitment state without adding new template families or changing
  the core API.
- Updated the README and reusable AGENTS snippet so users see that the existing
  model templates remain the execution scaffolds for all three flow types.
- Extended the Skill trigger self-review with structured argument and decision
  planning scenarios.
- Schema remains `1.0`; runtime dependencies and CLI templates are unchanged.

## v0.5.1 - 2026-05-09

- Refreshed the public project template so package-generated starter files
  match the richer model-first Skill template with validation, rejection,
  repeated-input handling, and traceability checks.
- Added public-safe Risk Intent + CheckPlan and post-runtime model-miss review
  template scaffolds, including CLI writers for `project-template`,
  `risk-intent-template`, and `model-miss-template`.
- Added template execution tests and privacy-marker checks to keep public
  scaffolds neutral and free of local project details.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.0 - 2026-05-08

- Added `FlowGuardFindingLedger`, `FlowGuardFindingLedgerEntry`, and
  `build_finding_ledger` to flatten summary findings and skipped/not-run gaps
  into one coverage-first repair ledger.
- `FlowGuardSummaryReport.finding_ledger` now exposes the ledger, and
  `to_dict()` includes it as machine-readable output for agents.
- Updated the helper-runner self-review with a broken variant that catches
  point-rule patches made before a full finding ledger is built.
- Updated the model-first Skill, AGENTS snippet, check-plan docs, framework
  upgrade guidance, modeling protocol, and README to route FlowGuard or
  LiveFlowGuard self-upgrades through coverage-first triage.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.4.2 - 2026-05-07

- Added Post-Runtime Model-Miss Review guidance to the model-first Skill:
  runtime, test, replay, or manual-validation failures after a FlowGuard pass
  must reopen the model-first loop instead of becoming direct patch-and-finish
  work.
- Clarified that agents should classify why the prior model missed the issue,
  represent in-scope misses as scenarios, invariants, replays, representative
  traces, or explicit out-of-scope boundaries, then rerun checks before
  validating the repair.
- Updated the reusable AGENTS snippet, modeling protocol, project integration
  notes, README, and Skill doc tests for the new completion gate.
- No core API, schema, runtime dependency, or CLI behavior changed.

## v0.4.1 - 2026-05-07

- Clarified that when no FlowGuard model exists yet, the AI agent should create
  one from the current plan or adapt the included model template instead of
  refusing the task.
- Reframed the model as a fit-for-risk, customer-purpose artifact rather than
  always a minimal script: it should capture the failure modes the customer
  wants to expose and grow as new risks appear.
- Updated the README, AGENTS snippet, modeling protocol, project integration
  notes, and Skill wording to make evolving model scripts part of the public
  onboarding path.
- No core API, schema, runtime dependency, or CLI behavior changed.

## v0.4.0 - 2026-05-02

- Added `RiskIntent` for explicit pre-modeling briefs that name failure modes,
  protected harms, model-critical state, adversarial inputs, hard invariants,
  and blindspots.
- Extended `RiskProfile` with an optional `risk_intent` field and audit
  suggestions for missing or thin Risk Intent Briefs.
- Updated the model-first Skill, modeling protocol, check plan docs, API
  surface docs, and README to make Risk Intent Briefs part of the public
  FlowGuard workflow.
- Fixed README version-section ordering so release notes read newest to oldest:
  `v0.4.0`, `v0.3.1`, `v0.3.0`, then `v0.2.0`.

## v0.3.1 - 2026-05-02

- Added opt-in Mermaid source exporters for representative traces, generic
  state graphs, and loop review graphs.
- Exposed `trace_to_mermaid_text`, `graph_to_mermaid_text`,
  `loop_report_to_mermaid_text`, and `mermaid_code_block` through the public
  FlowGuard reporting helper API.
- Updated the README with English and Chinese Mermaid examples showing how
  FlowGuard turns a risky request into a finite model, reachable traces,
  findings, and optional conformance replay.
- Added a runnable `examples/mermaid_export_example.py` script that prints a
  Markdown Mermaid code block.
- Documented that Mermaid output is copyable text source and remains off by
  default so routine reports stay concise.

## v0.3.0 - 2026-04-30

- Expanded the `model-first-function-flow` Skill from coding/repository-only
  framing to coding, repository, and process-design work.
- Added `process_preflight` mode for non-code or mixed workflows that need
  validation, adjustment, observation, or loss-prevention review before action.
- Clarified that booking, purchase, publication handoff, operational runbook,
  data migration, support escalation, and multi-agent coordination flows can be
  modeled when they have meaningful state, side effects, external dependencies,
  rollback concerns, or irreversible cost.
- Preserved the skip boundary for trivial reversible tasks and clarified that
  non-code process models are risk-discovery preflights, not proof of real-world
  prices, availability, policies, or vendor behavior.
- Updated the README, AGENTS snippet, Skill documentation, and Skill doc tests
  for the broader process-preflight scope.

## v0.2.1 - 2026-04-30

- Simplified the `model-first-function-flow` Skill adoption-note wording so
  agents leave a short plain-language record instead of treating adoption
  logging as a heavy field checklist.
- Clarified that the adoption CLI can help create the log entry, but it is not
  a substitute for a short human-readable note when the model found something
  important.
- Updated the reusable AGENTS snippet with the same lighter note guidance.
- Clarified that `SCHEMA_VERSION` / `python -m flowguard schema-version`
  reports the artifact schema version, not the GitHub/package release version.

## v0.2.0 - 2026-04-30

- Added optional standard property factories, model quality audit,
  `RiskProfile`, `FlowGuardCheckPlan`, and `run_model_first_checks()` to make
  model-first checks easier for AI coding agents without changing the core
  `Input x State -> Set(Output x State)` model.
- Added deterministic counterexample minimization, scenario matrix generation,
  unified summary reporting, and lightweight domain packs for deduplication,
  cache, retry, and side-effect risks.
- Added helper surfaces for adoption evidence review, state-write inventory,
  low-friction adoption logging, and optional maintenance workflow scaffolding.
- Expanded public examples, benchmark/evidence documentation, self-review
  models, and tests while keeping runtime dependencies at Python standard
  library only.
- Clarified that warnings, skipped checks, and `pass_with_gaps` are confidence
  boundaries, not hard failures and not production conformance claims.

## v0.1.3 - 2026-04-29

- Added model-fidelity calibration guidance to the `model-first-function-flow`
  Skill.
- Added a modeling protocol step that treats FlowGuard models as falsifiable
  simulators of real workflows, not ground truth.
- Clarified that conformance replay and replay adapters must not hide relevant
  production behavior.
- Updated the reusable AGENTS.md snippet to record model-fidelity gaps and
  calibration changes.
- Refreshed the README positioning around FlowGuard as an architecture
  simulator / finite-state workflow simulator, including the hero tagline and
  AI-agent install path.
