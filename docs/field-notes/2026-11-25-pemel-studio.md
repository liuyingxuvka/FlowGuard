# PEMEL Studio field notes, 2026-11-25: FlowGuard 5.1.0 in daily use

These notes cover one working round of PEMEL Studio on the v5.1.0 tag. The Studio is a Python/PySide6 desktop application, and it runs pytest with `-p flowguard.intent.plugin`. Everything happened in one working tree.

The lead installed v5.1.0 and ran `new-task` at `2256acb`. Seven agent steps followed:
- a calibration package and its review fix;
- a package that gave four Controller fields one owner, and its fix;
- a review of the legacy ledger entries, and its fix;
- the integration.

Nine full suites ran, from `2862` to `2888 passed`.

The 2026-11-24 note covered the 5.1 candidate on an isolated copy. Its points are not repeated here.

Every claim was checked against the v5.1.0 source (`bcc57bd0`). Read-only commands were run again on the Studio at `c86dbb1` (the brief, `show`, `show --last`, `check --static --all` and `ledger check`). "Probe" means FlowGuard's own extractors run on a few synthetic lines: `structure/extract.py:extract` and `map/discovery_syntax.py:_FileVisitor`.

## Where it helped

### 1. Choice records fit how this owner answers
- **What happened:** This owner usually answers by agreeing, in a few words, to options the agent offered. Four of the round's stored words are choice records: `req add REPLY --id R15 --offer FILE --picked TEXT`, then R16, R17 and R20 the same way. Their replies are 303, 54, 60 and 237 bytes. `show rules` cites five rules by them, for example `source: R16 picked "…" (holds: the agent's option, the owner's pick)`.
- **In the source:** `map/requests.py:store_choice` stores the offer apart, in `offers/<id>.md`, as the agent's words, and the reply as the owner's words. It refuses a `--picked` text that does not occur exactly once in the offer (`choice_picked_absent`, `choice_picked_ambiguous`). `intent/cli.py` prints the `(holds: …)` note.
- **Why it matters:** "I agree with both points" holds no rule on its own. Now a rule's source names the option the owner agreed to, and that option stays marked as the agent's text, never his.
- **Suggestion:** none. The 5.1 rules block (rule 7) already sends agents to this route.

