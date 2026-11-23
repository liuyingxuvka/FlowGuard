# FlowGuard 5.0.1 in a Python desktop project: restructuring and multi-agent work

Observed on upstream `4807f259e07285c2a53afcd11a931a551641929e` (v5.0.1) from
2026-11-18 to 2026-11-23. The project is a desktop engineering application: a
PySide6 interface, a service layer and a numerical engine, with a nested
`pyproject.toml`. Every pytest run loaded `-p flowguard.intent.plugin` and a
small local plugin that works around the excluded-file problem described below.
Several agents worked in one working tree at the same time, and each committed
only its own paths. Most of the period was restructuring: modules moved and
renamed with `git mv`, about 1,500 lines of dead code deleted, a 3,000-line
controller split, shared text helpers moved, and a flat package grouped into
subpackages. A typical run ended with `FlowGuard: 0 red, 23 impact, 316 not
compared`. Sections called addenda add new evidence to the 2026-11-17 and
2026-11-18 notes. "Reproduced" means checked on 5.0.1 in a small scratch
fixture.

## High priority: a source file edited during a run ends the pytest session

### What happened

This happened twice in two days. In the first case the full suite was running
while `src/pemel_service/serialization.py` was edited. After 238 passed tests,
pytest stopped with an `INTERNALERROR` and exit 3. The trace ran from
`flowguard/intent/sites.py` line 529 (`intercepted`) through `_recompile` and
`_parse` to `ast.parse(src)`. It ended in `IndentationError: expected an
indented block after 'if' statement on line 1`.

In the second case, tests were appended to the already collected
`tests/app/test_app.py` during a run. The trace ran from `plugin.py:863`
(`scope`) through `imports.observe_imports`, `_bind_module`, `runtime.hook` and
`sites.intercepted` to `_recompile`, `_parse` and `_source`. There
`inspect.findsource(fn)` raised `OSError('lineno is out of bounds')`. pytest
stopped after 190 of 2544 tests (exit 3), and the FlowGuard block still printed
`0 red`.

Neither trace names the file or the function. With several agents in one tree,
any agent's save can end another agent's 8 to 12 minute run.

Reproduced: in a scratch module whose file was rewritten after import,
`sites._parse(fn)` raised `OSError('lineno is out of bounds')` when the file
became shorter. When the shifted lines began with `if True:` followed by an
unindented line, it raised the same `IndentationError`. Neither error is a
`ValueError`, so both escape the handler around `runtime.hook`.

### What would have helped

A function whose source no longer matches the loaded code is reported as
`not compared: source changed during the run`, with the file named, and the
session continues. At minimum, the run stops with one line that names the file
and the function. An aborted session does not print a plain `0 red` summary.
This is new evidence for the 2026-11-17 request that an interrupted run carry
its own completion status.

Catch `OSError` and `SyntaxError` from `_source` and `_parse` around the hook.
Treat them as `NotMutable` with a reason such as `source of FILE changed on disk
after import`. A cheap guard compares the file at hook time with the file at
import. `imports._remember` already records each project module's source
fingerprint at import, so the guard can compare against that value. A
regression test can import a module, rewrite the file with fewer or shifted
lines, and then open the hook.

### FlowGuard code involved

- `flowguard/intent/plugin.py:739-748`: the `except` at line 747 catches only
  `ValueError`, `TypeError` and `sites.NotMutable`.
- `flowguard/intent/sites.py:137-148` (`_source`, `inspect.findsource`),
  `161-163` (`_parse`, `ast.parse`), `529` (the `_recompile` call in
  `intercepted`).
- `flowguard/intent/imports.py:22-26` (`_remember`, the fingerprint at import).

## Addendum to the 2026-11-17 high-priority section: excluded files have one entry point, and every run needed a local filter there

### What happened

Unchanged in 5.0.1. The project's `pyproject.toml` has
`[tool.flowguard] exclude = ["src/pemel_studio/resources/translations/*.ts"]`.
Every pytest run from 2026-11-18 to 2026-11-23 still loaded this local plugin
with `-p fg_exclude_shim`:

```python
from flowguard.map.common import matches_any
from flowguard.structure import api, store

_original = api.MapHandle._git_changed


def _git_changed(self, since):
    ignore = store.ignored(self.root)
    return [path for path in _original(self, since) if not matches_any(path, ignore)]


api.MapHandle._git_changed = _git_changed
```

With it, no run failed on the `.ts` files. Three agents wrote separately that
the shim was still needed for every run, although `exclude` already lists those
files.

