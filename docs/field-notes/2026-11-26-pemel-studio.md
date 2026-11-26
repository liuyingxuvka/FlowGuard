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

## A dynamic write to a mapped field reads as a field access

`show LibraryStore._parsed_models` reported the constructor as its writer
and `LibraryStore._load` as a reader. In `_load`, the exact target
`self._parsed_models[path] = (stamp, model)` changes the cache. The shared
model comes from that cache and is copied before it reaches a caller, so
both access points matter during ownership review.

In 5.1.0, `structure/extract.py:Reader.written` recognizes direct attribute
targets and subscript targets whose key is a string constant. An indexed
assignment with a variable key keeps its expression as an assignment
target, but it does not resolve to a write on the containing field. The
map could surface a separate "mutates entries" relationship for indexed
assignments and deletes on a known field. That would keep assignment to
the field itself distinct from a change to one of its members. Calls
such as `move_to_end` can stay ordinary calls unless the receiver and
the method's effect are known.

The same distinction mattered when a task field changed during a focused
test run. `show --last` said that the source had changed on disk after
import and withheld the comparison. That was a useful prompt to rerun
the completed slice with a stable source tree.

## Command identifiers and dynamically dispatched callers

During removal of a library folder command, `show lib_folder` returned
103 word matches. A literal source search located its registry row, its
presentation entry and its availability checks directly. In the export
naming change, `show LibraryStore.export_model_package` also missed the
workflow call through the controller's runtime-injected library object.
By contrast, `show file_safe_name` found the New Project caller we needed
to preserve when moving the shared path helper.

In 5.1.0, `intent/cli.py:show` builds the source map and distinguishes
resolved nodes and agreement anchors from lexical matches.
`structure/extract.py` records call sites when the receiver or callee can
be resolved. Command identifiers used as registry values and dispatch
keys deserve an exact-literal lookup with each site labeled by its use.
An indirect caller can be surfaced as a possible reference with its
unresolved receiver, without counting it as a resolved call or marking
the user's architecture red.

## A checked documentation link during an intake change

Before the data-format contract named the new parser, `show` listed its six
source call sites and said that no text described the file. Adding one
`about` marker next to the CSV dialect rules made the same command show
`docs/data_input/CONTRACT.md:19` while retaining those call sites. This
confirmed both the missing relationship and the correction before the
tests were available to run.

In 5.1.0, `intent/docs.py:module_lines` reads and reports those markers
and supplies the exact missing-marker syntax when an owned file has
none. The immediate source pointer worked well while the documentation
and implementation were being prepared separately.

## An occupied request number during a patch release

The owner supplied a new statement with a requested number already used by an
older approved statement. `req add FILE --id R45` returned `request_exists:
R45 is stored; a correction from the owner is a new request`. In 5.1.0,
`map/requests.py:_store` checks `_identifiers`, which includes protected paths.
Moving the two local files aside did not make the number available. The check
preserved the earlier original while the new text was stored under a distinct
identifier. `req add` and `cmp` confirmed the new bytes, and `show` verified
that an exact quote from the new record was cited by the updated rule.

The refusal could include the current record's path and a suggested available
suffix, or the CLI could expose a non-writing ID availability check. It would
also help to distinguish an existing identical body from a different statement
at the same requested ID. The repository keeps the original record and the
new supplement with traceable references. No replacement of protected bytes
is needed.
