# PEMEL Aging Studio field note

Observed with FlowGuard 5.1.0 on 2026-11-27 during an import admission regression check. The scenario used synthetic inputs and an isolated workspace.

`python -m flowguard show src/pemel_service/calibration/jobs.py:CalibrationJobStore.active` resolved the method and showed its three direct callers: `refuse_mutation`, `ScientificTaskReservation.reserve` and `workspace_activity`. This exposed the shared owner check used by both the UI and the background task before changing its behavior.

The focused UI test session passed 11 tests. `python -m flowguard show --last` reported zero red findings and named four unpaired comparisons. It explicitly reported that no call to `CalibrationJobStore._job_ids` was recorded because the function is a generator. It gave the same generic explanation, “no comparable JSON result”, for `CalibrationJobStore.active`, `ScientificTaskReservation.reserve` and `ScientificTaskReservation._owner`. It also stated that the run selected zero of 57 intent items. Separate app tests asserted actual outcomes for verified exits, live workers and unreadable process identity.

The installed source hashes matched the 5.1.0 checkout. In `flowguard/intent/runtime.py`, the observer creates no comparable sample when a call has a receiver or its inputs cannot be serialized, and it also clears the sample if return serialization fails. `flowguard/intent/plugin.py:Observations.report` derives the same summary line from the missing sample. The explanation could tell readers whether the call had non-comparable inputs or a receiver, or whether encoding the result actually failed. This would help users decide what their explicit tests need to cover. The generator and intent-coverage explanations already give actionable scope. The application regression itself is outside the tool finding.

## Shared storage and portable exports

During the separate path-length repair, `show src/pemel_service/project/store.py` reported the common project store and its calls from Data Library and background tasks. The path report made it apparent that correcting the store would cover imports through both entry points. The report also pointed to the separate native Data and project archive callers, which led to checking their staging depth.

`show --last` reported four document impacts in the broad test run. The `ACCEPTANCE_GUIDE.md:37` entry included the concrete path from the acceptance input generator's `write_cycles` to `DataLibraryStore.export_native`. The guide could keep its existing format and choices after reviewing the call: the temporary layout changed and the exported inputs did not. The other impact paths led to the format and free-space contracts, which were unchanged. Installed FlowGuard 5.1.0's `intent/docs.py` builds these messages from documented locations and the changed direct-call endpoints. This is useful evidence for checking the contract after an internal change.

The same report counted zero red findings and separately named one failing ordinary app test. The failing assertion looked at the export folder before the background reaper completed. Waiting through the existing cleanup API fixed the test, and a focused rerun passed. The warnings about unavailable runtime comparisons were read as coverage information.