`_git_changed` returns `git diff --name-only` plus untracked files, with no
ignore filter. It is the only source of the task's change set: it feeds
`MapHandle.impact` and `owners.Change.files`. `ignored()` is applied in
`store._build` and in `Change.module` for deleted files. This narrows the
2026-11-17 pointer to `_file_deltas` and `_baseline_facts`.

### What would have helped

As in the 2026-11-17 note: an excluded path never enters the task's change set.
A changed Qt Linguist `.ts` (XML) file then never reaches the TypeScript reader,
and pytest needs no shim.

Apply `ignored(root)` with `matches_any` inside `_git_changed`, so both callers
are covered. Keep the 2026-11-17 regressions: an excluded `.ts` file that
differs from the baseline with the languages extra absent, and an agreement in a
file that this change newly excludes, so that honouring exclude does not hide a
weakening.

### FlowGuard code involved

- `flowguard/structure/api.py:1858-1861` (`_git_changed`, no ignore filter),
  `1778` (`impact` uses it).
- `flowguard/intent/owners.py:90` (`Change.files` uses it), `188`
  (`Change.module` applies `ignored()` for deleted files).
- `flowguard/structure/store.py:435-444` (`ignored()`, applied in `_build` at
  line 443).

## High priority: a moved file or a renamed class is reported as new

### What happened

A file was moved with `git mv src/pemel_service/calibration/v2_projection.py
src/pemel_service/calibration/parts.py`, and one docstring line changed
(`git diff -M --name-status` shows R089). The run then printed:

```
impact: copies _literal: src/pemel_service/calibration/parts.py:_literal has another body than the same-named _literal in packaging/runtime/build_runtime.py, src/pemel_adapters/model_source.py -> fix it, or say why in your report
```

The same three bodies existed at the baseline. An equally old `copies _section`
pair, whose files did not move, stayed `before: ... was broken at task start`.

In another task the class `StreamingLoss` was renamed `GroupedLoss`, with the
same `evaluate` body. The run printed `impact: GroupedLoss.evaluate now writes
ProfileInfo.bound_hits, ProfileInfo.profile_performance; 0 other writers, 0
readers of ProfileInfo`. These writes existed before, under the old name.

This matters because the period had many moves, a controller split and a
package regrouping.

Reproduced with `check --static` in a two-file fixture. Two same-named
`_literal` helpers with different bodies in `app/a.py` and `app/b.py` were
committed, and `new-task` was run. Editing a copy's body in place gives
`before: copies _literal at b.py:_literal was broken at task start`. The same
edit after `git mv app/b.py app/moved.py` (R100) gives `impact` for both
members, because the baseline group then has only one member and no issue.

Cause: `health._module_functions(before=True)` reads baseline nodes only for the
current paths in `change.files`. For a moved file it reads the new path, which
has no baseline blob, and never the old path. So the moved member counts as
fresh. `field_impact` compares writes by function id
(`then.get(function, {})`), so a renamed class has no baseline entry.

### What would have helped

A pure move or rename keeps `before` for a pre-existing copy finding. A renamed
function whose writes did not change gives no `now writes` line, or a single
`renamed from OLD, same writes` line. Only a body that really changed becomes
impact. The guide already says that the comparison runs "a moved file from its
old path" (`docs/intent-guide.md:11`). The structure checks should follow the
same rule.

In `health._module_functions(before=True)`, map each new path from
`Change.renamed()` (`{old: new}`) to its old path, and read
`old_part(old_path, 'nodes')`. Keep the new path's module
(`change._modules[new_path]`) in the baseline ids, so that moved members compare
equal. Then pair removed and added ids that have the same fingerprint, before
`field_impact` and before the copies `fresh` set. This generalises
`_without_moves`, which does it only for anonymous callbacks.

Add two regression fixtures. The first is a `git mv` of a file with a known
copy finding: an in-place edit gives `before`, and the moved edit must too. The
second is a class rename with unchanged attribute writes.

### FlowGuard code involved

- `flowguard/intent/health.py:502-517` (`_module_functions(before=True)`
  ignores renames), `564` (`fresh = nodes - then`).
- `flowguard/intent/owners.py:158-164` (`renamed`, already computed from Git
  rename detection), `1365` (`before = then.get(function, {})`).
- `flowguard/structure/api.py:1894` (`_without_moves`, callbacks only).

## Parallel agents in one working tree share one baseline and one change set

### What happened

Rule 1 of the rules block says to start each task with
`python -m flowguard new-task`. One agent did so and got:

```
baseline 321efbfad670; new task from HEAD 321efbfad670 (was fa329ac344ba, 4 commits before HEAD: those changes are no longer compared; compare them once with python -m pytest --flowguard-base fa329ac344ba)
```

