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

## Calibrating a narrow numerical rule in a larger module

The calibration-range change introduced a scalar function that returns the
amount below and above two inclusive limits. Its independent intent table
provided three literal cases. The first focused run passed the ordinary
assertions, while the FlowGuard rows and cells both reported `not compared`.
`show --last` traced the refusal to the imported module's initialization,
including NumPy, contextual data classes and unrelated imported modules.

The same production function was then marked `calibrated_by` with a named
pytest case that calls it directly with real values. The combined interface
suite reported 309 passing tests and no unverified intent tests. The public
input-route follow-up reported 27 passing tests. Both blocks reported zero
red. The rule's expected results remained independent of the production
calculation. The change used the design of `intent/calibration.py`, which
obtains its observation inside the actual test session.

The distinction between a comparison refusal and a failing agreement is
useful. The explanation would be easier to use if it showed the closest
blocking import or initializer first, then grouped transitive blockers under
an expandable command. The initial message for this single decision listed
several dozen transitive dependencies. A direct suggestion to use a named
real test for an otherwise suitable scalar edge would make the next action
clear sooner.

## Request originals first added by a merge

A normal merge resolved two branches that had used the same request
identifier for different owner statements. Both bodies were kept. The older
body was registered with `req add` under a new identifier, checked with
`cmp`, and first committed as part of the merge.

`git log --format=%H --diff-filter=A --reverse -- <request-file>` returned
no commit for the new body and sidecar. The same path query with
`--full-history` showed the merge. FlowGuard 5.1.0 uses the first query in
`map/records.py:_first_blob`. `_stored_digest` can use the original local
write receipt, so the author checkout verifies the record. A fresh checkout
has neither that receipt nor a result from `_first_blob`. The committed
content on its own cannot serve as the original.

Before pushing, the byte-identical record was put in an ordinary commit and
the merge was recreated. The first-add query then returned the ordinary
commit for both files. Checks of all seven affected body and sidecar pairs
matched their first additions exactly. The branch content remained identical.

An explicit diagnostic for originals introduced in a merge would have made
the problem visible before the push. Any history change here needs to identify
the merge's actual first write without learning an original digest from the
working copy or silently choosing between two different parent originals.

An earlier, locally retired duplicate also used an identifier that the incoming
branch legitimately stored for different words. Its temporary files were never
committed. After the merge, `req list` still marked the legitimate incoming
record `retired` in the original checkout. The incoming body and sidecar both
matched their first committed blobs. Moving the worktree without changing its
tree or the saved receipt made `req list` report the same record as `stored`.

`map/records.py:protected_paths` finds original-write receipts by their
absolute paths. `map/requests.py:_owner_row` treats a matching retirement ID
as retired even when the state of that retirement is missing. The strong
receipt remains useful for the deleted temporary files in the original
checkout. The listing could show the missing or conflicting retirement
separately from the intact incoming request, using the original body digest to
identify which record it concerns.

## First-write provenance recovered without changing the branch tree

A later integration again placed three preserved request names in a merge
only. The local `req list` displayed `stored` for each, while the same
path-limited `git log --format=%H --diff-filter=A --reverse -- <path>` used
by `map/records.py:_first_blob` returned no addition for the six body and
sidecar files. In this case the merge had already been pushed.

An ordinary commit on the incoming branch's base recorded the six original
blobs. A new merge used that ordinary commit as its first parent and kept the
published integration as its second parent. `git merge-tree` produced the
same tree as the published integration. The delivery branch moved by fast
forward. The normal path-limited query then returned the ordinary commit for
all six files. Checking every stored request body and sidecar against its
first returned commit found no byte differences. No source or file byte was
changed by the recovery.

The command output makes the distinction between local receipt protection and
portable Git provenance important. `req list` could state the evidence source
for stored originals, or provide a portability view with separate counts for
Git history and local first-write receipts. `map/records.py:_stored_digest`
already selects between them and raises `Unverifiable` when neither exists.

## A field's import reach and a worker's actual delivery

After fixing delivery of a rendered result from a worker to the GUI thread,
78 focused tests passed. The FlowGuard block named a single new field writer
and directed us to `show FigureRenderTask._results`. That view correctly
located the initialization and both reader methods. It let the reviewer
check the two consumers against the delivery test, without searching other
queued Qt callbacks.

The default output then listed many tests as "reaches a writer". Some named
unrelated UI journeys. The output ended with 503 more lines, with 298 of
those matching only a word. In 5.1.0 `intent/owners.py:field_lines` passes
source filenames to `graph._tests_for`, so these links describe test-file
import reach. The command does not know whether a test executed the write or
exercised result delivery. Labelling the rows as import reach would preserve
the useful impact hint and avoid reading the list as field-level execution
coverage. A compact field-only view could leave the import candidates for
`--full`.

