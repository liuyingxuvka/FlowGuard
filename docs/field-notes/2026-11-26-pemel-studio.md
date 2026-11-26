# PEMEL Aging Studio field notes

Observed on 2026-11-26 with FlowGuard 5.1.0 during a Windows CI test-harness repair.

## A test file looks empty in `show PATH`

`python -m flowguard show tests/studio/dialogs/test_dialog_fit.py` printed
`1 file, 0 functions`, followed by advice to add a Markdown `about` marker.
The file contains the parametrized test and its screen-measurement helpers.
In 5.1.0, `structure/extract.py` classifies functions from test files as
`test` nodes, `structure/api.py` filters those out of `functions()`, and
`intent/docs.py:module_lines` counts only that result. A test-file summary
could say that the map holds test nodes and report their count. The general
advice to add a contract document could be limited to implementation files.

## A focused check reports its coverage honestly

`new-task` recorded baseline `bf87bf8236e9` and showed the owner rules and
the existing known item. Pytest reported two passing dialog cases in 18.75 s.
The FlowGuard block reported `0 red` and 8.7 s. `show --last` also said
`the last pytest run selected 0 of 24 intent items; no complete collection
is recorded`. That line made the scope of the green result clear. The local
FlowGuard cache occupied 39 MiB on disk after this run.

## A qualified symbol name keeps the resolved caller list readable

`show layout_settings` found the window-layout store but also reported
101 more lines, 97 of which merely shared a word. The suggested
`show pemel_studio.shell.window_layout:layout_settings --full` returned
the six actual callers in 0.85 s. It confirmed that the main window and
library windows use the same store, so the existing test fixture could
be scoped without duplicating the patch. The subsequent 23-case targeted
run reported one `not compared` call. `show --last` identified the call
and explained that it had no comparable JSON result.

## Field impacts helped review a deferred Qt commit

The focused task-progress, locale and PDF batch passed 193 tests. Its
FlowGuard report listed eight impacts, 45 comparisons without paired
results, zero red findings and zero of 24 intent tests selected.
Three impacts listed the same `SerialTaskObserver._commit_scheduled`
field under its initializer, polling callback and deferred commit. The
two readers led directly to the cancellation and ownership checks that
needed review. An independent test delivered a replacement owner
between scheduling and commit and asserted that the stale callback
could not publish.

FlowGuard 5.1.0's `intent/owners.py:field_impact` computes differences
per function and repeats the field's reader and writer lists for each
difference. A field-grouped summary for these repeated-impact cases
could retain every function location while making a long review
easier to scan. The complete function-level view remains useful.
`intent/sites.py:intercepted` explicitly excludes closure targets, and
`intent/plugin.py:report` separately derives the no-JSON-result entries
from missing comparable readings. The reasons in `show --last` let the
Qt test assertions and the scope of the comparisons be reviewed
independently.