That note reached only the agent that ran it. The other agents shared the
working tree and its `.flowguard/cache`. They lost the comparison of their work
since `fa329ac` without seeing it. The baseline that one agent's `new-task` set
stayed in force for all of them.

The change set is the whole tree against the baseline, although each agent
committed only its own paths. A focused run gave `0 red, 6 impact, 25 not
compared`. All six impact lines were about `PaneHandle._hovered` and
`PaneHandle._pressed` in another agent's uncommitted file
(`shell/project_panel.py`). Three more agents reported the same foreign lines.
One wrote that there is no way to scope the block to one agent's files.

`--flowguard-base` sets a per-run baseline commit. It cannot leave out other
agents' uncommitted edits in the same tree, and no option scopes "this change"
to some paths.

### What would have helped

A workflow where parallel tasks share one tree works with FlowGuard. A run can
limit "this change" to the paths the agent owns. `new-task` warns before it
moves a baseline that other runs are still using.

- A pytest and `check` option such as `--flowguard-paths PATHSPEC`, with an
  environment variable for CI. It limits which changed files count as this
  change for impact, changed and before. Red stays on for every agreement, so a
  recorded agreement cannot be broken outside the scope.
- Named task baselines (`new-task --name area2`, `--flowguard-task area2`),
  stored beside the single one in `.flowguard/cache`.
- `new-task` already prints the compare-once command for its own agent. The gap
  is a warning for the other runs: when `new-task` replaces a baseline that a
  run used within the last N minutes, it says so before it moves the baseline.

### FlowGuard code involved

- `flowguard/intent/cache.py:132-160` (one recorded baseline; `new_task` moves
  it and prints the compare-once note).
- `flowguard/structure/api.py:1858-1861` (the change set is the whole tree).
- `flowguard/intent/plugin.py:1295-1302` (the options are `--flowguard-base`,
  `--flowguard-deep`, `--flowguard-complete`, `--flowguard-rules` and
  `--flowguard-record-tests`; none scopes paths).

## Addendum to the 2026-11-18 note: even same-class `self.attr` reads count as `0 readers`, and `show Class.field` lists no reads

### What happened

Four agents hit the 2026-11-18 issue again, now in its simplest form:

- `impact: Controller.request_continue now writes Controller._closing_window;
  1 other writer, 0 readers of Controller`, while `Controller.request_close`
  reads `not self._closing_window`.
- `PaneHandle.__init__ now writes PaneHandle._hovered, PaneHandle._pressed;
  2 other writers, 0 readers`, while the `highlighted` property reads both.
- Two more lines had the same shape: `Controller.task_dialog` (`3 other
  writers, 0 readers`, while `owns_task_dialog`, `opening_project` and
  `stop_all` read it) and `SingleRecordBackend._comparison` (`2 other writers,
  0 readers`, while its `comparison` method reads `held = self._comparison`).

`python -m flowguard show Controller._closing_window` lists only `writes`
lines. `show PaneHandle.highlighted` says `called by no function through a call
the map resolved`, because a property access is not a call. One agent wrote:
"0 readers invites the reader to skip the check the line asks for."

Reproduced: in a fixture class whose `@property` and a second method read
`self._hovered`, `show Pane._hovered` printed two `writes` lines and no `reads`
line.

### What would have helped

As the 2026-11-18 note asks. In addition, `self.<attr>` reads inside methods and
properties of the writer's class count as readers. They appear as `reads` lines
in `show Class.field`, which the guide (`docs/intent-guide.md:13`) says a field
view lists.

Start from the `symbol_reads` rows `self.<attr>` in methods of the class that
the write binds to. Use them in both `owners.field_impact` and
`owners.field_lines`. Extend the 2026-11-18 fixture with a same-class reader
method and a `@property` reader.

### FlowGuard code involved

- `flowguard/intent/owners.py:1375` (impact readers are `graph.queries` and
  `graph.sql_reads` only), `3077-3090` (`field_lines` reads the same two).
- `flowguard/structure/extract.py:732-735` (the `self.<attr>` loads are already
  recorded in `symbol_reads`).

## `show NAME` lists import aliases that only share a word with NAME as exact matches

### What happened

Three agents reported this separately.

- An impact line for a removed attribute ended `-> check them for this change
  only (python -m flowguard show CalibrationSetupDialog.band)`. That command
  printed unrelated import resolutions (`CalibrationJobStore`,
  `CalibrationPlan`, `resolved_calibration_model`, ...). It printed nothing
  about the removed attribute, its writers or its readers.
  `show ExplorerPage._bands` printed page-contract import resolutions.