### 2. The Controller's many-writer fields got owners
- **What happened:**
  - At the task start, `check --static --all` listed four fields with no writers agreement: `Controller.task_dialog` (7 files), `discarded_project`, `project` and `selection`. That made 34 `before:` lines, and they were the owners package's work list.
  - The package added `# flowguard: writers Controller.project Controller.__init__,Controller.set_current_project` (`src/pemel_studio/controller.py:164`) and a matching agreement for `selection` (`:167`). It routed `task_dialog` through `adopt_task_dialog` and removed the dead `discarded_project`.
  - After the agreement, `show Controller.project` named an outside writer that a grep over `src/` had missed: `packaging/app/diagnostic_runtime.py:183`, `controller = window.controller; controller.project = reopened`. It now calls `set_current_project`.
  - The round's 24 `impact:` lines let the integration step check the change function by function, for example: `impact: Controller.select's writes of Controller.selection moved to Controller.set_selection, which it calls (src/pemel_studio/controller.py:542); other callers of Controller.set_selection: Controller.activate_tab, Controller.set_selected, MainWindow.apply_settings`.
  - At the end, no line says `has no writers agreement`.
- **In the source:**
  - 5.1 types writes through names imported under `TYPE_CHECKING` (PEMELPM-317). That made the four fields visible.
  - Once an agreement exists, `intent/owners.py:owner_writes` reads `writes(by_name=True)` and holds every untyped write of the field's name. That is how the write through the untyped local `controller = window.controller` was caught.
- **Why it matters:** The writers job worked end to end: a finding, an agreement, an outside writer, a route.
- **Suggestion:** none here. The same matching by name causes item 6.

### 3. The 5.1 ledger forms cleared the legacy backlog and shaped a fix
- **What happened:**
  - `ledger check` went from `184 entries (52 legacy), 190 code handlers` to `181 entries (36 legacy, 36 of them reviewed), 186 code handlers; 0 red, 0 unverified`.
  - Twelve legacy `suppress(T)` entries took a reason and a rule under their old key. The two `before: ledger legacy: …` lines of `check --static --all` went away.
  - A new test's polling loop gave `red: ledger: New unregistered fallback: test_packaging.py:309 except psutil.NoSuchProcess can end without raising`. The test was rewritten with `os.waitid(..., WEXITED | WNOWAIT)` and needs no handler.
  - The reviewer first proposed catching `Exception` in `SerialTaskObserver._commit`, with a ledger entry. 5.1 does not allow that, so the fix raises one declared type from `SerialTaskRunner.finish_commit` instead.
- **In the source:** The module docstring of `intent/ledger.py` says `except Exception` "cannot be listed: they are red until the code changes", and that a legacy entry "can only shrink". `evaluate` adds "Only ledger init may record legacy entries", and `reviewed` needs at least eight words.
- **Why it matters:** The written rule let the error reach the caller instead of a second handler that ends quietly.
- **Suggestion:** none.

### 4. `show` and `known add` saved searches
- **What happened:**
  - `show NO_EFFECT_BOUND` printed `anchor NO_EFFECT_BOUND -> pemel_service.calibration.steps:ends_without_effect src/pemel_service/calibration/steps.py:163`, its rule (`tests/intent/calibration_parts.py:49; 6 literal rows`) and `undecided: rule NO_EFFECT_BOUND has no result for 7 classes`. That said where a new start value had to come from.
  - `show CalibrationPlan.stage_parameters` printed `reads CalibrationPlan.stage_parameters src/pemel_service/calibration/contracts.py:633 CalibrationPlan.identity (asdict)`. So removing a key changes a stored plan's identity, which would otherwise show only as a failed resume.
  - `show src/pemel_service/workspace/event_log.py:RotatingJsonLog.record` printed `candidate pemel_service.workspace.event_log:RotatingJsonLog.__init__ :?: same decision sites (2 of 10 the home's sites): L62 self.path.is_symlink()`. That was a third copy of a refusal the review had named twice. All three now share one helper, and the candidate line is gone.
  - `known add - --act ask --id aging-no-effect-start --site src/pemel_service/calibration/backend.py:SingleRecordBackend.fit_stage …` wrote an open question in one command, and `check --static --all` listed it at once.
- **In the source:** `structure/homes.py` gives the `same decision sites` reason. `structure/api.py:MapHandle.field_reads` counts `asdict(x)` as a read of every field.
- **Suggestion:** none.

### 5. The suite runs without the local shim
- **What happened:** The first full suite after the switch gave `2862 passed, 1 skipped, 2 unverified in 778.00s` with the block `FlowGuard 5.1 (since 2256acb): 0 red, 2 loosened, 4 not compared; 77.3 s`. Eight more full suites followed. None needed the small local pytest plugin that 5.0.1 required to keep the excluded Qt Linguist `.ts` files out of the change set. The repository's AGENTS.md note on that issue was removed in `1e680ef`.
- **Suggestion:** none. The 2026-11-24 note traced the fix.

## Where it fell short (by priority)

### 6. (High) A dict key is held to a class field's writers agreement
- **What happened:**
  - Once the agreements were in, every `check --static --all` printed `before: writers Controller.project at store.py:ProjectStore.export_saved already wrote Controller.project outside this agreement at task start; this change added the agreement -> leave it unless your task is about it`, and the same for `Controller.selection at jobs.py:decode_plan`.
  - The two lines are `manifest["project"] = without_saved_band(manifest["project"])[0]` (`src/pemel_service/project/store.py:1082`) and `raw["selection"] = CalibrationSelection(**selection)` (`src/pemel_service/calibration/jobs.py:162`). Both write a key of a local dict parsed from JSON.
  - `show Controller.project` prints `outside writers: src/pemel_service/project/store.py:1082 ProjectStore.export_saved (assign)`. It also prints `test fixture (not held): tests/service/simulation/test_storage_estimate_measured.py:305 … (assign, value 300)`, which is `free["project"] = 300`.
- **Cause:**
  1. `structure/extract.py:Reader.written` records `row['key'] = …` as a write of a field named after the key (`form: key`). With an untyped receiver, the field is `manifest.project`, unresolved.
  2. `structure/api.py:MapHandle.writes(by_name=True)` turns that into a row with `how='name'`, `model=None` and `reason='attribute assignment matched by field name only'`, and drops `form`.
  3. `_writes_target` matches such a row to any `X.project`.
  4. `intent/owners.py:_of_class` returns True for every row whose `how` is not `attribute`, so `owner_writes` holds the row.
  - Probe: `manifest = {}; manifest["dialog"] = 4` gives `W 15 app:start app:manifest.dialog unresolved key`.
- **Why it matters:**
  - The 5.1 CHANGELOG says an untyped attribute write is held by its field name on purpose. A Python dict key is not an attribute of any class instance.
  - Nobody can act on the two lines. The only ways to clear them are to loosen the agreement or to bend service code around the tool. So they will stay `before` in every later structure review (`check --static --all`).
  - Their step, "leave it unless your task is about it", is given in the very task that added the agreement.
  - The reason the row carries ("matched by field name only") is never printed.
- **Suggestion:**
  - Keep `form: key` through `MapHandle.writes`.
  - Do not hold a Python key write to an agreement whose field `_agreed_class` resolves to a Python class. Key writes still matter for row-shaped data such as SQL or Prisma.
  - Print "matched by its field name only" on every by-name line that remains.

### 7. (High) The many-writer list and `show` miss writes in closures and through local aliases
- **What happened:**
  - `show Controller.data_import_dialog` lists the writers `Controller.__init__` and `start_import (data_import.py:356)`, and the read `src/pemel_studio/workflows/data_import.py:125 start_import.finish_intake (attribute)`. It does not list the next line, `:126 controller.data_import_dialog = None`, in the same nested function.
  - At the task start, the 7-file list for `Controller.task_dialog` left out the closure writes at `data_import.py:187` and `:331`.
  - The list for `Controller.project` left out `c = self._controller; c.project = saved` (`history.py:184` at `941313b`). grep found them.
- **Cause:**
  - In `structure/extract.py`, `Reader.visit_FunctionDef` sets `self.typed` to the nested function's own annotated parameters. That drops the enclosing `controller: Controller`. `self.reading` keeps the enclosing scope's names.
  - `Reader.written` types a write's receiver only through `self.typed`. Reads use `Reader.receiver`, which also follows local aliases (`bind_reading`).
  - `MapHandle.writes()` leaves out an untyped write unless `by_name` is set, and `intent/health.py:_production_write` drops a row that has no model.
  - Probe, inside `def start(controller: Controller)`:
    - `def finish(): if controller.dialog is not None: controller.dialog = None` gives `R 9 app:start.finish app:Controller ['dialog']` but `W 10 app:start.finish app:controller.dialog unresolved`;
    - `c = controller` makes `c.dialog` a typed read, while `c.dialog = None` writes `c.dialog unresolved`.
- **Why it matters:**
  - The many-writer finding is the work list for a writers agreement, and `show Class.field` is the "check before you change" step. Both counted fewer writers than the code has.
  - Once an agreement exists, the same writes are held by name, as item 2 shows. The gap is in the list before the agreement and in what `show` says.
  - `show` and `impact` say `untyped reads not counted`, but nothing tells the agent that untyped writes are not counted either.
- **Suggestion:**
  - Type a write's receiver with the same `receiver()` that reads use, which follows enclosing scopes and local aliases.
  - Until then, count by-name writes of a field as "unclear" members of the many-writer finding, and print `untyped writes not counted` beside the note on reads.

### 8. (High) Following `known fixed?` reads as `loosened` all round, and a new open question reads as nothing
- **What happened:**
  - After the switch, the 5.1 block marked both writer entries of `known.toml` (act = "leave") as `known fixed?`, and its step said to remove them. The lead removed them in `1e680ef`.
  - From then on, every block to the end of the round printed `loosened: known.dirty-field-default removed from .flowguard/known.toml -> name it in your report; loosening an agreement is the owner's decision`, and the same line for `known.simulation-state-field-default`. "Every block" means 9 full suites, the verifier runs, each targeted run and `check --static --all`. Six agent notes explain the same two lines.
  - Meanwhile `known.aging-no-effect-start` (act = "ask", added in `699fd85`) shows in the brief and in `check --static --all`, but in no pytest block. The integration block was `0 red, 24 impact, 2 loosened, 54 not compared; 170.7 s`.
- **Cause:**
  - In `intent/signals.py`, `FIXED_STEPS['leave']` says: "if you meant to fix it, remove known.{id} and say so in your report".
  - `intent/sources.py:loosened(old, new)` makes every known entry removed since the baseline catalog a `loosened` line, whatever became of its finding. `catalog_loosened` compares with the task baseline, so the line repeats until the next `new-task`.
  - `signals.deliver` gives a `known` line only when the change touches the entry's sites. `fit_stage` is back at its baseline text.
  - `loosened` lists an added entry only when its act is not "ask".
- **Why it matters:**
  - Keeping open questions is one of FlowGuard's jobs. Here its own route ends in a line that calls the removal a loosening, which makes it the owner's decision, in every block.
  - Agents learn to skip `loosened`, the kind that most needs reading.
  - A question the round left for the owner shows in the brief and in `check --static --all`, but not in the pytest run the rules name as the check.
- **Suggestion:**
  - When a removed entry's finding is not found now, which is the `known fixed?` condition and holds whatever made the finding go, report the removal as resolved rather than loosened.
  - Give an `ask` entry added since the baseline one `known` line in the block, for example `known.X added: an open question for the owner`.

### 9. (Medium) Calls through a typed parameter or a tuple-assigned attribute are not resolved
- **What happened:**
  - `show src/pemel_studio/controller.py:Controller.set_current_project` prints `called by no function through a call the map resolved (a call matched by its name alone is not counted)`. grep finds 7 calls, such as `controller.set_current_project(candidate)` in `purge_items(controller: Controller, …)` (`project_items.py:312`).
  - The impact lines of one change describe the same routing two ways. A call through `self.` reads `impact: Controller.select's writes of Controller.selection moved to Controller.set_selection, which it calls`. Calls through `controller: Controller` read `impact: purge_items no longer writes Controller.project; 2 other writers, 57 readers` and `impact: new_project no longer writes Controller.discarded_project, Controller.project; …`.
  - `show src/pemel_service/tasks/runner.py:SerialTaskRunner.finish_commit` also says that no function calls it. Yet `SerialTaskObserver._commit` calls `self.runner.finish_commit()`, and `__init__(self, controller: Controller, runner: SerialTaskRunner, …)` assigns `self.controller, self.runner = controller, runner`.
- **Cause:**
  - Python calls are linked by `map/discover.py:_resolve`, through `structure/store.py:_resolve_call`. It resolves `self.m()`, plain and imported names, `x = C(); x.m()`, and `self.attr.m()` through an attribute set from a constructor parameter.
  - It has no case for an annotated parameter of an ordinary function. `map/discovery_syntax.py:_FileVisitor._visit_function` keeps annotations only for `__init__`.
  - `_FileVisitor.visit_Assign` records a constructor parameter only for a single `self.attr = param` target. Probe: `self.controller, self.runner = controller, runner` gives `injected {}`, while `self.runner = runner` gives `{'Obs2|self.runner': 'runner'}`.
  - Meanwhile the field reader in `structure/extract.py` types the same parameters, and since 5.1 it unpacks tuple targets.
- **Why it matters:**
  - The callers that `show` lists are how an agent checks that a writers agreement's owner is the one route.
  - Impact's "moved to" clause is how FlowGuard says a write was routed, not dropped. Here "no longer writes" describes a routed write, and a reviewer needs grep to tell the two apart.
- **Suggestion:** Type call receivers with the parameter annotations and tuple targets that the field reader already uses. Then one typer serves both fields and calls.

### 10. (Medium) A writers agreement does not see a change made in place
- **What happened:**
  - The agreement is `# flowguard: writers SerialTaskRunner.recovery_warnings SerialTaskRunner.__init__` (`runner.py:823`).
  - `show SerialTaskRunner.recovery_warnings` lists `writes … runner.py:824 SerialTaskRunner.__init__ (assign)` and `reads … runner.py:883 SerialTaskRunner.recover_interrupted (attribute)`. Line 883 is `self.recovery_warnings.append(friendly_error(error))`.
  - The rename's impact line counted that append as the field's `1 reader`. The real reader is `Controller._init_operations` (`for text in self.task_runner.recovery_warnings:`, `controller.py:367`). It is not counted, because `task_runner` is set in `__init__` with no declared type. The line's `untyped reads not counted` does cover that.
- **Cause:**
  - In `structure/extract.py`, writes come only from the targets of `Reader.written`: assignments, augmented and annotated assignments, `for` and `with`.
  - The same file defines `MUTATORS = {"append", "add", "extend", "update", "setdefault", "insert", "appendleft"}`, but only `_target_names` uses them, for return paths.
  - The attribute load before `.append` becomes a `field_reads` row. Probe: `controller.items.append(3)` gives two reads (`['items', 'append']` and `['items']`) and no write.
- **Why it matters:** For a list or dict field, a writers agreement holds only the functions that rebind the field, not those that change what it holds. Any function may append and the agreement still holds. `impact` counts the appender as a reader.
- **Suggestion:** Record a `MUTATORS` call on a field as a write, with the method name. Hold it to writers agreements, at least as a separate "changes in place" member.

### 11. (Medium) Changing a handler's caught types reads as two unrelated reds
- **What happened:**
  - `except (OSError, RuntimeError)` in `SerialTaskObserver._commit` became `except (OSError, ValueError, KeyError, TypeError, RuntimeError)`. That gave `red: Code disappeared: ledger entry "src/pemel_studio/serial_task_observer.py:SerialTaskObserver._commit:(OSError, RuntimeError)" …` and `red: New unregistered fallback: src/pemel_studio/serial_task_observer.py:246 except (OSError, …) …`, the second with a placeholder reason.
  - Narrowing `Controller._event:suppress(ValueError, OSError)` to `suppress(OSError)` did the same. Both times, the reviewed reason and rule were carried over by hand.
- **Cause:** `intent/ledger.py` keys an entry `file:function:caught`, and `evaluate` judges each key alone. A new key gets `PLACEHOLDER_REASON` in its template, and a key that disappeared gets "remove this entry".
- **Why it matters:** The ledger asks for narrow handlers, but narrowing one drops the reason and rule that were reviewed for it. Nothing in the output connects the two reds.
- **Suggestion:** When a key disappears from a function and another key of that function appears with the same count, print one finding: "caught types changed from A to B: rename the key and check the reason again". Put the old entry's reason and rule in its template.

### 12. (Low) `not compared` reasons drop what FlowGuard knows
- **What happened:**
  - Of the integration block's 54 `not compared` items, 47 read `no comparable JSON result`. One is the new pure helper `parts.chosen_modules(part: str, selection: Collection[str]) -> tuple[str, ...]`.
  - Two read `calibration variadic signature is unsupported` (`Controller._event(self, level, event, **fields)` and `RotatingJsonLog.record`), and one reads `calibration closure is unsupported`.
  - In the fix-ledger step, `RotatingJsonLog.__init__` and `_refuse_link(path, name)` changed the exception they raise from `ValueError` to `OSError`, which is exactly what the review finding asked for. Both were `not compared` with `no comparable JSON result`.
- **Cause:**
  - `intent/plugin.py:1277` (`Observations.report`) writes `point['name'] + ': no comparable JSON result'` when a reading has no `sample`. It drops `reading.reasons`, which hold why the call could not be encoded: `runtime.py:_checked` accepts only None, bool, int, float, str, list and dict, so a tuple, set or `Path` is `not JSON data`. The reasons also say when a call had a receiver.
  - The `calibration …` texts are `NotMutable` messages from `intent/sites.py:intercepted`. "Calibration" is FlowGuard's internal name for its call hook, and the Studio has a calibration feature of its own.
  - `_compare` does compare raised exceptions (`value()` gives `{'raises': …}`). The change of exception was unverified only because a `Path` argument is not JSON.
- **Why it matters:** `not compared` is the "unverified" signal. Without its reason, the agent cannot tell whether to change an argument's type, bind `fields`, or accept it.
- **Suggestion:**
  - Carry the first reason and name the argument or the result, for example `argument selection: frozenset is not JSON data` or `a method: its receiver is not JSON data`.
  - Word the hook's refusals without "calibration", for example `a **kwargs signature cannot be hooked`.

### 13. (Low) `show NAME` for a name nothing has gives no "not on the map" line
- **What happened:**
  - `show set_task_window` asks for a name that nothing in the code has. All 39 lines of its default view are import lines such as `pemel_adapters._runtime.model_assembly:ParameterSet (…) -> pemel_adapters._runtime.parameters:ParameterSet …` and `…:TaskReceipt -> …`. `--full` has 63 of them before the word-match header. No line says that nothing is named `set_task_window`.
  - `show "close the open project"` lists re-exports first; `close_open_project` is line 111 of `--full`.
- **Cause:** In `intent/cli.py:show`, `graph.import_aliases(name)` returns "the names an import binds that share a word with `words`" (`structure/api.py:MapHandle.import_aliases`). `show` ranks each of them at 1000, the exact tier, and sets `named = True`. That flag suppresses `not on the map: no function, class, … is named NAME`. The 2026-11-24 note reported the ranking ("alias rows as exact matches"); the hidden line is the new consequence.
- **Why it matters:** Before writing a new owner (`set_selection` and `set_current_project` in this round), the agent runs `show` to find one to reuse. "Nothing is named X" is the answer it needs.
- **Suggestion:** Rank an alias as exact, and let it set `named`, only when its name equals the query.

### 14. (Low) `show --last` keeps one run, so a later check replaces the full suite's record
- **What happened:**
  - The integration step ran the full suite and then `check --static` at 00:02:58. After that, `show --last` printed `FlowGuard 5.1.0 last run: check --static at 2026-11-25 00:02:58`, and the full suite's 54 `not compared` items could no longer be listed.
  - In the calibration step, a verifier run did the same (`the last pytest run selected 0 of 24 intent items`).
- **Cause:** `intent/cache.py:save_last` has one slot per scope: "the next run of that slot replaces it".
- **Why it matters:** `show --last` is the documented way to explain every line of a block. Any later check erases that explanation, and the full suite is the run a report has to explain.
- **Suggestion:** Keep the last pytest run with a complete collection apart from check runs and partial runs, and let `show --last` say which run it prints.

### 15. (Low) An impact line that names several fields counts only the first
- **What happened:** `impact: close no longer writes Controller.discarded_project, Controller.project, Controller.selection; 0 other writers, 0 readers (untyped reads not counted)`. The counts belong to `discarded_project`, which is now removed. `Controller.project` has 57 readers (`impact: Controller.set_current_project now writes Controller.project; 1 other writer, 57 readers`).
- **Cause:** `intent/owners.py:field_impact` takes `shown = (added or moved or hidden or gone)[0]` and computes the other writers, the readers and the `show` hint for `shown` alone.
- **Suggestion:** Give counts per field, or name the field the counts belong to.

## What it cost

### 16. Block time follows the functions changed since the task baseline
- **What happened:** In the full suites, the block went from 74-96 s to 155-171 s within the round, from 11-14 % to 22 % of the run. "Changed" counts module-level functions and class methods whose syntax tree differs from `2256acb` at that step's commit (`git show` and `ast.dump`).

  | Step | Changed (methods) | Block | not compared | Suite |
  |---|---|---|---|---|
  | switch (lead) | 0 | 77.3 s | 4 | 778.0 s |
  | calibration | 7 (3) | 96.1 s, 96.2 s | 14 | 707.1 s, 729.0 s |
  | fix-calibration | 5 (0) | 74.3 s | 9 | 703.0 s |
  | owners | 37 (14) | 155.5 s | 38 | 782.7 s |
  | fix-owners | 38 (14) | 155.5 s | 40 | 782.2 s |
  | ledger | 45 (17) | 163.9 s | 45 | 784.6 s |
  | fix-ledger | 54 (23) | 170.8 s | 54 | 824.0 s |
  | integrate | 54 (23) | 170.7 s | 54 | 789.5 s |

  The block fell when the calibration fix reverted code. It did not follow the number of commits or the cache size.
- **Cause, from the source:**
  1. `intent/plugin.py:Observations.__init__` makes a point of every function and method whose code changed since the task baseline. Functions that read a changed constant or call a changed same-file function count too.
  2. `Observations.scope` binds every point again in every test. `Runtime.hook` calls `sites.intercepted`, which compiles a call stub from the function's text each time (`_recompile`: `ast.parse`, `compile`, `exec`). The intent guide says so: "Calls are recorded through a stub compiled from the function's text, read again in each test."
  3. `Runtime.full` unhooks a function after 20 distinct inputs. But `Runtime.observe` keys a method's call by its arguments without the receiver, so a method called with the same few arguments never reaches 20. It stays hooked for the whole session, with `signature.bind` and a JSON encode on every call.
  4. A call with a receiver never gets a sample (`observe`: "a receiver is never JSON data"). So a changed method yields only `not compared: no comparable JSON result`, and the guide lists methods as not compared. At the end, 23 of the 54 changed functions were methods.
- **Not measured:** the block keeps one total (reported on 2026-11-24). Parsing and compiling the texts of the 54 changed functions takes 20.8 ms per pass here, 6.6 ms for the 23 methods alone. One pass per test over 2888 tests is 19-60 s, the same order as the rise. So recompiling the stubs is a large part of the cost, but I could not split it from the work done on each call.
- **Why it matters:** The cost grows with each task's diff, and in this round it mostly bought `not compared` lines. In a shared tree, where the baseline moves once a round, the late steps pay for every earlier step's changes.
- **Suggestion:**
  - Do not hook a changed method whose comparison cannot run: one with no `same` mark and no `fields`. Give its `not compared` line from the source instead.
  - Compile a function's stub once per session, and reinstall it in each test while the file's bytes stay the same; 5.1 already checks those bytes.
  - Print phase times in `show --last`.

### 17. Cache, comparison with 5.0.1, commands
- **Cache:** It was 42.6 MB after the first suite, 52-55 MB in the middle of the round and 90 MB at the end (a 93.5 MB file). A read-only copy shows 101,154 `site_history` rows from 26 builds, 3.4k to 5.6k per build. With its two indexes, that table takes about 47 MB, which accounts for the round's growth. It is the growth the 2026-11-24 note reported: `structure/store.py:_unlink_file` inserts rows and nothing prunes them.
- **Compared with 5.0.1:** Before the switch, the 5.0.1 block took 511.9 s on a baseline 24 commits old, with an 857 MB cache. The first 5.1 block took 77.3 s with a 42.6 MB cache, after `new-task` and a rebuilt cache. The like-for-like run of 2026-11-24 gave 64.6 s for 5.0.1 and 71.7 s for 5.1. So the drop came from the new baseline and cache, not from 5.1, and within one round the block doubled again (item 16).
- **Commands:**
  - the brief, 0.2 s;
  - `show`, 0.6-0.9 s;
  - `check --static --all`, 2.1-3.0 s;
  - `ledger check`, 0.35 s (1.9 s with a calibration running);
  - `show --last`, 0.13 s;
  - targeted blocks, 3.6-18 s;
  - the verifier block (70 tests), 3.6-4.3 s.

## Round 2, one starting route

### 18. Resolved callers guided a complete removal

`show model_choices` identified the method, its signature and the one resolved
production caller in the first four lines. `show request_identity` pointed to
8 resolved callers, including both sides of local preparation. This distinguished
a method that could be removed with its caller from an identity contract that had
to remain while the setup narrowed. Inspection and targeted tests confirmed both
paths. In pinned 5.1.0, `intent/cli.py:_node_lines` takes the reverse index of
`structure/api.py:MapHandle.resolved_calls` and puts production callers before tests.

### 19. Closing an answered item and deleting an agreement have the same label

The owner approved removal of an old screen and explicitly asked to close the
related item in `known.toml`. `show --last` recorded one `loosened` finding when
that item was removed. The finding was helpful as a check that consent was recorded.
`intent/sources.py:loosened` detects any deletion from `old.known`; it has no
closure state linked to a preserved owner reply. A supported resolution entry
linked to the archived reply could retain this review gate and display why the
item was closed, without making an answered question linger on the live list.

## Round 2, current saved formats

### 20. The call map helped preserve a current cache path

During removal of older-file readers, `show` on the data preview owners exposed
callers in data review, library enrollment and project synchronization. Source
inspection confirmed that the current importer can produce a valid record without
a derived display cache. The obsolete reader went away while the cache can still
be prepared. The four scoped `show` calls took about 2.4 s including the wrapper.
These are resolved call links, as built by `structure/api.py:MapHandle.resolved_calls`;
the current-writer check itself came from reading the code.

### 21. Explain why constants are unavailable in a predicate

An equality check over a short tuple composed from an earlier literal constant
passed its application tests but was marked `uses unavailable binding` in the
contract cells and rows. `intent/anchors.py:_literal_globals` uses
`ast.literal_eval` with a few standard-library constructors, and does not fold
references to earlier local literals inside a tuple. `intent/runtime.py` reports
only the unavailable identifier. Showing the assignment and its unsupported
expression would explain the limit. A bounded fold of names already proven
literal in the same module could cover this case without importing project code.

A separate declaration tried to verify that a retired label returns `None`.
`intent/loader.py` treats a `None` predicate result as outside the rule's domain,
so it refused the row. The application test checks refusal directly and the rule
covers the current labels. The error could name `None` as the out-of-domain
result when that is what it observed.

## Round 2, small-effect delivery

### 22. Signature checks preserved a bound rule when its caller added evidence

An existing numerical decision gained two optional keyword inputs. The first run
reported a signature mismatch for the `same` anchor before trying to reuse its old
proof. The two inputs are now declared as context on the original bound rule;
separate tests verify the added evidence path. `intent/anchors.py` compares the
spelled anchor names with positional-only, positional and keyword-only source
arguments. An explanation distinguishing new optional arguments could direct the
reader to the context syntax when the old rule deliberately holds them fixed.
The finite bound grid was checked, with the existing nonlinear exhaustive-proof
limit reported separately from the passing application tests.

### Follow-up D: checking the installed model code and its package together

The model-code change moved the forward and static-voltage calls to one
versioned entry point. In the focused run, FlowGuard showed two useful reader
lists for new adapter fields and pointed to the existing profile contract in
the engine guide. The lists named the methods that consume the bound execution
entry point and restart metrics. We checked those readers and the guide's
one-second input and continuation-state rules before moving on. The passing
run reported 533 tests, one expected skip, zero red, three impacts and 81
uncompared observations. The ordinary pytest result still matters. The first
run had the same three impacts and zero red alongside test failures from old
fixtures and a package direction violation.

Before the change, `show packaging/` found the source owners and their callers
but said `described by no text`. A nearby application packaging README already
explained the release and diagnostic paths. In 5.1.0,
`intent/docs.py:module_lines` uses explicit about markers and generated regions
to build its contract list. The line is correct about registered contracts, but
sounds as though the directory has no README. Consider wording it as
`no registered contract` and listing any tracked nearby README as a candidate
for the agent to read. Keep the marker as the authority for impact reporting.

### Follow-up F: finding the one owner of a fixed explanation

`show calibration_notes` pointed to `run_job` as the only resolved caller.
That let us remove two obsolete report rules without touching the optimizer.
`show CalibrationSetupDialog` identified the class and its fields, which helped
keep the existing choice and readiness fields in place while adding passive
information icons. Both exact lookups also included dozens of import aliases
outside the resolved caller list. The default views ended by reporting 618
and 835 more lines, of which 530 and 718 respectively shared a word.

The import list is produced by `structure/api.py:MapHandle.import_aliases`.
It looks for overlapping tokens. `intent/cli.py:show` gives those alias rows
the highest rank alongside exact owners. This reproduces the earlier alias
ranking issue on ordinary report and form work. When an exact owner is found,
keep the resolved callers, fields and rules first. Put token-only aliases
in the word-match section or the full view.

### Follow-up E: show an interrupted Python validation as unfinished

The first full pytest process stopped when its environment was restored. Its
log ended before the pytest counts and before FlowGuard's final block. Our
detached retry wrote a separate start and exit receipt and kept verbose test
names. It finished in 945.98 seconds with 2,952 passing tests, 57 failures,
11 setup errors, one expected skip and two unverified intent cells. The
FlowGuard block had zero red and its own outcome still reported the pytest
failure. The separate verdicts helped us keep the ordinary test failures
visible while correcting the retired fixtures.

In 5.1.0, `intent/plugin.py:pytest_sessionfinish` runs the Python verdict
transaction and `Block.pytest_sessionfinish` prints it at the end.
`intent/cache.py:stamp_start` already supports a start marker that survives
a killed Vitest run beside the earlier completed receipt. Reuse that mechanism
for pytest. Then `show --last` can distinguish the last completed verdict
from a later Python run that started and never reported, without treating
process disappearance as a successful test or a verified failure.