The same view marked `packaging/app/test_packaging.py` as "left out of the
test scope". Default pytest discovery really excludes the file because
`testpaths` is `tests`. Both the source quality and native-package workflows
explicitly pass that filename to pytest, and the latest source run passed
3,267 tests with that command. `intent/cli.py:_test_marks` computes the mark
from `deps.test_scope`. The narrower wording "outside default pytest
discovery" would describe that fact accurately; explicit invocation in a
workflow is separate evidence. This distinction matters when deciding which
checks a delivery candidate actually ran.

## Exact symbol queries fill the first screen with partial import matches

`python -m flowguard show render_manual` resolved the manual renderer and
named its only resolved caller, `build_manuals`. It then filled the first
screen with import bindings such as `render_message` and `render_ui_text`,
ending with 55 more lines. The exact-site query
`python -m flowguard show tools/model_manual/build_manual.py:render_manual`
returned the same renderer and caller in four lines. This made it easier to
place a shared documentation change before editing either renderer.

`python -m flowguard show ModelPartStatus` produced a larger example. It
found the class, then showed bindings such as `ModelBundle`, `model_number`
and `runtime_literal` above the truncation notice. The notice counted 673
additional lines, including 507 that the view identified as word matches.

The installed 5.1.0 source matched the checked source bytes for both files.
`structure/api.py:import_aliases` deliberately returns bindings whose names
share any query token. `intent/cli.py:show` then ranks every returned alias
at 1000, so those partial import matches appear on the exact-name side of
the cutoff and are omitted from the word-match count. Give a binding exact
rank when its imported name or resolved target actually matches the query.
Group the remaining import candidates with the word matches under `--full`.
Keep the exact-site result, and retain lexical candidates for open-ended
queries that have no exact symbol.

## An empty historical signature interrupts `show` after a source move

During a source-only move of the calibration declarations, an exact
`show` query for `runtime_backend_identity` identified its three callers.
It exposed both the setup path and the detached worker's identity check,
which helped preserve the same admission gates during the move.

In an isolated copy with the original task baseline, after applying the
move, `python -m flowguard show src/pemel_service/calibration/parts.py:read_runtime_contract`
printed the new two-root signature and its single caller and then returned
exit 2 with `flowguard: max() iterable argument is empty`. A second CLI call
reproduced the result. The corresponding backend query completed normally.
No application, test or model ran during the reproduction.

The installed 5.1.0 files match the reviewed source. `intent/cli.py:show`
calls `structure/api.py:search_homes`, which forwards reconstructed old
site groups to `structure/homes.py:site_homes`. The observed groups had
signature counts `[1, 2, 0, 5, 4]`. The existing `if not groups` accepts
the list, and `best_of` then calls `max` on the empty third group's
signatures. Filter tokenless groups before scoring and use the existing
empty-list result if no groups remain. Cover both mixed and all-empty
historical groups. Mixed groups should still report any genuine former
decision site.

## The fallback ledger caught broad Qt test handlers during a migration

The first focused stack-input run on an isolated checkout reported 103
passing tests and one fixture failure. FlowGuard separately reported 27
red findings. Two new Qt test callbacks caught `BaseException` and
`Exception`. The ledger classified them as forms that cannot be registered.
This prompted a source correction. The tests retain their explicit dialog
and timeout checks and let pytest-qt capture unexpected callback exceptions.

The report also emitted separate “Code disappeared” and “New unregistered
fallback” findings for handlers moved into named model-store and import
methods. `intent/ledger.py:evaluate` compares the exact keys from `found`
and `entries` and requires a rule quote for each nonlegacy entry. A paired
migration hint for handlers with matching normalized code would reduce the
work reviewing a move. Keep the move visible as a proposal and recheck the
actual handler and rule source before changing the ledger.

For a parallel review, `python -m flowguard ledger check --help` offered
no candidate input. `intent/cli.py:_ledger_result` reads the configured
project ledger directly. We verified the draft by directing the installed
evaluator's ledger input to a scratch file while preserving the original
source map and baseline. A read-only `--candidate-ledger` option would make
that check available without modifying the shared tree or the baseline.
The same rule-quote and broad-handler checks must apply to the candidate.

## Intent-file collection and named scope are easy to confuse

During the synthetic CSV and HDF5 verification, an ordinary pytest
witness beside its declarations under `tests/intent/` did not run. The
four declarative cases existed, but the witness had to move to
`tests/tools/` to exercise both files for each case. In the installed
5.1.0 source, `intent/plugin.py:pytest_pycollect_makemodule` hands every
Python module in the configured intent directory to `IntentFile`.
`IntentFile.collect` then yields the declared intent items. Add a precise
collection message when such a file also defines a `test_*` function that
ordinary pytest would otherwise collect. Include the path and explain
where to put the ordinary test. This would make an absent witness visible
even when the declaration items run successfully.