- `show _current_basis_text` printed 4 useful lines and then about 20
  import-alias lines such as `current_band_colors`, `render_ui_text` and
  `anode_exchange_current_density_A_cm2`.
- `show citation_text` printed about 35 lines such as
  `pemel_service.calibration.reports:join_text -> ...display_text:join_text`,
  unmarked. Only the trailer said `139 more lines, 129 of them only share a
  word`.

Cause: `import_aliases(words)` returns every import name that shares a token
with the query. `CalibrationSetupDialog.band` gives calibration, setup, dialog
and band; `citation_text` gives citation and text. `cli.py` then ranks each
alias at score 1000, the exact-match tier that goes into the head, and sets
`named = True`. Setting `named` also suppresses the `not on the map` line that
would have said the attribute is gone.

Reproduced in a three-file fixture. `show citation_text` printed
`app.panel:join_text (app/panel.py) -> app.text:join_text app/text.py:1`, and
the same for `render_ui_text`, directly under the node view and unmarked.
`show Pane.render`, for a field that `Pane` does not have, printed the
`render_ui_text` alias line and no `not on the map` line. `show Pane.ui`, whose
tokens drop `ui`, did print `not on the map`.

### What would have helped

Aliases that only share a word with the query are listed under the `word
matches: ... only share a word` header, or wait for `--full`. The guide already
says this. `docs/intent-guide.md:13` lists "the import names that have the
name" before the word-matches line, and "the functions, rules and known entries
that only share a word with it" after it. For a name the map no longer has,
`show` says `not on the map`. The step of a `no longer writes` impact line
leads to a view that shows that write and its former readers and writers.

In `cli.py:1191-1194`, give an alias score 1000 only when its bound name, or its
last dotted part, equals the query or the query's last part. Rank the others
below 1000, so they fall under the word-matches header, and set `named` only for
exact ones. For a `no longer writes` impact line, point the step to
`python -m flowguard show --last`, whose detail lines already hold `other writer
of` and `reader of`. Or let `show Class.field` list the baseline writes of a
field that the current map lacks.

### FlowGuard code involved

