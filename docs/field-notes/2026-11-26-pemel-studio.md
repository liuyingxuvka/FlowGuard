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