An ordinary test in `tests/tools/` subsequently fed a fabricated failing
receipt to the release-verdict helper. Its Python assertions passed, but
FlowGuard reported two conflicts with the shipped-case rule. The rule's
`calibrated_by` test genuinely checked the release files. In the same
plugin, `_rule_calls` filters the named witness, while `_rule_signals`
can check all observed calls when the dedicated field items did not cover
the anchor. The detailed red output printed both conflicting inputs and
made the test scope error diagnosable. The negative test now exercises the
public ZIP verifier with an actual missing CSV or HDF5 member. This keeps
the strict release rule and verifies that incomplete input is refused.
Document the distinction between a named witness and the wider live
comparison beside `calibrated_by`, and show it in a detailed rule finding
when the conflicting call came from another test.

The complete archive test later called the same verdict helper four times,
once per real case. Its ordinary assertions passed, while the rule's
`[cells]` and `[rows]` items were unverified. The receipt said the target
"may be absent or ambiguous". The installed `intent/calibration.py:_recorded`
uses that wording for both zero calls and multiple calls. Give the observed
count and the exact named witness in each finding. For multiple calls,
suggest retaining the complete workflow test with a separate named witness
that reaches the verdict helper once. A precise count would distinguish a
missing test from a test of the whole workflow.

## An owner's small numerical exception kept its provenance

The owner approved the discrepancy reproduced in one Windows synthetic
case. `printf '%s' … | python -m flowguard req add - --id R51` archived
132 UTF-8 bytes with the digest prefix `1fae8d2f7d21`. A byte comparison with
the input passed. `show R51` displayed the actual reply and the exact-quote
source of the new narrow rule passed `show rules`. The general release
verification requirement retained its earlier owner source.

The installed code matched the reviewed `intent/cli.py` and
`map/requests.py` files. `_input_bytes` preserves the pipe bytes and
`store_request` adds a first-write identity. The offset test separately
encodes the original model, platform, phase and candidate. The archive and
the passing quote check give the reason for the exception; the exact
Windows release check is the evidence that it applies as intended.

## Static checks and task payload fields

During a data-import format change, `python -m flowguard check --static
--all` reported 0 red, 1 before, 2 known and 22 impact in 6.4 seconds.
`show revise_scan_review` located the consumer and its task-runner caller.
Following the command from the UI exposed a contract mismatch that these
checks had not reported. The scan edit still sent the retired `mode` key.
The task received it and rejected the request whenever that key was
present. The same stale command still offered the former stack-facts editor.
This finding came from the two source branches, before a new UI test ran.
The ordinary regression should click Edit Scans and complete the task.

The installed 5.1.0 `structure/extract.py` matches the reviewed checkout.
The Python reader's `visit_Compare` records membership labels for literal
containers and its label extraction deliberately leaves out mapping keys
and `key in mapping` tests. The ordinary field map follows typed attribute
paths. A dynamically routed `dict[str, Any]` task can therefore need a
separate, explicitly named contract on allowed and removed fields.

A useful next step would be an opt-in view of task message producers and
consumers anchored to the same literal command, including retired keys
that a reachable producer still sends. Mark producers with unresolved
`**values` as such. A simpler starting point is to say in `show` when a
resolved caller hands off an untracked task payload, so the reviewer knows
which UI-to-worker route needs a real test. Keep routine mapping-key noise
out of the default static check.

## The enum boundary needs a clear rule-specific failure

A small text-size rule declared the literal domain `(14,)` and applied
arithmetic directly to its argument. In the focused Studio regression,
FlowGuard evaluated this rule with `value='<other>'`. The arithmetic
raised `TypeError`. The run ended with a session-level red line that called
this a FlowGuard internal error. `python -m flowguard show --last` retained
the full trace. It pointed to the product-side predicate and made the input
that caused the failure visible.

The installed 5.1.0 copies of `intent/cells.py`, `intent/engine.py` and
`intent/plugin.py` match this feedback branch byte for byte. The cells
module deliberately adds an outside representative for enum fields.
`eval_rule` calls it a predicate error and includes the rule and cell.
`finish_verified` catches it during contract aggregation and labels it a
session internal error. The guard against a passing session is valuable.

Show this case as a rule authoring failure under the rule owner, with the
declared domain and the auto-generated representative. Explain that a
predicate for a single literal can return `None` elsewhere. Keep the
nonzero exit and the detailed trace. Where possible, preserve receipts for
unrelated rules that already finished, with a clear indication that the
overall check failed.