- `flowguard/intent/cli.py:1191-1197` (alias ranking and `named`).
- `flowguard/structure/api.py:1648-1662` (`import_aliases`: "the names an import
  binds that share a word").
- `flowguard/intent/owners.py:1386-1388` (the impact step names `show` of the
  removed field).

## The map cache grows without bound: `site_history` is most of a 506 MB `map.sqlite`

### What happened

Found by direct inspection on 2026-11-23, with sqlite opened read-only
(`mode=ro`). The project's `.flowguard/cache/map.sqlite` is 506M (`du -sh`) for
510 tracked Python files. `site_history` holds 967,280 rows from 219 builds
(build 2 to 220), against 7,602 current `site` rows. It grew by about 7,000
rows within the same day. By `dbstat` page sizes,
`sqlite_autoindex_site_history_1` takes 193 MB, `site_history` 185 MB and
`site_history_node` 68 MB. Together that is about 446 MB (88%).

Every relink of a changed file inserts all its current sites into
`site_history`. The UNIQUE key includes `line`, so a line shift stores a fresh
copy of every site of that file. Nothing deletes rows. The only reader is the
copy search's historical groups (`_old_groups`). All agents in the shared tree
write to this one cache.

### What would have helped

A generated cache stays proportional to the source plus a bounded history.

Prune `site_history` in a bounded way. For example, keep the rows of the
recorded baseline build and of the latest build, or prune on `new-task`. Drop
`line` from the uniqueness key, since `_old_groups` deduplicates by signature
set anyway. A one-off `VACUUM` after pruning reclaims the space. The map size
could also appear in the `show --last` timing.

### FlowGuard code involved

- `flowguard/structure/store.py:54-57` (`site_history` schema; the UNIQUE key
  includes `line`), `602` (`INSERT OR IGNORE` on every unlink; no `DELETE` from
  `site_history` anywhere in the package).
- `flowguard/structure/api.py:1610` (`_old_groups`, the only reader).

## A function added since the baseline is `not compared: not a module-level function`, and is listed twice

### What happened

After a focused run (234 passed), `python3 -m flowguard show --last` listed:

```
not compared: _current_basis_text (src/pemel_service/reports/builders.py:1708) -> not a failure / not a module-level function
```

and further down:

```
not compared: _current_basis_text -> not a failure / no comparable JSON result
```

The block line read `20 not compared (no comparable JSON result, not a
module-level function, or 1 other reason)`.

`_current_basis_text` is a plain `def` at column 0. It did not exist at the
baseline `678f9d9`: it is absent from `builders.py` there, and it was added in
`6134660`, a descendant. `run(old=True)` runs the baseline text of
`builders.py`, and `runtime._closed` raises `not a module-level function` for
any qual that the source lacks. A function in a new file gets the correct
reason, `no baseline source`.

The second entry comes from `plugin.py:1028-1030`. It adds
`NAME: no comparable JSON result` for readings without a sample, in addition to
the item's own reasons.

### What would have helped

A function absent at the baseline is `not compared (new since the baseline)`.
Each function appears once in `show --last`, with all its reasons.

In `plugin._compare`'s `run(old=True)`, or in `runtime._closed`, give a qual
that the source does not define its own reason ("new since the baseline"),
separate from a nested or method qual. Merge the grey entry added at
`plugin.py:1028-1030` into the item's reasons.

### FlowGuard code involved

- `flowguard/intent/plugin.py:781-789` (the baseline sealed run on the file
  text), `1028-1030` (the second `no comparable JSON result` entry).
- `flowguard/intent/runtime.py:524-529` (`_closed`: `not a module-level
  function` whenever qual is not in the source's functions).

## Qt overrides that call `super()` are `not compared: calibration closure is unsupported`

### What happened

The 2026-11-17 note reported the confusing wording. The cause is now clear, and
there is no user closure. A run listed `not compared: PaneHandle.enterEvent ->
calibration closure is unsupported`. It listed the same for `__init__`,
`changeEvent`, `leaveEvent`, `mousePressEvent`, `mouseReleaseEvent` and
`PaneSplitter.__init__`. Each of these calls zero-argument `super()`
(`shell/project_panel.py` lines 89, 100, 105, 111, 117, 130 and 146).
`PaneHandle.paintEvent` (line 132) does not call `super()`, and it is not
listed. The agent read the reason as pointing at the application's calibration
subsystem.

Reproduced: for `class Child(Base): def hello(self, x): return
super().hello(x) + 1`, `hello.__code__.co_freevars == ('__class__',)`.
`sites.intercepted` raises `NotMutable('calibration closure is unsupported')`
for it, while a sibling method without `super()` is hooked. The module
docstring of `flowguard/intent/sites.py` (line 8) says "The __class__ closure
is supported", and `_recompile` supports it. Only the check in `intercepted`
refuses it. In a PySide6 app, every Qt override that calls `super()` gets this
reason.

### What would have helped

A function whose only free variable is `__class__` is recorded like any other,
since `_recompile` handles it. In `sites.intercepted`, allow
`co_freevars == ('__class__',)` and build `original` with
`closure=fn.__closure__`. The `types.FunctionType` call today passes no
closure.

If that is not possible, the reason names the real cause in Python terms, for
example `a method that uses super() (implicit __class__ cell): calls not
recorded`. Rename the "calibration ..." `NotMutable` texts (also `calibration
variadic signature is unsupported`) to describe the call hook.

### FlowGuard code involved

- `flowguard/intent/sites.py:500-501` (refuses any `co_freevars`), `510`
  (`types.FunctionType` without a closure), `422` and `441-445` (`_recompile`
  already supports `('__class__',)`), `8` (the docstring).

## Module constants and repeated literals cannot be marked `same`, although the map reads them

### What happened

Seven agent notes describe copies that must agree and that FlowGuard could not
hold. Each agent wrote an ordinary test instead.

- `DEVELOPER_FILES` has the same name in `packaging/app/build_app.py:68` (a
  tuple) and `packaging/app/scan_distribution.py:27` (a set). `ICON_SIZES`
  (`src/pemel_studio/app.py:31`) and `SIZES` (`packaging/app/make_icon.py:24`)
  are equal tuples. Ordinary tests bind both pairs.
- A user-facing text, "Calibration is not available in this installation", was
  a separate literal in three modules: `workflows/calibrations.py`
  (`UNAVAILABLE`), `calibration/supervision.py` and `calibration/readiness.py`.
  The block said `0 red`. A change in one place raises
  `MissingReportTranslation` only at runtime.
- The keys of `error_messages.FEATURE_TEMPLATES` must match the literal codes
  in `EngineFeatureMissing("...")` calls in the engine. A rename on one side
  silently falls back through `dict.get` to the generic text.
  `engine_api.BREAKDOWN_UNAVAILABLE_NOTES` and a warning literal in the engine
  have the same shape.
- An architecture review found `domain._PART_MODULES` beside a calibration
  `PART_MODULES`, and `ENGINE_ERROR_TEMPLATES` beside `simulation_state._ERRORS`
  (six codes with different text). It noted: "FlowGuard offers no candidate
  list".
- A model exponent of 1.5 is held in three places: `build_runtime.py`
  (`_model(..., 1.5)`), `golden_contracts.py` (`FIXED_SHAPES`) and
  `contracts.py` (`APPROVED_IRREVERSIBLE_EXPONENT`). No marker can be placed on
  any of them. The same value also has copies in YAML configuration in a
  sibling folder outside the project root.

The guide says that a Python module constant "gives no const line", and that a
`constants path` region gives none for a Python module. A `same` comment binds
only a function or class below it.

### What would have helped

FlowGuard's purpose covers checking necessary copies against one rule. A copy
held in a module constant or a repeated literal can be recorded and checked
like a function copy. At least, two same-named module constants with different
values in production files are a finding, as two same-named enums or Literal
sets already are.

The map already extracts UPPER_CASE module and class constants as `const` nodes
with a value fingerprint, and the sealed runner already reads literal module
constants from source.

1. Accept `# flowguard: same NAME` above a module-level assignment and compare
   the literal values, with an option for an order-insensitive set or tuple
   projection.
2. Extend the `declarations` structure check to same-named const nodes in
   different production files, for example `DEVELOPER_FILES`. The guide
   (`docs/intent-guide.md:41`) already gives `impact` or `before` for a
   same-named enum or Literal with different members.
3. Optionally, add a lead for a string literal of 20 or more characters that is
   repeated in several production modules.

### FlowGuard code involved

- `flowguard/intent/anchors.py:146-147` (comment heads), `545-557`
  (`_definitions`: only `FunctionDef`, `AsyncFunctionDef` and `ClassDef` are
  bindable).
- `flowguard/structure/extract.py:993-1006` (const nodes are already
  extracted).
- `flowguard/intent/health.py:507-509` (copies use only `kind = 'function'`).
- `flowguard/intent/owners.py:1038-1053` (`declarations_differ` covers enums,
  unions and field declarations only).
- `docs/intent-guide.md:13`, `41` and `69`.

## Checked-in generated files cannot be tied to the code that produces them

### What happened

In each case below a shipped copy went stale and the block reported `0 red`.
The agent found it by hand or with a one-off probe, and then wrote an ordinary
test.

- An example model package, `examples/Supplied_Stack_Model_v2.zip`, must equal
  what `model_exchange.model_package_bytes` writes. After a README wording
  change it no longer imported (`ValueError: model package differs from its
  reviewed source or customer documents`). A probe printed
  `differ: ['MANIFEST.json', 'README.md']`.
- `src/pemel_adapters/resources/model_source.zip` holds `EQUATIONS.md`,
  rendered by `build_model_source.support_documents`. After the manual text
  changed, the run passed with `0 red, 6 impact`, all six about another agent's
  `PaneHandle`. A direct check gave `zip == HEAD render True, zip == new render
  False`.
- `examples/data_input/PEMEL_Data_Guide.html` had drifted from the text that
  `write_template_kit` writes: it lacked one paragraph.
  `examples/data_input/pemel_prepare_data.py` copies the template of the same
  function.
- `packaging/runtime/verification/golden_receipt.json` fields
  `runtime_source_identity` and `supplied_model_sha256` went stale after the
  runtime package was regenerated.
- `input_convention` in `supplied_model.json` must equal
  `SUPPLIED_INPUT_CONVENTION` (`builders.py:1026`).
- Two more notes found the same pattern for generated HTML, YAML and ZIP copies.

The only existing tie between a file and code is the `about` marker. It would
fit a Markdown target, but `documents()` reads markers only from `.md` files,
and a ZIP, JSON or HTML file cannot hold one. The 2026-11-17 section "Attach
independent checks to generated artifacts" was about properties of runtime
output (PDF text). This section is about checked-in copies.

### What would have helped

A project can declare that a checked-in file is produced by a function, or by a
generator command. When a change edits the producer and not the file, the run
gives an `impact` line. This is the rule that `about` markers already apply to
Markdown.

Extend the existing owner of documents tied to code instead of adding a new
mechanism. Accept the about site syntax for any tracked path, declared in
`.flowguard/`, because a ZIP or JSON file cannot hold a comment. For example:

```toml
[produced]
"examples/Supplied_Stack_Model_v2.zip" = "src/pemel_service/model_exchange.py:model_package_bytes"
```

Report `impact: PATH is produced by SITE, which this change edits -> regenerate
it or say why`. For text outputs, a byte comparison (with `normalize_newlines`)
against a declared check command could follow later. The impact line alone
would have caught every case above.

### FlowGuard code involved

- `flowguard/intent/docs.py:67` (`documents()` reads about markers only from
  `.md` files).
- `README.md:76`.

## A function whose result changes because a tracked data file changed gets no line

### What happened

A model resource, `supplied_model.json`, moved to revision 3 with seven new
parameter values. `pytest -p fg_exclude_shim -p flowguard.intent.plugin -q -p
no:cacheprovider tests/engine/test_aging_engine.py` printed
`FlowGuard 5.0 (since 678f9d9): 0 red, 10 impact, 3 not compared`
(`ParameterSet.with_values`, `ParameterSet.validate`, `pack_parameters`). No
line named `supplied_model()`. That function reads
`files("pemel_adapters").joinpath("resources/supplied_model.json")`
(`aging_engine.py:82-88`), and its return value changed for the same empty
input. Only ordinary test pins caught it.

By design, the plugin marks a function changed only through Python source: its
code, the top-level bindings it reads, and imported changed values. The sealed
run cannot read files, so `changed` cannot cover this.

### What would have helped

When a change edits a tracked data file that a function reads through a
literal path, the run names that function with at least an impact line.

Record literal resource paths in the map: `open`, `Path(...).read_text` and
`importlib.resources` `files(...).joinpath("...")` with string literals. When
such a path is in the change set, add `impact: supplied_model reads
src/pemel_adapters/resources/supplied_model.json, which this change edits`. The
`.flowguard/` declaration proposed above for generated files could carry
readers as well as producers.

### FlowGuard code involved

- `flowguard/intent/plugin.py:630-649` (changed means its code, a top-level
  binding it reads, or an imported changed value).
- `flowguard/structure/extract.py` records no resource-path facts.

## Agreements can only be source comments, and delivered source cannot carry them

### What happened

`show SingleRecordBackend._comparison` correctly reported `together candidate
(reference only): SingleRecordBackend._record is written by 2 of the 3
functions that write SingleRecordBackend._comparison`. No marker was added. The
app delivers the calibration sources as `.py` files, and the project's rule
forbids internal tooling text in delivered sources, so a `flowguard:` comment
would have shipped to users. A second agent left model-default agreements
unrecorded for the same reason: those core files ship inside
`model_source.zip`. So a correct together candidate stayed unrecorded.

FlowGuard reads `same`, `together` and `writers` only from `# flowguard:` and
`// flowguard:` comments.

### What would have helped

An agreement can be recorded for code whose source must not carry tool
comments, with the same meaning and loosening rules as the comment form.

Allow `same`, `together` and `writers` agreements in a `.flowguard/` file whose
sites use the existing `path:symbol` site syntax of `known.toml`. For example:

```toml
[agreement.comparison-reset]
together = "SingleRecordBackend._comparison SingleRecordBackend._record"
site = "src/pemel_service/calibration/backend.py:SingleRecordBackend"
```

The same index that reads comments would read them, report `loosened` when one
is edited, and list them in `show`. Keep one reader, so the two spellings
cannot drift.

### FlowGuard code involved

- `flowguard/intent/anchors.py:146-147` (agreements are read only from `#` and
  `//` `flowguard:` comment heads).
- `README.md:39-58` (only the comment form is documented).

## Copy discovery skips classes, and a dead same-named class copy that only tests import went unreported

### What happened

`src/pemel_studio/dialogs/forms.py` defined `ProfileDialog`, `SimulationDialog`
and `ImportDataDialog`. The app used different classes with the same names in
`dialogs/cycle_editor.py`, `dialogs/simulation.py` and `dialogs/data_import.py`.
The copies differed: the `forms.py` `ProfileDialog` titled a new cycle "New
cycle", and the live one "Create operating cycle". No module under `src/`
imported the `forms.py` copies. Four test files did, so those tests passed
against code that users never run.

`python -m flowguard show ProfileDialog` listed both classes. Neither `show` nor
the plugin said that they diverged, or that one had only test importers. pytest
on three of those test files gave `36 passed` and `0 red, 2 not compared`.

The copies check selects only `kind = 'function'` nodes with no dot in `qual`,
so classes and methods are never candidates.

### What would have helped

Same-named classes in different production files whose bodies differ are a
`copies` finding, like same-named module functions. When `show` lists several
definitions of one name, it points out a definition that only test files
import.

Extend `health.copies` to classes. Compare method-name sets and per-method
shape similarity, with the same impact and before rules. In `show NAME` with
several definitions, add one line per definition with its count of non-test
importers. The map has the import edges and the `is_test` flag. For example:
`pemel_studio/dialogs/forms.py:ProfileDialog: imported only by 4 test files`.

### FlowGuard code involved

- `flowguard/intent/health.py:502-509` (`_module_functions`:
  `kind = 'function' AND qual NOT LIKE '%.%'`), `520-565` (`copies`).

## Copies findings do not name the route for a copy that must stay separate

### What happened

`python3 -m flowguard new-task` printed `3 open structure issues (1 other fields
have multiple writers and no writer agreement); highest severity: copy _literal;
copy _section; copy step`. `show _literal` listed three `_literal(tree, name)`
helpers: `packaging/runtime/build_runtime.py:104`,
`src/pemel_adapters/model_source.py:75` and
`src/pemel_service/calibration/v2_projection.py:48`. These are the helpers the
2026-11-17 note described. `build_runtime.py` is a standalone build script that
must not import the app, so the copy is deliberate. The agent concluded that
FlowGuard had no way to record a deliberate separate copy short of a `same`
anchor, and left it. The same line returned in every brief. Two agents reported
this.

The README documents `known add FINDING --act leave` and `--act ask`. But the
copies finding's own step says only "keep one implementation and call it
elsewhere; to bind agreement, write same ...; rename intentionally different
functions". Its impact line says "fix it, or say why in your report".

Other structure steps in the same module already name the route, through
`health._leave`. For example, the labels step ends "... is the owner's
decision; if they are, python -m flowguard known add NAME --act leave --why
TEXT records that". The replay diverged-copy step names `known add
copies:NAME --act ignore --why TEXT`. Only the static copies step lacks it.

The brief line also prints "1 other fields have", and for a count of one,
"1 open structure issues".

### What would have helped

A copies finding's step names every legitimate exit, including recording a
deliberate separate copy for the owner.

End the copies step the way the labels step ends: "whether they must stay
separate is the owner's decision; if they must, {_leave(name)}". Or use the
replay step's wording. Then every copies finding names the `known.toml` route.
Fix both plurals: "1 open structure issue" and "1 other field has".

### FlowGuard code involved

- `flowguard/intent/health.py:554-555` (the copies step), `337-340` (`_leave`),
  `801` (the labels step), `862-863` (the brief line).
- `flowguard/intent/owners.py:1782` (the replay diverged-copy step).
- `flowguard/intent/signals.py:68` (`IMPACT_STEP`).
- `README.md:68`.

## `test ... reaches a writer` lines follow the static import closure

### What happened

`python3 -m flowguard show SingleRecordBackend._comparison` listed more than 20
UI tests (`tests/app/test_app.py`, `test_appearance_mode.py`, `test_i18n.py`,
...) as reaching a writer of `SingleRecordBackend._comparison`. These tests
never construct a calibration backend.

The lines come from `MapHandle._tests_for`, the transitive static import
closure of the writer's file. Its docstring says "Test files whose static import
closure reaches a changed file". In a desktop app whose composition root
imports every service, that closure covers nearly every UI test. The words
"reaches a writer" read as a call path.

### What would have helped

The line says what it measures, and the list is narrow enough to pick tests
from.

Reword it to `test FILE imports the module of a writer (transitively)`. List
first the tests whose recorded calls in the last run reached a writer (the map
stores observed edges), or whose resolved call graph reaches one. Put
import-only tests behind `--full`.

### FlowGuard code involved

- `flowguard/intent/owners.py:3096-3098` (the `test ... reaches a writer`
  lines).
- `flowguard/structure/api.py:1830-1856` (`_tests_for`: the static import
  closure).

## Addendum to the 2026-11-17 timing request: on one baseline, FlowGuard's share of a full suite grew to a third

### What happened

Full suites on baseline `678f9d9`, all within one day:

- `2279 passed`; `0 red, 6 not compared; 38.1 s`.
- `2310 passed in 506.78s`; `0 red, 6 impact, 51 not compared; 97.8 s`.
- `2299 passed in 502.76s`; `0 red, 6 impact, 50 not compared; 94.3 s`.
- `2 failed, 2319 passed, 1 skipped` in 703.7 s; `0 red, 10 impact, 91 not
  compared; 229.1 s`.
- `2321 passed` in 708 s; `0 red, 10 impact, 91 not compared; 239.4 s`.

FlowGuard's seconds rose about six-fold, while the not-compared count rose from
6 to 91. The change set was the whole shared tree (see the section on parallel
agents), so other agents' edits probably added to it. No run measured where the
time went, because the block prints one total.

### What would have helped

As in the 2026-11-17 note: a phase split in `show --last` (map build, call
recording, sealed baseline and current runs, structure checks) that explains
the cost. Cache sealed baseline results by function fingerprint and input
digest, since the baseline side does not change within a task. The path scope
proposed for parallel agents would also bound the work to one agent's files.

### FlowGuard code involved

- `flowguard/intent/plugin.py:186-198` (`timed` and `tool_seconds`),
  `1140-1142` (`seconds()`): one total, no phases.
