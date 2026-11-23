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

## Afternoon: first full adoption (init, owner words, intent rules, ledger) and an architecture round

Observed on the same upstream commit (v5.0.1) in the afternoon of 2026-11-23.
Until then the project had only loaded the pytest plugin, for about a week.
Nobody had run `init` or `new-task`. No owner words were stored, and there
were no `rules.toml`, `tests/intent`, `known.toml` or ledger. The code held six
`same` markers and one `together` marker. The owner noticed and asked for
FlowGuard to be used as designed.

This afternoon one agent adopted it fully: `init`; `req add` R1 to R10, the
owner's words; 14 rules in `rules.toml`; three intent rules in `tests/intent`;
`known.toml` with one `ignore` and six `ask` entries; `ledger init` with 184
entries, 53 of them legacy; and the open structure findings resolved. Then
three read-only architecture reviews and three verifications ran, each in its
own detached worktree. Two fix steps and an integration step ran in the shared
tree. Every full suite of the afternoon ended with `0 red`. The sections are in
order of priority; the first lists where FlowGuard helped. "Reproduced" again
means checked on 5.0.1 in a small scratch fixture.

### Where it helped

- **Owner rules caught deliberate breaks.** Each intent rule was tested with
  a deliberate break, then restored. A changed fixed value in the model's JSON
  resource gave `red: rule SUPPLIED_FIXED_NUMBERS:
  name='irreversible_activity_floor': rule …, code … at
  model_values.py:parameter_number (1 of 4 cells disagree)`. A changed word in
  the English catalogue gave `red: rule PARAMETER_SOURCE:
  build_manual.citation_text: 1 of 4 calls disagree; … (row L32)`. Two saved
  labels dropped from a list gave a red for `SHOWN_ACCURACY_LABEL`. Each rule
  checks shipped data or wording through the real call of its calibrating
  test. The project had no such guard before.
- **Owner words.** For each of ten messages, `req add <file> --id R<n>`
  printed a line such as `stored R1 (request, sha 3d0d4d1f08da, 509 bytes)`.
  `cmp` found all ten byte-identical. It also wrote
  `.flowguard/requests/.gitattributes` (`*.md -text`), so the repository's
  `* text=auto` cannot rewrite them. `show rules` lists the 14 rules, each with
  `(holds)` and the intent test that cites it.
- **Ledger.** After two cleanups changed, ordinary pytest went red at once:
  `red: ledger: New unregistered fallback: data_store.py:778 except
  psutil.AccessDenied can end without raising`. `ledger check` printed the
  entry to paste. `check --static --all` grouped the legacy production
  handlers by body ("returns or substitutes another value: 68 handlers",
  "empty body: 36 handlers", each with file:line). The adopting agent called
  this the most useful review aid of the adoption; it led to two real defect
  fixes. Two later steps moved handlers to other modules and moved their
  ledger keys by hand. Each time `ledger check` (0.3 to 2 s) confirmed the move:
  `184 entries (53 legacy), 190 code handlers; 0 red, 0 unverified`.
- **The structure findings were real.** On a fresh map of the morning's
  HEAD, `check --static --all` (8.4 s) listed `copies _literal` in three files, `copies _section` in
  two, `copies step` in two, and `Project.dirty has no writers agreement and 6
  files write it`. A human-led import-graph audit had not listed them.
  `_literal` became one owner (`engine_api.py:runtime_literal`, `same
  RUNTIME_LITERAL ref`) plus a marked copy in a build script that must not
  import the app. The first try gave `red: comment engine_api.py:83: same
  anchor RUNTIME_LITERAL has conflicting roles, units or signature`: one copy
  returned `Any`, the other `object`. That red was clear and actionable.
  `_section` was merged in the morning's restructuring, after `show _section`
  printed its `before` line. `step` was a false match (two generated model cores) and went to `known.toml` as
  `ignore`. The `Project.dirty` writes were routed through two owner methods
  under a writers agreement.
- **`show` saved searches.** `show ProjectStore.export` and `show
  DataLibraryStore.cleanup_staging` printed `called by no function through a
  call the map resolved (a call matched by its name alone is not counted)`.
  grep confirmed a second project-ZIP writer that only tests call, and a
  cleanup with no product caller, although a document and two ledger entries
  said it ran at start-up. `show
  pemel_service.calibration.setup_meta:setup_availability` printed
  `candidate pemel_service.calibration.backend:backend_availability :?: same
  decision sites (5 of 6 the home's sites)`: a differently named copy, found
  with no prior knowledge. `show src/pemel_service/tasks/runner.py` (0.3 s)
  listed calls by file (`library/data_store.py (10 calls)`, `project/store.py
  (8 calls)`), which showed that the generic task runner also carries
  data-library work.
- **Open questions.** Each `known` line of `check --static --all` pointed at
  an `ask` entry. The integration step checked the four that are about code
  against the source; all four were true.
- **Command cost.** `new-task` took 0.14 to 0.23 s and the brief 0.13 s.
  `show NAME` took 0.3 to 0.8 s (3 to 8 s in one step on the 656 MB cache).
  `check --static --all` took 1.6 to 3.6 s warm and 8 to 9 s on a fresh map.
  `show` ran while a pytest session with the plugin ran in the same tree, with
  no lock error. `new-task` printed the compare-once command correctly.

### High priority (adds to the 2026-11-17 section on task handoffs): "7 still red" counts results of intent items that no longer exist

#### What happened

After the adoption, every brief said `7 still red: python -m flowguard show
--last`. Every pytest block of the same steps said `0 red`. The lead's brief
right after this round's `new-task`:

```
FlowGuard 5.0 brief, baseline 102da4d68d99; new task from HEAD 102da4d68d99 (was b921c3134b9f, 11 commits before HEAD: those changes are no longer compared; compare them once with python -m pytest --flowguard-base b921c3134b9f)
...
7 still red: python -m flowguard show --last
```

