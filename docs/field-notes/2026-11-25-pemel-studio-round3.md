# Field notes: PEMEL Aging Studio, round 3 investigation (FlowGuard 5.1.0)

Date: 2026-11-25. The project is a PySide6 desktop app plus a Python model package; the FlowGuard root is the app folder.

This round was a read-heavy investigation by nine agents: import freeze, CSV, data columns, model structure, example model, UI review, UI prototype, manual and reports, acceptance. The lead then ran `new-task` before a visual redesign.

Each point below was tested against "What it is for". Points marked *checked in source* were traced in the installed 5.1.0 code. The others are observations with their command and output.

## Where it helped

1. **Caller maps before a change.** `show src/pemel_studio/shell/tree_projection.py` (2.8 s) showed that `GROUPS` and the cue rules have exactly one consumer. `show src/pemel_service/data/prescribed.py` (3.0 s) listed every caller (`review.py`, `tasks/runner.py`, `packaging/app/task_probe.py`). Both saved a search.
2. **"described by no text" was actionable.** `show src/pemel_service/data/prescribed.py` reported no about-text. `docs/data_input/CONTRACT.md` does describe that module but carries no `about` marker. A format change would therefore not have flagged the contract, and the agent added the marker to its plan.
3. **`same` anchors found where a change must go.**
   - `show MODEL_TITLE` found `same MODEL_TITLE ref` at the display-name owner. The "no revision for the supplied model" change was planned on the ref only.
   - `show RUNTIME_LITERAL` found the generator/engine literal agreement that a restructure must keep.
   - `show MODEL_VALUE` linked the value agreement to its rule and pinning test.
4. **`new-task` named the stale baseline clearly:** "baseline 08767c004df9; new task from HEAD (was 2256acb53f51, 75 commits before HEAD: those changes are no longer compared; compare them once with python -m pytest --flowguard-base 2256acb53f51)".

## Where it fell short of its own purpose

1. **"(holds)" reads as "the rule is satisfied", and an uncited rule gets no note.** *Checked in source.*
   - Command: `python -m flowguard show rule.readable-model-code`.
   - Output: `source: R8 "…直接可以阅读的，然后该有的注释…" (holds)`, and no `cited by` line.
   - In 5.1.0, `intent/cli.py` `_holds()` and line 655 print "(holds)" when `catalog_authority` accepts the quoted source. Line 657 prints `cited by` lines only when some exist, so nothing at all is printed for an uncited rule.
   - The product broke this rule: the shipped model code had 0 comments, because a generator strips them. Four agents read "(holds)" as "this rule is met".
   - Suggestion: print "(source holds)" for this check, and print "not cited by any intent rule" when `cited.get(rule.id)` is empty. Only 7 of the 50 rules here are cited.
2. **Copies of one judgment in literal tables or string keys are not found.** *Observed.*
   - The data-column vocabulary (names and units) sits in at least 8 literal tables: `prescribed.py:36-43`, `help_content.py:255-280`, `display_text.py:288-296`, `explorer.py:36-50`, `template_kit.py:45`, `model_source.py:499`, `make_acceptance_inputs.py:43-51` and `model_execution_v1.py:22`. The file-suffix rule exists in 5 code places and 3 catalogue strings. The module-status vocabulary has 5 copies.
   - `check --static --all` lists none of them, and none is marked `same`. Within its purpose, FlowGuard can only check marked copies, so the gap is discovery: no hint pointed at these duplicated literal tables.
3. **A rename of string keys is not actionable through `show`.** *Observed.*
   - `show i_A_cm2` returned symbol and alias matches plus "50 lines that only share a word".
   - It returned none of the roughly 1,000 uses of the key as a string (`columns["i_A_cm2"]`). `grep` was needed.
4. **Writers missed for assignments on deep-copied values.** *Observed.* `show MeasuredData.stack` listed readers but no writer. Four places assign it (`review.py:128`, `review.py:340`, `parts.py:178`, `input_identity.py:41`), on deep-copied or call-returned objects. A `writers` agreement for that field could not be checked this way.
5. **Free-text `show` ranks re-export aliases above decisions.** *Observed.* In each of these the first 30–40 lines were import aliases and re-exports, and the agent could not act on the output:
   - `show "export file name"` returned alias lines, not `workflows/exports.py:30-39`;
   - `show "supplied model"` printed 573 lines;
   - `show "code identity"` printed 24 name matches;
   - `show "which suffix is a data file"` returned more than 30 lines.
6. **A rule's text is wider than its executable part, and `show` does not say so.** *Observed.* `rule.nirr-k4` says "k4 is the Dataset B value", but its intent table `SUPPLIED_FIXED_NUMBERS` has no k4 row. A k4 change gives no red and no changed line, and `show rule.nirr-k4` does not say that only part of the rule is executable.
7. **No marker is possible in byte-frozen files.** *Observed.* `model_execution_v1.py` is part of a code-identity hash, so an agreement there can only be bound by a test, not by a `same` comment. A sidecar marker would help. This is a fit-to-real-work note.
8. **A short request stored without its offer.** *Observed in the archive.* R37 was stored as the bare word "同意" (agreed) without `--offer`, so the archive cannot show what was agreed. `req add` could warn when a stored text is very short and no offer is given.

## What it cost

- `show`: 0.8–5.7 s.
- `check --static --all`: 4.8–28 s; the stale baseline added 37 impact and 5 "loosened" lines.
- The pytest block: 11 s on small runs, and 180 s on a 532-test run with the stale baseline. It printed `0 red, 1 before, 1 known, 37 impact, 5 loosened, 199 not compared`.
- `map.sqlite`: 94–109 MB.
- Noise: before the lead's `new-task`, every agent's block reprinted the same 42 lines from earlier rounds. One agent reported them as "named in your report" items although its task had not caused them. After `new-task` this noise is gone.