At that moment `show --last` printed the previous step's last `check
--static`, `since b921c31, 11 commits before HEAD: 0 red, 9 impact, 1
loosened`, with no red line. Three agents listed the seven with
`cli._brief_reds(cfg, cache.read(cfg))`. A read-only look at the `result` table
shows where they come from:

- `tests/intent/customer_text.py::load`, red, stored at 15:41: five `row
  expect must be a literal` messages for lines 38, 43, 48 and 49. They came
  from an early draft. The file has literal rows now and loads cleanly.
- `PARAMETER_SOURCE[build.citation_text:cells]` and `[…:rows]`, red, stored
  at 15:33: `home gone: build:citation_text (AttributeError: module 'build'
  has no attribute 'citation_text')`. The anchor has since moved to
  `build_manual:citation_text`, whose items were `ok` at 20:08.
- `collection incomplete`: the last session was a 70-test verifier run. Its
  attempt reads `collected 0, declared 9, selected 0`, with all 9 missing.

Two grey rows of an old home, `calibration.parts.parameter_number`, are
also still stored. The integration step saw the count fall to 6 right after
a full run and rise to 7 after the next targeted run. `show PARAMETER_SOURCE`
still prints both `home gone` lines under `cached results are stale or
unverified -> run check`, although the full run made the rule green. One agent
wrote: "A newcomer would think the tree is red." The integration agent had to
read FlowGuard's cache through FlowGuard's own functions to show that the tree
was green.

#### Cause

- A file's `::load` item exists only while the file has load errors
  (`Model.declared_items`, `loader.py:173-178`). A home item's name holds its
  target (`item_names`, `loader.py:130-135`). Once the errors are fixed, or the
  home moves, the old item is no longer declared or run.
- The session writes `result` rows with `INSERT OR REPLACE` by item
  (`plugin.py:1994-1995`). The only deletion is `DELETE FROM result WHERE item
  LIKE '%:live]'` (`plugin.py:1993`). The row of an item that is no longer
  declared stays forever.
- `cache.read` returns every row (`cache.py:427-429`). `_brief_reds` counts
  every `load` row and every red item of a rule (`cli.py:184-194`;
  `_rule_colour`, `cli.py:117-127`).
- `_missing` counts the declared items that a session did not select
  (`plugin.py:1555-1556`). `_brief_reds` turns any missing item into
  `collection incomplete` (`cli.py:198-199`). A targeted run that selects no
  intent item is the normal edit loop.

#### Why it matters

The brief is the one output that every agent reads before it writes code. A
red count that a green full run does not clear teaches agents to ignore it.
Then the brief no longer carries real reds between tasks.

#### What would help

- In the branch that saves a complete collection (`plugin.py:1990-1995`),
  delete the `result` rows whose item is not in `declared`. This also removes
  a file's `::load` row once the file loads.
- Count `collection incomplete` only when a session selected some intent items
  and missed others. A run that selected none can be stated once as a fact:
  "the last pytest run selected no intent item; the last complete collection,
  at TIME, was green".
- As the 2026-11-17 note asked, take the count and the view it names from the
  same record. `show --last` lists none of these seven.
- Regression: a rule file with a non-literal row, a full run (load red), the
  row fixed, another full run: the brief then counts no red. Then move a rule's
  home and run again: the old home's item is gone from the brief and from
  `show RULE`.

#### FlowGuard code involved

- `flowguard/intent/loader.py:130-135` (`item_names`), `173-178`
  (`declared_items`).
- `flowguard/intent/plugin.py:1555-1565` (`_missing`), `1944-1947` (the
  attempt record), `1990-1995` (result rows written, only `:live]` deleted).
- `flowguard/intent/cache.py:409-442` (`read`).
- `flowguard/intent/cli.py:179-200` (`_brief_reds`), `245-264` (`_brief`).

### High priority: the sealed run treats every name that a class body or a computed constant reads as unavailable

#### What happened

In the adoption, `parameter_number` in `calibration/parts.py` was `not
compared: … uses unavailable binding int`. The existing agreement `same
CUSTOMER_FIT_LABEL` had been in `domain.py` since before the round. It gave
`not compared: CUSTOMER_FIT_LABEL … customer_fit_label uses unavailable binding
FIT_ACCURACY_LABEL`, so its copies had not been compared. Later steps saw `uses
unavailable binding object` (`render_message`) and `uses unavailable binding
OFFERED_MODULES`.

The agent ran FlowGuard's own `_scope` over `src/`. In `domain.py` it blocks
`all`, `any`, `bool`, `dict`, `float`, `frozenset`, `int`, `isinstance`,
`len`, `list`, `set`, `str` and `tuple`. In `presentation.py`,
`model_ranges.py` and `calibration/parts.py` it blocks `int`, `float` and
`str`. To get the anchors compared, the agent moved them to modules whose top
level holds only imports: a new `calibration/model_values.py`, and
`display_names.py`.

Reproduced with `runtime._closed(source, qual)`:

- `def parse(x): return int(x) + 1` alone is sealed.
- The same function beside `@dataclass class Row: n: int = 0` gives `uses
  unavailable binding int`.
- `def label(x): return FIT if x else "none"` beside `FIT = "Fit"` and
  `PUBLIC = frozenset({FIT, "Other"})` gives `uses unavailable binding FIT`.

#### Cause

`runtime._scope` (`runtime.py:441-521`). For a top-level statement that is not
a def, an import or an assignment, `names` is every `ast.Name` in it
(`501-506`): for a class, its annotations, bases and decorators too. For an
assignment whose value is neither a literal nor foldable, `names` also takes
every name that the value reads (`496-497`). Each of these names is removed
from the sealed globals and blocked (`507-511`). The guide says that the
globals hold `int`, `str`, `frozenset` and the other listed builtins
(`docs/intent-guide.md:11`). One dataclass in a module takes them away from
every function in that module.

#### Why it matters

Copies and `changed` are both judged in the sealed run. A dataclass, or a
constant built from other constants, is common in a Python module. Here an
existing `same` agreement was never compared, and its reason was one line
among hundreds of `not compared`. The workaround reshapes the project's modules
for the tool.

#### What would help

Block the names a statement binds: targets, class and def names, import
aliases, `global` names, walrus and loop targets. Do not block every name it
reads. Reading a name cannot change a builtin or an immutable literal (a
string, a number, or a tuple or frozenset of literals). Keep blocking a mutable
value that a top-level expression statement may change, such as
`TABLE.update(...)`. Add the three sources above as regressions.

#### FlowGuard code involved

- `flowguard/intent/runtime.py:441-521` (`_scope`), `524-529` (`_closed`).
- `docs/intent-guide.md:11` (the sealed globals).

### High priority: a writers agreement on a dataclass field can never hold

#### What happened

The adoption routed every write of `Project.dirty` through two methods and
wrote `# flowguard: writers Project.dirty
Project.mark_changed,Project.mark_saved` (`domain.py:806`). Every `check
--static --all` after a `new-task` then printed:

```
before: writers Project.dirty at domain.py:Project was broken at task start -> leave it unless your task is about it
```

`show Project.dirty` names the cause: `outside writers:
src/pemel_service/domain.py:786 Project (assign, value False)`. That line is
the field declaration `dirty: bool = False`. The step says "call
Project.mark_changed or Project.mark_saved instead", which a field default
cannot do. Adding the class to the agreement is red: `cannot resolve
pemel_service.domain:Project to one declared function`.

A fix step later added `# flowguard: writers Simulation.state
mark_not_run,…,copy_execution` in this task. It got the same `before` line for
`state: str = "not_run"`, worded `was broken at task start`, although the
agreement did not exist at task start. `known add writer:Project.dirty --act
ask` answered `no place of writer:Project.dirty
(src/pemel_service/domain.py:Project) is a site: name one with --site
path:symbol`, and worked with `--site src/pemel_service/domain.py:Project.dirty`.
Both questions are now `ask` entries in `known.toml`. Four agents reported the
same line, two of them on a fresh map.

Reproduced. A dataclass `Project` with `dirty: bool = False` and a writers
agreement naming only `Project.mark_changed`: `show Project.dirty` prints
`outside writers: app/domain.py:7 Project (assign, value False)`. When the
agreement is added after `new-task` over writes that already exist,
`check --static --all` prints `before: writers Project.dirty at
domain.py:Project was broken at task start`.

#### Cause

- `extract.py:824-825` records a class-body default as a write by the class
  ("a class-body default belongs to its class").
- `health.written_field` already leaves such a row out of the
  many-writers check: "a class-body default declares, it does not write"
  (`health.py:577-580`). `owners.owner_writes` (`owners.py:353-366`) does not.
- A writer in an agreement resolves only to one declared function
  (`anchors.py:205-210`), so the class cannot be named.
- `_writer_issue` judges the current agreement on the baseline code (D2,
  `owners.py:386-388`), so an agreement added over old writes reads `before`.
  The before text is `{subject} at {place} was broken at task start`
  (`signals.py:216-219`).
- `known add` accepts a function, constant or `Model.field` as a site, not
  the class the finding names (`sources.py:953-971`).

#### Why it matters

Every future task's block, and every structure review, carries a `before` line
that nobody can clear without loosening the agreement. The honest route was two
open questions for the owner about FlowGuard's own behaviour.

#### What would help

Apply `written_field`'s class-body rule in `owner_writes` as well, for a plain
default and for `field(default=...)`. Word a member that only the baseline had
outside an agreement this change added as "the code at task start already
wrote it outside this new agreement", not "was broken". Regression: the
fixture above shows no line, and an outside write in a method stays red.

#### FlowGuard code involved

- `flowguard/structure/extract.py:824-825`.
- `flowguard/intent/health.py:570-581` (`written_field`).
- `flowguard/intent/owners.py:353-366` (`owner_writes`), `384-410`
  (`_writer_issue`).
- `flowguard/intent/anchors.py:197-214` (`_indexed_agreement`).
- `flowguard/intent/signals.py:66-67`, `215-219`.

### Writers: the field view lists fewer writers than the agreement holds, and both miss three common write forms

This adds evidence to the 2026-11-17 section on destructuring writes and to the
2026-11-18 note on Python readers.

#### What happened

- `show Controller.task_dialog` listed four writes in `controller.py` and two
  in test doubles (`tests/studio/workflows/test_data_intake.py:142
  Controller.__init__`, a local stand-in class named `Controller`). It listed
  none of the eleven `controller.task_dialog = TaskDialog(...)` writes in
  `workflows/*.py`. There `controller: Controller` is imported under `if
  TYPE_CHECKING:` (for example `workflows/cycles.py:25-26` and `:90`).
- `show Simulation.state` listed three writers. It missed `simulation.state =
  "running"` (`workflows/simulations.py:179`, after `simulation =
  project.simulations[simulation_id]`) and the tuple writes at
  `simulations.py:95` and `:224` and `history.py:147` and `:177`. Its
  `together candidate (reference only): … written by 3 of the 3 functions`
  lines were computed on that incomplete set.
- For `Project.dirty` the map showed 7 writes in 6 files; grep found 18 in 12.
  Among the misses were `self.current_project().dirty = True`
  (`controller.py:614`, `history.py:202`) and `candidate.modified,
  candidate.dirty = durable.modified, False`.
- Writes on a `controller: Any` parameter read as a class named `Any`. The
  last run still shows `impact: _save no longer writes Any.task_dialog; 0
  other writers, 0 readers of Any -> check them for this change only (python
  -m flowguard show Any.task_dialog)`.
- For `previous, self._previous = self._previous, None` a run printed
  `impact: SleepPrevention.release now writes (previous, self._previous); 0
  other writers, 0 readers of (previous, self -> check them for this change
  only (python -m flowguard show (previous, self._previous))`. That command
  cannot run as printed.

The agents concluded that a writers agreement written from the view would miss
these writes. The source shows that this is only partly true. Reproduced with
one dataclass `Project` and six functions that each write `project.dirty`.
Without an agreement, `show Project.dirty` lists the class default, the owner
method and `runtime_typed` (a parameter typed by a runtime import), and
nothing else. With `writers Project.dirty Project.mark_changed`, the agreement
check is red for `runtime_typed`, `checking_typed` (typed by a `TYPE_CHECKING`
import) and `untyped` (a local taken from a dict). It says nothing about
`any_typed` (`project: Any`, reported as `impact: any_typed now writes
Any.dirty`), `tuple_target` (`project.name, project.dirty = "a", True`) or
`chained` (`self.current().dirty = True`). The tuple form with a bare first
name reproduces the `(previous, self._previous)` line exactly.

#### Cause

- `syntax_records` reads import aliases from top-level statements only
  (`extract.py:576-583`). `annotation_class` therefore finds no class for a
  name imported under `if TYPE_CHECKING:`, and the receiver stays unresolved.
  The map's import table does hold that import: `show Project.dirty` prints
  `app.work:LaterProject (app/work.py) -> app.domain:Project`.
- `Any` resolves through its alias to `typing:Any` (`extract.py:594`), so the
  write is filed under a class `Any`.
- `assignment` records `ast.unparse(target)` as the field
  (`extract.py:803`). A tuple target is not walked, and a call receiver
  (`self.current()`) is kept as text, never matched to `Project`.
- `MapHandle.writes` drops unresolved rows unless `by_name=True`
  (`api.py:352`), and keeps only the class's short name (`api.py:350-357`).
  `_writes_target` matches that short name case-insensitively
  (`api.py:2097`), so a test class named `Controller` merges with the product
  class.
- `show Class.field` reads `graph.writes(name)` (`cli.py:1136`).
  `owner_writes` reads `writes(by_name=True)` (`owners.py:360`), which adds
  the writes matched by field name alone.

#### Why it matters

"Check before you change" means reading `show Class.field` before writing a
`writers` or `together` agreement. The view shows fewer writers than the check
will hold, so an agreement or a proposed `together` that looks satisfied
breaks as soon as it is written. The three forms that neither reads leave real
holes in red: a write through `Any`, a tuple assignment and a write through a
call result are all ordinary Python.

#### What would help

1. Read the imports of a top-level `if TYPE_CHECKING:` block into the aliases.
2. Walk tuple and list targets, as the 2026-11-17 note asked, and never print
   a parenthesised tuple as a field name.
3. Treat `Any` and `object` annotations as untyped, so their writes are
   matched by field name like other unresolved writes.
4. Resolve a call receiver through the called method's return annotation when
   the map has it. Otherwise record it as an unresolved write.
5. In `show Class.field`, list the writes matched by field name under a
   heading of their own, so the view shows what the agreement will hold.
6. Keep the owner module in a Python write row, so a test double of the same
   name stays apart.

Use the six-function fixture above as the regression.

#### FlowGuard code involved

- `flowguard/structure/extract.py:576-605` (aliases, `annotation_class`),
  `786-827` (`assignment`).
- `flowguard/structure/api.py:309-369` (`writes`), `2090-2099`
  (`_writes_target`).
- `flowguard/intent/cli.py:1135-1148` (the field view).
- `flowguard/intent/owners.py:353-366`, `3077-3099` (`field_lines`).

### A pytest-only project is never told it is half set up, and nothing points at the cost of an old baseline

This also adds to the morning's timing addendum.

#### What happened

From 2026-11-17 until this afternoon the project ran only `pytest -p
flowguard.intent.plugin`. The owner rules, open questions, ledger and almost
all agreements did not exist. Each block still looked complete:

```
FlowGuard 5.0 (since 321efbf, 87 commits before HEAD): 0 red, 64 impact, 986 not compared; 1511.3 s
FlowGuard 5.0 (since 321efbf, 95 commits before HEAD): 0 red, 106 impact, 1078 not compared; 1654.7 s
```

The brief would have said `baseline 321efbfad670; task start, 109 commits
before HEAD; next task: python -m flowguard new-task`, but nobody ran it. It
said nothing about the missing rules block either.

The block's time follows the baseline's distance much more than the suite's
size:

| Baseline distance | FlowGuard block | Whole run | not compared |
|---|---|---|---|
| 87 commits | 1,511 s | 2,065 s | 986 |
| 95 commits | 1,655 s | 2,230 s | 1,078 |
| 108 to 109 commits | about 1,570 to 1,640 s | 37 to 39 min | not recorded |
| 26 commits | 284.5 s | 15 min 1 s | 144 |
| 11 commits | 164.1 s | 778 s | 40 |
| 7 to 10 commits | 105.9 to 112.7 s | 702 to 749 s | 33 to 34 |

The suite grew from 2,552 to 2,634 tests over these runs. Without the plugin,
2,543 tests took 507 s. So the old baseline quadrupled each full run, and a
`new-task` per step cut the block about fifteen-fold.

#### Cause

- The block's title names the distance and no step (`signals.baseline_label`,
  `signals.py:267-284`). The only `new-task` hint is the brief's
  (`cache.remember_baseline`, `cache.py:168`).
- `_stale_rules` reports a rules block that differs (`cli.py:2779-2799`). For
  a missing file `_rules_text` returns empty text (`cli.py:2765-2766`), so no
  line says that there is no block at all.
- The plugin says nothing when there is no `rules.toml`, `tests/intent`,
  `known.toml` or ledger. `ledger init` already tells a project whose pytest
  does not load the plugin to run `init` (`cli.py:2866`). The reverse case has
  no such line.
- The work grows with the change set: every function in `git diff baseline`
  is hooked and compared (`plugin.py:528-531`, `666-691`).

#### Why it matters

A project that adopts only the plugin, as this one did, sees `0 red` and
believes the agreements, owner rules and ledger are checked. Nothing says
otherwise. An old baseline also cost about 25 minutes per full run here, and
it buried this task's lines among 64 to 106 impact lines from earlier tasks.

#### What would help

- When AGENTS.md and CLAUDE.md have no rules block and there is no `rules.toml`
  and no ledger, print one line in the block and in `show --last`: "only the
  pytest plugin is set up: python -m flowguard init adds the rules block, the
  sentinel and the CI step".
- When the baseline lies more than some number of commits before HEAD, say 20,
  add the step to the title as the `missing` case already does: `since
  321efbf, 87 commits before HEAD -> python -m flowguard new-task starts the
  next task`. A long task may keep its baseline, so this is a pointer, not a
  failure.
- Give `show --last` the phase split the morning addendum asked for, with the
  number of changed files and functions compared, so the cost of an old
  baseline is visible.

#### FlowGuard code involved

- `flowguard/intent/signals.py:267-284` (`baseline_label`).
- `flowguard/intent/cache.py:132-172` (`remember_baseline`).
- `flowguard/intent/cli.py:2759-2799` (`_rules_text`, `_stale_rules`),
  `2866` (the `ledger init` hint).
- `flowguard/intent/plugin.py:528-531`, `666-691`.

### Addendum to "a source file edited during a run ends the pytest session": a file deleted during a run fails in `loosened` and hides pytest's summary

#### What happened

A fix step ran a targeted suite in the background and ran `git rm
src/pemel_studio/workflows/comparison_commands.py` while it ran. At session
finish the plugin raised `KeyError:
'src/pemel_studio/workflows/comparison_commands.py'` in `owners.py:1259
stated_now` (`change._modules[path]`). The call came from `loosened()`, from
`static_findings()`, from `plugin.py:1065 report`. The output showed 18 `F`
marks but no failed test names and no `-r` summary. The agent reran without
the plugin (`-o addopts=""`) to learn which tests failed. This is a third
route besides the two traces of the earlier section.

#### Cause

`loosened` builds `edited` from `graph._kinds('anchors', 'anchor_issues')`
and indexes `change._modules[path]` for each path (`owners.py:1257-1261`).
`_kinds` caches the path list once per map handle (`_derived['paths']`,
`api.py:195-196`). `Change.__init__` reads `_modules` from the `file` table
again (`owners.py:91`). A build committed to the shared `map.sqlite` between
the two reads drops the deleted path from one list and not the other
(`store._unlink_file` deletes the row). In this tree other agents' `show` and
`check` calls build that file. I did not reproduce this exact sequence. Even
with the module found, `read_source(graph.root / path)` would then fail on
the deleted file.

#### What would help

Read both lists in one transaction, or treat a path that `_modules` or the
disk no longer has as deleted, with no comments now. `Change.module` already
does that for a deleted file (`owners.py:177-194`). As the earlier section
asks, an internal error at session finish should print its text after
pytest's own summary, never instead of it.

#### FlowGuard code involved

- `flowguard/intent/owners.py:88-95` (`Change.__init__`), `1226-1262`
  (`loosened`, `stated_now`).
- `flowguard/structure/api.py:190-198` (`_kinds`).
- `flowguard/structure/store.py:599-606` (`_unlink_file`).

### A merged copy and a moved marked function both read as `loosened`

#### What happened

- One step deleted `pemel_studio/product.py:model_name_with_revision`, marked
  `same MODEL_TITLE`, and kept the reference
  `display_names.model_name_with_revision` (`same MODEL_TITLE ref`). Every
  caller now calls the reference. The run printed `loosened: same MODEL_TITLE
  removed from src/pemel_studio/product.py:model_name_with_revision -> name it
  in your report; loosening an agreement is the owner's decision`. All four
  blocks of the next step repeated it, and the last run still shows it.
- The adoption moved `customer_fit_label` from `domain.py` to
  `display_names.py`, with the same comment and the same reference. It printed
  `loosened: same CUSTOMER_FIT_LABEL removed from domain.py:customer_fit_label`.

Reproduced. A `same TITLE ref` and a `same TITLE` copy: delete the copy and
import the reference. A `same LABEL` copy: move it, with its comment and body,
from `ui.py` to `other.py`. `check --static` printed:

```
loosened: same LABEL removed from ui.py:label -> name it in your report; loosening an agreement is the owner's decision
loosened: same TITLE removed from ui.py:title -> name it in your report; loosening an agreement is the owner's decision
```

#### Cause

`loosened` compares `same` marks per `(name, function id)`
(`owners.py:1328-1331`). A function that moves to another module, or is
deleted, leaves its old pair with no current row. The docstring covers files
that Git reports as renamed (`_moved_modules`), not a function moved between
two existing files.

#### Why it matters

A merge into the reference is the outcome that a copies finding asks for
("keep one implementation and call it elsewhere"). Reporting it as an owner's
loosening decision makes every later agent re-explain the line until the
baseline moves.

#### What would help

Before writing `same NAME removed`, check two cases. If the function is gone
from the map and the group keeps its reference, write "copy deleted: TITLE now
has only its reference (names.py:title)". If a `same NAME` row with the same
qualified name and body fingerprint exists in another file, write "moved to
other.py:label". Keep `loosened` for a mark removed from a function that is
still there.

#### FlowGuard code involved

- `flowguard/intent/owners.py:1226-1332` (`loosened`).

### Ledger: 53 handlers stay "unreviewed" because their form cannot take a reason

#### What happened

`ledger init` printed `184 legacy entries, 189 handlers (53 forms cannot be
newly registered)`. After the review, 131 entries had a reason and a rule
sentence. The other 53 can only keep `rule = "旧账"` and the fixed reason
`Legacy, unreviewed: … when editing it, explain what it does …`. By caught
form: 18 `BaseException`, 17 `Exception`, 16 `contextlib.suppress` with named
types (for example `suppress(OSError, ValueError)` six times,
`suppress(ProcessLookupError)` once), and 2 warning filters. 28 are in `src`,
21 in tests, 3 in packaging and 1 in CI.

Some were judged right in review. `Controller.dispatch` shows the text of every
command error. The serial task observer fails the task with the error. Test
helpers collect assertion errors from a modal dialog. Narrowing `except
Exception` in a Qt slot would let an unexpected error escape the event loop.
A reviewed entry for these forms is red: `a ledger entry cannot clear this
failure`.

Two smaller points:
- Moving a handler needs a hand edit of the key in a 72 KB TOML file.
  `ledger` has only `init` and `check`. The check made the edit safe.
- `ledger check` prints `184 entries (53 legacy), 190 code handlers`. To
  learn how many legacy handlers are in production code, an agent parsed the
  TOML with `tomllib`.

#### Cause

The module docstring makes these forms unlistable: "they are red until the code
changes" (`ledger.py:12-16`). `_python_refusal` refuses every
`contextlib.suppress`, whatever it names (`ledger.py:139-151`). `except
OSError: pass` is listable, because only `Exception` and `BaseException` are
broad. `ledger.py:405-409` makes a reviewed entry red for a refused form.

#### Why it matters

The ledger's job is to make every fallback explicit with its reason. For these
53 the reviewer's verdict has no place, and "unreviewed" stays false forever.
`suppress(OSError)` is the same handler as `except OSError: pass`, which the
ledger accepts.

#### What would help

- Treat `contextlib.suppress(T, ...)` with named, non-broad types like
  `except (T, ...): pass`: listable, with a reason and a rule. Here that covers
  16 of the 53.
- Whether a broad handler at a documented boundary (an event-loop slot, a
  worker's top level) may carry a reviewed reason is FlowGuard's owner's
  decision. If it may, keep the rule that the count cannot grow, and let the
  entry record the reason and the rule sentence.
- In `ledger check`, split the legacy count into production and tests.
- When a key vanishes and an unlisted handler with the same caught type and
  body appears in another function, print the entry to move.

#### FlowGuard code involved

- `flowguard/intent/ledger.py:12-16`, `44-45` (`LEGACY_REASON`), `139-151`
  (`_python_refusal`), `405-409`.

### A changed function that no test calls is not in the block at all

#### What happened

The integration step changed `engine_cancel_worker` and `cancellation` in
`packaging/app/diagnostic_runtime.py`, inside the project root. No pytest test
runs them; a frozen-app check and CI's diagnostic do. The full-suite block
read `0 red, 9 impact, 1 loosened, 34 not compared; 112.7 s`. Neither function
was in it or in `show --last`, and the 34 were the same 34 as in the run
before. `check --static --all` was silent too. The project's rules say "`not
compared` means unverified", so a reader takes the 34 as the whole list.

Reproduced. In `app/calc.py`, `called` is changed with the same result and
`uncalled` is changed to another result. The only test calls `called`. The
block reads `FlowGuard 5.0 (since 573ff9a): 0 red; 0.1 s`, and `show --last`
adds nothing.

A related cost: the functions that two refactors most needed compared were
`not compared`: `render_message` and `format_message` (their arguments are a
`str` subclass carrying a template), `CommandRegistry.enabled`, and
`load_settings`, which returns a dataclass of `str` and `Path` fields (`no
comparable JSON result`). A byte comparison outside FlowGuard did the check.

#### Cause

`_compare` builds its items from the samples of recorded calls
(`plugin.py:797-800`). A changed point with no recorded call gets no item and
no reason. The comment at `plugin.py:1024-1026` says so: "Only a call due for
a comparison is `not compared`". The vitest side reports `not reached by any
test`, but only for same-name copies (`docs/intent-guide.md:79`).

#### What would help

Print one count after `not compared`: `2 changed functions ran in no test`,
with the names in `show --last`. It is not a failure. For results, an opt-in
projection of a dataclass whose fields are JSON values or paths
(`dataclasses.asdict`, `str(path)`) would make settings readers and similar
refactors comparable.

#### FlowGuard code involved

- `flowguard/intent/plugin.py:666-691` (changed points), `769-829`
  (`_compare`), `1024-1030`.

### `check --static --all` in a structure review: one line per member, `before` lines that name nothing, and copies found only by name

#### What happened

The repository's rules make `check --static --all` the structure review of
architecture work. Its output was the hardest FlowGuard output to act on:

- One finding took seven lines. `Project.dirty has no writers agreement and 6
  files write it` was printed once per writer, as `before: Project.dirty has
  no writers agreement and 6 files write it, PLACE among them; so at task
  start -> leave it unless your task is about it`.
- `before: copies _literal at build_runtime.py:_literal was broken at task
  start` names neither the other copies nor how they differ. "Broken" reads
  like a broken agreement, but no agreement existed: these were unregistered,
  diverged look-alikes.
- Every `before` line ends `-> leave it unless your task is about it`. In a
  structure review the task is about all of them. The finding's own step
  ("keep one implementation and call it elsewhere; to bind agreement, write
  same … ref …") is not on the line.
- `ignored: 2 (act = "ignore")` stood for one `known.toml` entry with two
  sites. A reader cannot tell entries from members.
- `show setup_availability` found the differently named copy
  `backend_availability` (same decision sites, 5 of 6). `check --static --all`
  printed no line for it. The two had already diverged: one commit had added
  the error cause to only one of them. Three Windows device-name rules with
  different contents were also found only by `show "whether a name is a
  Windows device name" --full`, at lines 25 to 27 of 274.
- `show RECORD_PASSES` led to `lead unbound candidate
  pemel_adapters.operating_points:point_seconds … look-alike, not run: shared
  number 1e-05` and one more unrelated function. The functions that compute
  the same pass count were not suggested.
- `show Controller.flush_document_edits` said `called by 10 functions through
  resolved calls`, all in `controller.py`. About 21 calls from workflow
  modules, typed `Controller` under `TYPE_CHECKING`, and 5 calls on
  `controller: Any` were not counted. A call through a local alias (`minimize =
  optimizer_boundary.spsa_adam_minimize` and then `minimize(...)`) was not
  resolved either. The caveat about name-only calls is printed only when the
  list is empty, so a non-empty list reads as complete.

#### Cause

- `signals.deliver` writes one line per member (`signals.py:182-219`). For a
  `before` line it prints `{subject} at {place} {verb}` and drops `what`,
  which for copies names the other files (`health.py:558-560`).
- `BROKEN` has a verb only for `same` (`signals.py:67`). Every other family
  says `was broken at task start`. `BEFORE_STEP` is one fixed text
  (`signals.py:66`).
- `ignored` counts `(finding, member)` pairs (`signals.py:238`), printed as
  `ignored: N` (`cli.py:446`).
- `health.copies` groups module functions by name (`health.py:520-541`).
  Decision-site candidates (`search_homes`) run only in `show` (`cli.py:360`,
  `1118`).
- A look-alike needs only "a shared number other than 0, 1, -1 and 2"
  (`owners.py:1643-1648`).
- The callers line adds the caveat only when nothing was found
  (`cli.py:895-900`).

#### What would help

- One line per finding: the subject, the member count and the files. The
  members go to `show --last` and `show NAME`.
- For copies, keep `what` in the `before` line and give one input on which
  they differ when the sealed run has one, or the `show` command. Say
  "differed at task start" for an unregistered copy. Keep "was broken" for a
  recorded agreement.
- With `--all`, give each finding its own step instead of `BEFORE_STEP`.
- `ignored: 1 entry (2 members)`.
- List the strong decision-site candidates in `check --static --all` as copy
  leads, for example from 5 of 6 sites up. The copies job is about judgments
  that must agree, whatever their names.
- Do not lead on a shared number alone, or rank such leads below shape
  similarity.
- Add `(N more calls match by name only)` to a non-empty callers line too.

#### FlowGuard code involved

- `flowguard/intent/signals.py:66-67`, `133-238` (`deliver`).
- `flowguard/intent/health.py:520-565` (`copies`), `588-639` (`writers`).
- `flowguard/intent/owners.py:1643-1648` (`_look_alikes`).
- `flowguard/intent/cli.py:360`, `446`, `886-900`, `1118`.

### Writing the first intent rules: what got in the way

All three rules work (see "Where it helped"). Getting there took most of the
adoption. Each point below concerns owner rules or the owner's words.

- **A home named like an installed package.** `tools/model_manual/build.py`
  was mapped as module `build`. Python imported the installed `build`
  package instead: `red: rule PARAMETER_SOURCE: home gone: build:citation_text
  (AttributeError: module 'build' has no attribute 'citation_text')`. The
  project renamed the script, which also fixed a real shadowing in another
  script's `from build import`. So the red was right. But the line did not say
  which file `build` resolved to, so it read as a FlowGuard fault.
  `engine.run_home` prints only the target and the error (`engine.py:1055`).
  Suggestion: name the imported module's file when it lies outside the project
  root.
- **A test that loads a project file by path ends the session.** A test that
  used `importlib.util.spec_from_file_location` and registered the module in
  `sys.modules` stopped pytest with `ValueError: build_manual was imported
  before source verification: …; start a fresh verification process`
  (`imports.py:291-293`). It is not a test failure; the whole session ends.
  Suggestion: report it as one line for that module and let the session
  finish.
- **A rule with `fields` is judged at every call the tests reached**
  (`engine._at_calls`, `engine.py:1138-1141`). Tests that pass synthetic
  catalogues went red: `red: rule PARAMETER_SOURCE: identifier='empirical' …:
  rule 'Empirical', code 'en empirical'`. The fix was a `fields
  language_label=ui["language"]` clause, so that the rule has no opinion on a
  synthetic catalogue. The guide gives no pattern for a rule about data that
  an anchor receives. Suggestion: one guide example.
- **A rule cannot say "not shown".** `None` means no opinion
  (`.agents/skills/flowguard/reference.md:79`), and the anchor returns `None`
  for a label it hides. That half of an owner rule stays in an ordinary test.
- **The red step blames the code after a data change.** After only the
  model's JSON resource changed, the step read `-> change the code so
  model_values.py:parameter_number follows rule SUPPLIED_FIXED_NUMBERS`
  (`signals.rule_steps`, `signals.py:940`). Suggestion: when the home's source
  is unchanged since the baseline, add "its source is unchanged; a file it
  reads may have changed". This ties to the morning section on tracked data
  files.
- **The comment does not fit a line.** A `same … calibrated_by=…
  fields …` comment is 204 characters at `tools/model_manual/build_manual.py:245`.
  The parser reads `calibrated_by=(\S+)(?=\s+fields\s|\s*$)`
  (`anchors.py:723`), so a trailing `# noqa` breaks it. The project told ruff to
  treat `flowguard` as a task tag. Suggestion: allow a continuation line, or a
  trailing linter pragma.
- **The date of the owner's words.** `req add` records only `received`, the
  storage time (`map/requests.py:32`, `46`). The owner said these words on
  2026-11-18 and 2026-11-22, and only the order R1 to R10 and a commit message
  keep that. Suggestion: `req add --said YYYY-MM-DD`.
- **A nested project cannot cite the repository's own rules.** A rule's
  document source must lie inside the project root (`sources.py:154`). The
  repository-root AGENTS.md holds an owner rule that the project needs, but it
  cannot be cited from the nested project.

### Documents: `show PATH` prompts for a marker, but stacked markers have an empty span

#### What happened

- Helped: `show src/pemel_service/simulation/profiles.py` printed `described
  by no text: put <!-- flowguard: about src/pemel_service/simulation/profiles.py
  --> above the Markdown text that is its contract`. A paragraph of
  `docs/ENGINE_ADAPTER.md` had already drifted from that module. Two markers
  were added later, and `show docs/ENGINE_ADAPTER.md` confirmed one at once:
  `docs/ENGINE_ADAPTER.md:58 describes src/pemel_service/simulation/profiles.py`.
- `show docs/ARCHITECTURE.md` prints only `document docs/ARCHITECTURE.md`. The
  text names about 60 source paths and symbols. The module view prompts for a
  marker; the document view gives no hint.
- Two markers stacked above one paragraph tie only the second one to it.
  Reproduced with `docs.markers`: `('src/a.py', 3, '')` and `('src/b.py', 4,
  'One paragraph for both sites.')`. The empty span is accepted without a
  finding. A marker inside a Markdown table splits the table, so a table of
  modules cannot be tied row by row.
- A marker on a file is reread for one-hop callers too: `impact:
  docs/ENGINE_ADAPTER.md:58 describes src/pemel_service/simulation/profiles.py,
  whose …:source_from_data is called by src/pemel_studio/task_worker.py:execute_task,
  which this change edits -> reread that text`. That edit only made one
  argument of `execute_task` required. It is one line and easy to dismiss, but
  it will return for nearly every edit of `execute_task`.

#### Cause

- `docs.markers` ends a span at the next marker or heading
  (`docs.py:75-98`).
- `docs.findings` gives the neighbour impact for a file site when an edited
  function in another file calls into it, or is called from it
  (`docs.py:153-161`, `_linked` `298-313`).

#### What would help

- Let consecutive markers share the span below them, or make an empty span an
  input finding.
- In the document view, list the map's paths and symbols that the text names
  and that no marker ties, as candidates to tie.
- Name the called function in the neighbour line and rank it below a direct
  edit.

#### FlowGuard code involved

- `flowguard/intent/docs.py:75-98` (`markers`), `140-161`, `298-313`.

### `init`: a CI step that runs the suite again, and a sentinel the formatter rewrites

#### What happened

`init` was probed first in a scratch worktree. It printed one line,
`Initialized intent sentinel, pytest plugin, CI fragment and seven project
rules.`, and wrote a small, reviewable set of files. Three points cost time:

- `.flowguard/ci.yml` says to merge `actions/checkout@v5` with `fetch-depth: 0`
  and `python -m flowguard check --all --deep`. `init` itself had added
  `addopts = "-ra -p flowguard.intent.plugin"`, so CI's ordinary pytest step
  already runs the intent items. `check --all --deep` runs the ordinary tests
  itself (`docs/intent-guide.md:9`), so merging it as written runs a 12 to 15
  minute suite a second time, with mutation checks, inside a 25-minute job.
  The agent added only an install step. The fragment does not say that it
  replaces the project's pytest step.
- The sentinel is not in formatter style. `ruff format --diff` on it adds two
  blank lines after the docstring and one inside the function (`1 file would
  be reformatted`). `init` refuses a changed sentinel: `an existing test needs
  merging with the intent sentinel` (`cli.py:2808-2809`). So formatting the
  file blocks the next `init`, which is the route to rewrite a stale rules
  block. The project excludes the file from `ruff format`.
- A new AGENTS.md starts with two blank lines (`content.rstrip() + newline +
  newline + rules` on empty content, `cli.py:2827`).

#### What would help

- In the fragment, say that `check --all --deep` replaces the project's pytest
  step, or offer `check --static --all` beside an existing step that loads the
  plugin.
- Write the sentinel in black style, and compare an existing sentinel by its
  syntax tree rather than its bytes.
- Write no leading blank lines into a new AGENTS.md.

#### FlowGuard code involved

- `flowguard/intent/cli.py:28-32` (`SENTINEL`), `2716-2721` (`CI_PYTEST`),
  `2802-2827` (`init`).

### Addendum to the cache section: 707 MB, a second unbounded table, and the task baseline in the same file

#### What happened

`map.sqlite` grew through the day: 527 MB this morning, 571 MB at the round's
start, 619 MB after the adoption, then 655, 669 and now 707 MB (706,961,408
bytes). A fresh map of the same tree, built by `check --static --all` in a new
worktree, is 34 MB and took 8 s.

Read-only, with `dbstat`: `site_history` now holds 1,267,658 rows from builds
2 to 288. With its two indexes it takes about 587 MB, 83% of the file. The
second-largest part is `meta` at about 74 MB: 53,976 `baseline_facts:` rows for
1,498 baseline records. The verifier saw the file's mtime change after a
`show`, because `show` and `check` build the map too.

#### Cause

- `site_history` as in the morning section (`store.py:602`).
- A baseline record's key includes the file path (`api.py:463-466`), and
  `_put_parts` writes each of its kinds as a meta row (`api.py:456-461`). No
  code deletes from `meta`, so every baseline version of every path stays. A
  `git mv` of 36 files stores their baseline facts again under the new paths.
- The task baseline (`meta.task_baseline`, `cache.py:121-125`), the intent
  results (`result`) and the test readings (`reading`) are in the same file.

#### Why it matters

The obvious fix for a 707 MB cache is to delete it. That also deletes the task
baseline, so the next run records HEAD and stops comparing the task's commits.
It also deletes the stored intent results and test readings. Nothing says so.

#### What would help

Keep the task baseline and the test records apart from the rebuildable map, so
that the map can be deleted safely. Prune `baseline_facts` to the recorded
baseline commit, as the morning section suggests for `site_history`, for
example on `new-task`.

#### FlowGuard code involved

- `flowguard/structure/api.py:456-466`.
- `flowguard/structure/store.py:54-57`, `599-606`.
- `flowguard/intent/cache.py:101-125`.

### Addendum to the module-constants section: `show CONSTANT` prints nothing about a Python constant

`show EVENT_RULES` opens with 11 import lines of unrelated names
(`sufficiency_rules`, `RULES`, `EventLink`, `TaskEvent`, …) and then `word
matches: the 101 lines below only share a word`. It never prints the
declaration (`data/prescribed.py:52`) or the identical table `EVENT_TEMPLATES`
(`data/display_text.py:124`). Those two must agree: one module recognises a
stored rule by its exact text. `show MAX_POINTS` does not print
`report_cache.py:34` or `report_sampling.py:11`, even with `--full`. `show
SUPPLIED_MODEL_METADATA_FIELDS` does not name its identical copy
`_SUPPLIED_METADATA` (`library/model_store.py:66`). The guide says that "a
Python, C, C++ or C# module constant gives no const line"
(`docs/intent-guide.md:13`). So the view that the rules block tells agents to
run before they change a constant has no line about that constant. The map
already holds Python const nodes with value fingerprints (see the morning
section). Suggestion: print a Python constant's declaration line, and
"same value as FILE:NAME" for an equal const node in another production file.

### Addendum to the import-alias and moved-file sections: the same gaps at module scale

- After 36 modules moved with `git mv` (R091 to R100), 39 of 106 impact lines
  named a class or function from a moved file whose code had not changed. For
  example `impact: SleepPrevention.__init__ now writes
  SleepPrevention._previous, SleepPrevention._set_state; 1 other writer, 0
  readers of SleepPrevention`, for `power.py` moved to `calibration/power.py`
  with docstring edits only. A class moved between existing files read the
  same: `ScientificTaskReservation.__init__ now writes
  ScientificTaskReservation.folder, ScientificTaskReservation.path; 0 other
  writers, 0 readers`. In one step `not compared` grew from 591 to 986 items
  with no change of behaviour.
- `show src/pemel_service/power.py` (the old path) printed `word matches: the
  2960 lines below only share a word`. `show src/pemel_service/builders.py`
  (split into eight modules) printed one unrelated line and `word matches: the
  2967 lines below only share a word`. Neither printed `not on the map` or where
  the code went. Suggestion: for a path that Git reports as renamed since the
  baseline, print "moved to NEW_PATH"; for a deleted one, print "deleted since
  the baseline".
- `show "which task operations run in the service"` printed 38 import-mapping
  lines and then `… 1718 more lines`. Neither the dispatch table
  (`tasks/runner.py:76`) nor `task_worker.execute_task` was among them. `show
  load_settings` printed 38 lines, of which the first three were the answer and
  35 were alias rows that share a word. As the morning section asks, these rows
  belong under the `word matches` header.
