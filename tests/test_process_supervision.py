from __future__ import annotations

import inspect
import ctypes
from ctypes import wintypes
import json
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path
import flowguard.process_supervision as supervision

import flowguard.validation_ownership as ownership
from flowguard.process_supervision import (
    SupervisedCommandResult,
    _confirmed_windows_process_ids,
    _descendant_process_ids,
    run_supervised,
    run_supervised_bytes,
    write_terminal_artifact,
)


class ProcessSupervisionTests(unittest.TestCase):
    @staticmethod
    def _instances(identities, *, owned=None, parents=None, actual_parents=None):
        parent_rows = dict(parents or {})
        class Instances:
            owned_creation_times = dict(owned or {7: 100})
            parents = parent_rows

            def __init__(self):
                self.admitted = []
                self.discarded = []
                self.queried = []

            def identity(self, pid):
                self.queried.append(pid)
                value = identities[pid]
                if isinstance(value, list):
                    return value.pop(0) if len(value) > 1 else value[0]
                return value

            def admit(self, pid, parent, executable, creation):
                self.admitted.append(pid)
                self.owned_creation_times[pid] = creation
                self.parents[pid] = (parent, executable)

            def discard(self, pid):
                self.discarded.append(pid)

            def parent_process_id(self, pid):
                return (actual_parents or {}).get(pid, 7 if pid == 8 else 8)

        return Instances()

    def test_reused_parent_never_grants_ownership_to_foreign_child(self) -> None:
        instances = self._instances(
            {7: (100, "gone"), 8: (210, "ok"), 9: (220, "ok")},
            owned={7: 100, 8: 110}, parents={8: (7, "launcher.exe")},
        )
        result = supervision._identity_bound_windows_tree(7, {9: 8}, {9: "foreign.exe"}, instances, creation_by_pid={9: 220})
        self.assertEqual({}, result)
        self.assertEqual([], instances.admitted)
        self.assertNotIn(9, instances.queried)
        # Adoption consumes this exact authenticated snapshot, so a foreign
        # child is neither assigned to the job nor included in termination.
        with mock.patch.object(supervision, "_windows_process_tree_snapshot", return_value=result):
            job = mock.Mock()
            self.assertEqual({}, supervision._adopt_windows_launch_descendants(
                job, 7, instances=instances, observation_seconds=0
            ))
            job.assign_process_id.assert_not_called()
        self.assertEqual((), _confirmed_windows_process_ids(result, instances.owned_creation_times))

    def test_old_child_of_reused_root_pid_is_not_owned(self) -> None:
        # A protected foreign process may deny OpenProcess. A coherent older
        # birth excludes it before that query, including its foreign children.
        instances = self._instances({7: (100, "gone"), 8: (None, "unknown"), 9: (None, "unknown")})
        self.assertEqual({}, supervision._identity_bound_windows_tree(
            7, {8: 7, 9: 8}, {8: "old.exe", 9: "old-child.exe"}, instances,
            creation_by_pid={8: 90, 9: 95},
        ))
        self.assertEqual([], instances.admitted)
        self.assertNotIn(8, instances.queried)
        self.assertNotIn(9, instances.queried)

    def test_child_replaced_between_table_and_handle_is_not_admitted(self) -> None:
        instances = self._instances(
            {7: (100, "gone"), 8: (210, "ok"), 9: (220, "ok")},
            actual_parents={8: 999},
        )
        self.assertEqual({}, supervision._identity_bound_windows_tree(
            7, {8: 7, 9: 8}, {8: "foreign.exe", 9: "foreign-child.exe"}, instances,
            creation_by_pid={8: 210, 9: 220},
        ))
        self.assertEqual([], instances.admitted)
        self.assertEqual([8], instances.discarded)
        self.assertNotIn(9, instances.queried)

    def test_unknown_same_handle_child_parent_blocks(self) -> None:
        instances = self._instances({7: (100, "gone"), 8: (110, "ok")}, actual_parents={8: None})
        self.assertIsNone(supervision._identity_bound_windows_tree(7, {8: 7}, {8: "child.exe"}, instances, creation_by_pid={8: 110}))
        self.assertEqual([], instances.admitted)
        # A newer protected/unknown child, a missing birth, and a snapshot /
        # retained-handle mismatch must each remain unknown, never empty.
        cases = (({}, (110, "ok")), ({8: 0}, (110, "ok")), ({8: True}, (110, "ok")),
                 ({8: 110}, (None, "unknown")), ({8: 110}, (111, "ok")),
                 ({8: 110}, (None, "gone")))
        for births, identity in cases:
            with self.subTest(births=births, identity=identity):
                instances = self._instances({7: (100, "gone"), 8: identity})
                self.assertIsNone(supervision._identity_bound_windows_tree(
                    7, {8: 7, 9: 8}, {8: "child.exe"}, instances,
                    creation_by_pid=births,
                ))
                self.assertEqual([], instances.admitted)

    def test_retained_gone_parent_authenticates_actual_live_orphan(self) -> None:
        instances = self._instances(
            {7: (100, "gone"), 8: (110, "gone"), 9: (120, "ok")},
            owned={7: 100, 8: 110}, parents={8: (7, "launcher.exe")},
        )
        result = supervision._identity_bound_windows_tree(7, {9: 8}, {9: "orphan.exe"}, instances, creation_by_pid={9: 120})
        self.assertEqual({9: (8, "orphan.exe", 120)}, result)
        self.assertEqual([9], instances.admitted)

    def test_unknown_parent_identity_blocks_without_adopting_child(self) -> None:
        instances = self._instances({7: (None, "unknown"), 8: (120, "ok")})
        self.assertIsNone(supervision._identity_bound_windows_tree(7, {8: 7}, {8: "child.exe"}, instances, creation_by_pid={8: 120}))
        self.assertEqual([], instances.admitted)
        self.assertNotIn(8, instances.queried)

    def test_reused_child_does_not_authenticate_foreign_grandchild(self) -> None:
        instances = self._instances(
            {7: (100, "gone"), 8: (210, "ok"), 9: (220, "ok")},
            owned={7: 100, 8: 110}, parents={8: (7, "launcher.exe")},
        )
        self.assertEqual({}, supervision._identity_bound_windows_tree(
            7, {8: 7, 9: 8}, {8: "other.exe", 9: "foreign.exe"}, instances,
            creation_by_pid={8: 210, 9: 220},
        ))
        self.assertEqual([], instances.admitted)
        self.assertNotIn(9, instances.queried)

    def test_immediate_same_handle_decision_drops_already_exited_child(self) -> None:
        instances = self._instances({7: (100, "gone"), 8: [(110, "ok"), (110, "ok"), (110, "gone")]})
        with mock.patch.object(supervision.time, "sleep") as sleep:
            result = supervision._identity_bound_windows_tree(7, {8: 7}, {8: "child.exe"}, instances, creation_by_pid={8: 110})
        self.assertEqual({}, result)
        sleep.assert_not_called()

    def test_live_owned_child_stays_blocking_at_immediate_decision(self) -> None:
        instances = self._instances({7: (100, "gone"), 8: (110, "ok")})
        with mock.patch.object(supervision.time, "sleep") as sleep:
            result = supervision._identity_bound_windows_tree(7, {8: 7}, {8: "child.exe"}, instances, creation_by_pid={8: 110})
        self.assertEqual({8: (7, "child.exe", 110)}, result)
        sleep.assert_not_called()

    @unittest.skipUnless(supervision.os.name == "nt", "Windows retained process handles")
    def test_retained_instance_handle_keeps_birth_after_process_exit(self) -> None:
        process = supervision.subprocess.Popen((sys.executable, "-c", "pass"))
        instances = supervision._WindowsProcessInstances(process)
        try:
            birth = instances.owned_creation_times[process.pid]
            snapshot = supervision._windows_system_process_snapshot()
            self.assertIsNotNone(snapshot)
            self_birth, self_status = supervision._windows_process_creation_time(supervision.os.getpid())
            self.assertEqual("ok", self_status)
            self.assertEqual(self_birth, snapshot[supervision.os.getpid()][2])
            if process.pid in snapshot:
                self.assertEqual(birth, snapshot[process.pid][2])
            self.assertEqual(supervision.os.getpid(), instances.parent_process_id(process.pid))
            process.wait(timeout=5)
            self.assertEqual((birth, "gone"), instances.identity(process.pid))
            self.assertEqual(supervision.os.getpid(), instances.parent_process_id(process.pid))
        finally:
            instances.close()

    def test_terminal_unknown_reobserves_same_episode_without_launching(self) -> None:
        process = mock.Mock(pid=77)
        process.poll.return_value = 0
        with mock.patch.object(supervision, "_contained_process_ids", side_effect=[(77,), ()]), mock.patch.object(
            supervision, "_windows_process_tree_observation", side_effect=[None, {}]
        ), mock.patch.object(supervision.subprocess, "Popen") as launch:
            observed = supervision._terminal_process_tree_observation(
                mock.Mock(), None, process, (88,), observation_seconds=0.05
            )
        self.assertEqual(((), {}, False), observed)
        launch.assert_not_called()

    def test_terminal_persistent_unknown_remains_unknown(self) -> None:
        process = mock.Mock(pid=77)
        process.poll.return_value = 0
        with mock.patch.object(supervision, "_contained_process_ids", return_value=()), mock.patch.object(
            supervision, "_windows_process_tree_observation", return_value=None
        ), mock.patch.object(supervision.subprocess, "Popen") as launch:
            observed = supervision._terminal_process_tree_observation(
                mock.Mock(), None, process, (), observation_seconds=0.01
            )
        self.assertEqual(((), None, False), observed)
        launch.assert_not_called()

    def test_terminal_persistent_unknown_job_never_becomes_known(self) -> None:
        process = mock.Mock(pid=77)
        process.poll.return_value = 0
        with mock.patch.object(supervision, "_contained_process_ids", return_value=None), mock.patch.object(
            supervision, "_windows_process_tree_observation", return_value={}
        ):
            observed = supervision._terminal_process_tree_observation(
                mock.Mock(), None, process, (), observation_seconds=0.01
            )
        self.assertEqual((None, {}, False), observed)

    def test_terminal_known_live_descendant_is_never_retried_away(self) -> None:
        process = mock.Mock(pid=77)
        process.poll.return_value = 0
        snapshot = {88: (77, "git.exe", 123)}
        with mock.patch.object(supervision, "_contained_process_ids", side_effect=[(88,), ()]) as contained, mock.patch.object(
            supervision, "_windows_process_tree_observation", side_effect=[snapshot, {}]
        ):
            observed = supervision._terminal_process_tree_observation(
                mock.Mock(), None, process, (88,), observation_seconds=0.05
            )
        self.assertEqual(((88,), snapshot, False), observed)
        self.assertEqual(1, contained.call_count)

    def test_terminal_known_running_root_is_never_retried_away(self) -> None:
        process = mock.Mock(pid=77)
        process.poll.return_value = None
        with mock.patch.object(supervision, "_contained_process_ids", return_value=()), mock.patch.object(
            supervision, "_windows_process_tree_observation", return_value={}
        ):
            observed = supervision._terminal_process_tree_observation(
                mock.Mock(), None, process, (), observation_seconds=0.05
            )
        self.assertEqual(((), {}, True), observed)

    def test_process_times_confirmed_exit_is_gone_not_a_live_identity(self) -> None:
        kernel = mock.Mock()
        kernel.WaitForSingleObject.return_value = 0x102
        def times(_handle, creation, exit_time, _kernel_time, _user_time):
            ctypes.cast(creation, ctypes.POINTER(wintypes.FILETIME)).contents.dwLowDateTime = 123
            ctypes.cast(exit_time, ctypes.POINTER(wintypes.FILETIME)).contents.dwLowDateTime = 456
            return True
        kernel.GetProcessTimes.side_effect = times
        self.assertEqual((None, "gone"), supervision._windows_process_creation_time_from_handle(kernel, 1))

    def test_process_times_failed_query_remains_unknown(self) -> None:
        kernel = mock.Mock()
        kernel.WaitForSingleObject.return_value = 0x102
        kernel.GetProcessTimes.return_value = False
        with mock.patch.object(supervision.ctypes, "get_last_error", return_value=5, create=True):
            self.assertEqual((None, "unknown"), supervision._windows_process_creation_time_from_handle(kernel, 1))

    def test_signaled_process_with_retained_zero_exit_time_is_gone(self) -> None:
        kernel = mock.Mock()
        kernel.WaitForSingleObject.return_value = 0
        # A retained Toolhelp/process object is not a live child, including
        # the interval when timestamp output would still look unexited.
        self.assertEqual((None, "gone"), supervision._windows_process_creation_time_from_handle(kernel, 1))
        kernel.GetProcessTimes.assert_not_called()

    def test_process_exiting_during_identity_query_is_gone(self) -> None:
        kernel = mock.Mock()
        kernel.WaitForSingleObject.side_effect = [0x102, 0]
        def times(_handle, creation, _exit, _kernel, _user):
            ctypes.cast(creation, ctypes.POINTER(wintypes.FILETIME)).contents.dwLowDateTime = 123
            return True
        kernel.GetProcessTimes.side_effect = times
        self.assertEqual((None, "gone"), supervision._windows_process_creation_time_from_handle(kernel, 1))

    def test_only_unsignaled_process_keeps_creation_identity(self) -> None:
        kernel = mock.Mock()
        kernel.WaitForSingleObject.return_value = 0x102
        def times(_handle, creation, _exit, _kernel, _user):
            ctypes.cast(creation, ctypes.POINTER(wintypes.FILETIME)).contents.dwLowDateTime = 123
            return True
        kernel.GetProcessTimes.side_effect = times
        self.assertEqual((123, "ok"), supervision._windows_process_creation_time_from_handle(kernel, 1))

    def test_unknown_kernel_wait_remains_unknown(self) -> None:
        for status in (0xffffffff, 0x80):
            with self.subTest(status=status):
                kernel = mock.Mock()
                kernel.WaitForSingleObject.return_value = status
                self.assertEqual((None, "unknown"), supervision._windows_process_creation_time_from_handle(kernel, 1))

    def test_windows_termination_waits_on_verified_handle_before_close(self) -> None:
        kernel = mock.Mock()
        events = []
        clock = [100.0]

        def open_process(access, inherit, pid):
            self.assertEqual(0x0001 | 0x1000 | 0x00100000, access)
            self.assertFalse(inherit)
            events.append(("open", pid + 1000))
            return pid + 1000

        def identity(_kernel, handle):
            self.assertIs(kernel, _kernel)
            events.append(("identity", handle))
            return (123, "ok")

        def terminate(handle, exit_code):
            self.assertEqual(1, exit_code)
            events.append(("terminate", handle))
            return True

        def wait(handle, milliseconds):
            events.append(("wait", handle, milliseconds))
            clock[0] = 101.0
            return 0

        kernel.OpenProcess.side_effect = open_process
        kernel.TerminateProcess.side_effect = terminate
        kernel.WaitForSingleObject.side_effect = wait
        kernel.CloseHandle.side_effect = lambda handle: events.append(("close", handle))
        with mock.patch.object(supervision.os, "name", "nt"), mock.patch.object(
            supervision.ctypes, "WinDLL", return_value=kernel, create=True
        ), mock.patch.object(
            supervision, "_windows_process_creation_time_from_handle", side_effect=identity
        ), mock.patch.object(supervision.time, "monotonic", side_effect=lambda: clock[0]):
            supervision._terminate_windows_process_ids(
                (8, 7, 7), cleanup_deadline=101.0,
                expected_creation_times={7: 123, 8: 123},
            )
        self.assertEqual([
            ("open", 1007), ("identity", 1007), ("terminate", 1007),
            ("wait", 1007, 1000), ("close", 1007),
            ("open", 1008), ("identity", 1008), ("terminate", 1008),
            ("wait", 1008, 0), ("close", 1008),
        ], events)

    def test_windows_termination_never_kills_or_waits_wrong_birth(self) -> None:
        cases = (
            ("missing", {}, 42, (123, "ok"), True),
            ("mismatched", {7: 123}, 42, (124, "ok"), True),
            ("unknown", {7: 123}, 42, (None, "unknown"), True),
            ("gone", {7: 123}, 42, (123, "gone"), True),
            ("denied", {7: 123}, 0, (123, "ok"), True),
            ("termination_failed", {7: 123}, 42, (123, "ok"), False),
        )
        for name, expected, handle, identity, terminated in cases:
            with self.subTest(case=name):
                kernel = mock.Mock()
                kernel.OpenProcess.return_value = handle
                kernel.TerminateProcess.return_value = terminated
                with mock.patch.object(supervision.os, "name", "nt"), mock.patch.object(
                    supervision.ctypes, "WinDLL", return_value=kernel, create=True
                ), mock.patch.object(
                    supervision, "_windows_process_creation_time_from_handle", return_value=identity
                ) as query:
                    supervision._terminate_windows_process_ids(
                        (7,), cleanup_deadline=10.0, expected_creation_times=expected,
                    )
                kernel.WaitForSingleObject.assert_not_called()
                if name == "termination_failed":
                    kernel.TerminateProcess.assert_called_once_with(42, 1)
                else:
                    kernel.TerminateProcess.assert_not_called()
                if not expected:
                    kernel.OpenProcess.assert_not_called()
                    query.assert_not_called()
                elif not handle:
                    query.assert_not_called()
                else:
                    query.assert_called_once_with(kernel, handle)
                if expected and handle:
                    kernel.CloseHandle.assert_called_once_with(handle)
                else:
                    kernel.CloseHandle.assert_not_called()

    def test_windows_termination_timeout_or_unknown_never_confirms_cleanup(self) -> None:
        for wait_status in (0x102, 0xffffffff):
            with self.subTest(wait_status=wait_status):
                kernel = mock.Mock()
                kernel.OpenProcess.return_value = 42
                kernel.TerminateProcess.return_value = True
                kernel.WaitForSingleObject.return_value = wait_status
                with mock.patch.object(supervision.os, "name", "nt"), mock.patch.object(
                    supervision.ctypes, "WinDLL", return_value=kernel, create=True
                ), mock.patch.object(
                    supervision, "_windows_process_creation_time_from_handle", return_value=(123, "ok")
                ), mock.patch.object(supervision.time, "monotonic", return_value=9.0):
                    self.assertIsNone(supervision._terminate_windows_process_ids(
                        (7,), cleanup_deadline=10.0, expected_creation_times={7: 123},
                    ))
                kernel.TerminateProcess.assert_called_once_with(42, 1)
                kernel.WaitForSingleObject.assert_called_once_with(42, 1000)
                kernel.CloseHandle.assert_called_once_with(42)
                # A termination request or completed wait never replaces either
                # final observation. Exercise the real terminal verdict with an
                # exited root and each remaining blocking observation.
                for final_observation in (((88,), {}, False), ((), None, False)):
                    with self.subTest(final_observation=final_observation), mock.patch.object(
                        supervision, "_terminal_process_tree_observation", return_value=final_observation
                    ):
                        result = run_supervised(
                            (sys.executable, "-c", "pass"), cwd=Path.cwd(), timeout_seconds=5,
                        )
                    self.assertEqual(0, result.exit_code, result.to_dict())
                    self.assertFalse(result.cleanup_confirmed, result.to_dict())
                    self.assertFalse(result.ok, result.to_dict())
                    self.assertEqual("cleanup_unconfirmed", result.terminal_reason)
                    if final_observation[0]:
                        self.assertEqual((88,), result.descendant_process_ids)
                    else:
                        self.assertFalse(result.containment_query_succeeded)

    def test_windows_cleanup_cleans_late_authenticated_child_once_with_shared_deadline(self) -> None:
        expected = {7: 123}
        observed = {7}
        clock = [10.0]
        calls = []
        late = {8: (7, "python3.12.exe", 124)}

        def record(snapshot):
            expected.update({pid: row[2] for pid, row in snapshot.items()})
            observed.update(snapshot)

        def terminate(pids, *, expected_creation_times, cleanup_deadline):
            self.assertEqual(11.0, cleanup_deadline)
            self.assertIs(expected, expected_creation_times)
            calls.append((tuple(pids), dict(expected_creation_times)))
            clock[0] += 0.25

        instance = mock.Mock()
        with mock.patch.object(supervision.os, "name", "nt"), mock.patch.object(
            supervision.time, "monotonic", side_effect=lambda: clock[0]
        ), mock.patch.object(
            supervision, "_windows_process_tree_observation", side_effect=[late, {}]
        ) as query, mock.patch.object(
            supervision, "_terminate_windows_process_ids", side_effect=terminate
        ):
            supervision._clean_windows_observed_descendants(
                (7,), root_process_id=6, observed_process_ids=observed,
                expected_creation_times=expected, instances=instance,
                record_snapshot=record, cleanup_deadline=11.0,
            )
        self.assertEqual([((7,), {7: 123}), ((8,), {7: 123, 8: 124})], calls)
        self.assertEqual([mock.call(6, observed, instances=instance)] * 2, query.call_args_list)
        self.assertEqual({7, 8}, observed)
        self.assertEqual(10.5, clock[0])

    def test_windows_cleanup_stops_on_known_attempted_unknown_or_deadline(self) -> None:
        cases = (
            ("attempted_still_alive", [{7: (6, "python.exe", 123)}, {}], [10.0], 1),
            ("unknown", [None, {}], [10.0], 1),
            ("deadline_before_snapshot", [{8: (7, "python.exe", 124)}], [11.0], 0),
            ("deadline_after_snapshot", [{8: (7, "python.exe", 124)}, {}], [10.0, 11.0], 1),
            ("reused_foreign_instance", [{7: (6, "foreign.exe", 999)}, {}], [10.0], 1),
        )
        for name, snapshots, times, query_count in cases:
            with self.subTest(case=name):
                expected = {7: 123}
                observed = {7}

                def record(snapshot):
                    # Core preserves the first birth and never grants a reused
                    # PID a new termination identity.
                    for pid, row in snapshot.items():
                        expected.setdefault(pid, row[2])
                    observed.update(snapshot)

                def monotonic():
                    return times.pop(0) if len(times) > 1 else times[0]

                with mock.patch.object(supervision.os, "name", "nt"), mock.patch.object(
                    supervision.time, "monotonic", side_effect=monotonic
                ), mock.patch.object(
                    supervision, "_windows_process_tree_observation", side_effect=snapshots
                ) as query, mock.patch.object(
                    supervision, "_terminate_windows_process_ids"
                ) as terminate:
                    supervision._clean_windows_observed_descendants(
                        (7,), root_process_id=6, observed_process_ids=observed,
                        expected_creation_times=expected, instances=None,
                        record_snapshot=record, cleanup_deadline=11.0,
                    )
                self.assertEqual(query_count, query.call_count)
                terminate.assert_called_once_with(
                    (7,), expected_creation_times=expected, cleanup_deadline=11.0,
                )
                self.assertEqual(123, expected[7])

    def test_windows_venv_fast_runtime_and_joined_child_are_terminal(self) -> None:
        source = "import subprocess,sys; subprocess.run([sys.executable,'-c','print(123)'],check=True); print('joined')"
        result = run_supervised((sys.executable, "-c", source), cwd=Path.cwd(), timeout_seconds=10)
        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual("process_exit", result.terminal_reason)
        self.assertTrue(result.cleanup_confirmed)
        self.assertEqual((), result.descendant_process_ids)
        self.assertEqual("123\njoined\n", result.stdout)

    def test_native_process_snapshot_query_and_malformed_rows_remain_unknown(self) -> None:
        prefix = supervision._WindowsSystemProcessPrefix
        size = ctypes.sizeof(prefix)
        def table():
            buffer = ctypes.create_string_buffer(size * 2)
            row = prefix.from_buffer(buffer)
            row.UniqueProcessId = 7
            row.InheritedFromUniqueProcessId = 1
            row.CreateTime = 100
            return buffer, row
        buffer, _ = table()
        self.assertEqual({7: (1, "", 100)}, supervision._parse_windows_system_process_information(buffer, size))
        for defect in ("length", "short", "offset", "duplicate", "name", "odd_name", "name_length"):
            with self.subTest(defect=defect):
                buffer, row = table()
                used = size
                if defect == "length":
                    used = ctypes.sizeof(buffer) + 1
                elif defect == "short":
                    used = size - 1
                elif defect == "offset":
                    row.NextEntryOffset = 1
                elif defect == "duplicate":
                    row.NextEntryOffset = size
                    prefix.from_buffer(buffer, size).UniqueProcessId = 7
                    used = size * 2
                else:
                    row.ImageName.Length = 3 if defect == "odd_name" else 2
                    row.ImageName.MaximumLength = 0 if defect == "name_length" else 4
                    row.ImageName.Buffer = ctypes.addressof(buffer) if defect != "name" else 1
                self.assertIsNone(supervision._parse_windows_system_process_information(buffer, used))
        # Native status failure and bounded resizing cannot become a known
        # empty tree. A successful table still needs our same-handle ABI join.
        for failure in ("status", "resize", "short", "self_birth"):
            with self.subTest(failure=failure):
                library = mock.Mock()
                def query(_class, buffer, _capacity, returned):
                    if failure == "status":
                        return 0xc0000022
                    if failure == "resize":
                        return 0xc0000004
                    row = prefix.from_buffer(buffer)
                    row.UniqueProcessId = supervision.os.getpid()
                    row.CreateTime = 100
                    ctypes.cast(returned, ctypes.POINTER(ctypes.c_uint32)).contents.value = size - 1 if failure == "short" else size
                    return 0
                library.NtQuerySystemInformation.side_effect = query
                with mock.patch.object(supervision.os, "name", "nt"), mock.patch.object(
                    supervision.ctypes, "WinDLL", return_value=library, create=True
                ), mock.patch.object(supervision, "_windows_process_creation_time", return_value=(101, "ok")):
                    self.assertIsNone(supervision._windows_system_process_snapshot())
                self.assertLessEqual(library.NtQuerySystemInformation.call_count, 9)

    def test_public_configuration_defaults_remain_exact(self) -> None:
        signature = inspect.signature(run_supervised)

        self.assertIs(inspect.Parameter.empty, signature.parameters["cwd"].default)
        self.assertIs(
            inspect.Parameter.empty,
            signature.parameters["timeout_seconds"].default,
        )
        self.assertEqual(3.0, signature.parameters["grace_seconds"].default)
        self.assertIsNone(signature.parameters["environment"].default)
        self.assertIsNone(signature.parameters["cancel_event"].default)

    def test_success_requires_zero_contained_processes(self) -> None:
        result = run_supervised(
            (sys.executable, "-c", "print('ok')"),
            cwd=Path.cwd(),
            timeout_seconds=5,
        )
        self.assertTrue(result.ok, result.to_dict())
        self.assertTrue(result.cleanup_confirmed)
        self.assertEqual((), result.descendant_process_ids)
        self.assertFalse(result.root_process_running)
        self.assertTrue(result.containment_query_succeeded)

    def test_requested_interpreter_identity_is_preserved(self) -> None:
        source = (
            "import json,sys;"
            "print(json.dumps({'executable':sys.executable,'prefix':sys.prefix}))"
        )
        result = run_supervised(
            (sys.executable, "-c", source),
            cwd=Path.cwd(),
            timeout_seconds=5,
        )

        self.assertTrue(result.ok, result.to_dict())
        payload = json.loads(result.stdout)
        self.assertEqual(
            Path(sys.executable).resolve(),
            Path(payload["executable"]).resolve(),
        )
        self.assertEqual(sys.prefix, payload["prefix"])

    def test_unknown_process_tree_query_blocks_cleanup(self) -> None:
        with mock.patch(
            "flowguard.process_supervision._windows_process_tree_observation",
            return_value=None,
        ):
            result = run_supervised(
                (sys.executable, "-c", "pass"),
                cwd=Path.cwd(),
                timeout_seconds=5,
                grace_seconds=0.01,
            )

        self.assertFalse(result.ok)
        self.assertFalse(result.cleanup_confirmed)
        self.assertFalse(result.containment_query_succeeded)
        self.assertEqual("cleanup_unconfirmed", result.terminal_reason)

    def test_transient_process_tree_query_failure_does_not_poison_final_cleanup(
        self,
    ) -> None:
        # The launch observation may race a short-lived Windows launcher.  A
        # later confirmed empty containment/tree observation is authoritative
        # for cleanup; only an unknown final observation remains blocking.
        observations = [None]

        def observe_until_known(*_args, **_kwargs):
            # The production code may need more than one observation while a
            # short-lived launcher exits.  Model the contract (one transient
            # unknown, then a stable empty tree) rather than a fixed query
            # count that turns an extra legitimate observation into
            # StopIteration.
            return observations.pop(0) if observations else {}

        with mock.patch(
            "flowguard.process_supervision._windows_process_tree_observation",
            side_effect=observe_until_known,
        ):
            result = run_supervised(
                (sys.executable, "-c", "pass"),
                cwd=Path.cwd(),
                timeout_seconds=5,
                grace_seconds=0.01,
            )

        self.assertTrue(result.ok, result.to_dict())
        self.assertTrue(result.cleanup_confirmed)
        self.assertTrue(result.containment_query_succeeded)

    def test_pid_reuse_is_not_confirmed_as_the_original_descendant(self) -> None:
        snapshot = {
            41: (7, "python.exe", 200),
            42: (7, "python.exe", 300),
        }
        self.assertEqual(
            (42,),
            _confirmed_windows_process_ids(snapshot, {41: 100, 42: 300}),
        )
        self.assertEqual(
            (),
            _confirmed_windows_process_ids(snapshot, {42: 300}, (42,)),
        )

    def test_transient_exited_root_pid_is_not_a_descendant(self) -> None:
        self.assertEqual((), _descendant_process_ids((321,), 321))
        self.assertEqual((654,), _descendant_process_ids((321, 654), 321))
        self.assertIsNone(_descendant_process_ids(None, 321))

    def test_green_looking_value_with_descendants_is_not_success(self) -> None:
        result = SupervisedCommandResult(
            command=(sys.executable, "-c", "pass"),
            cwd=str(Path.cwd().resolve()),
            episode_token="episode:caller",
            started_at_epoch=1.0,
            finished_at_epoch=2.0,
            exit_code=0,
            stdout="",
            stderr="",
            terminal_reason="process_exit",
            timed_out=False,
            cancelled=False,
            interrupted=False,
            termination_stage="none",
            cleanup_confirmed=True,
            descendant_process_ids=(999,),
        )

        self.assertFalse(result.ok)

    def test_unknown_containment_query_blocks_deterministically(self) -> None:
        with mock.patch(
            "flowguard.process_supervision._contained_process_ids",
            return_value=None,
        ):
            result = run_supervised(
                (sys.executable, "-c", "pass"),
                cwd=Path.cwd(),
                timeout_seconds=5,
                grace_seconds=0.01,
            )

        self.assertFalse(result.ok)
        self.assertFalse(result.cleanup_confirmed)
        self.assertFalse(result.containment_query_succeeded)
        self.assertEqual("cleanup_unconfirmed", result.terminal_reason)

    def test_normal_exit_preserves_exact_stream_and_status_parity(self) -> None:
        source = (
            "import sys;"
            "print('stdout-value');"
            "print('stderr-value', file=sys.stderr);"
            "raise SystemExit(7)"
        )
        command = (sys.executable, "-c", source)

        result = run_supervised(
            command,
            cwd=Path.cwd(),
            timeout_seconds=5,
        )

        self.assertEqual(command, result.command)
        self.assertEqual(str(Path.cwd().resolve()), result.cwd)
        self.assertEqual(7, result.exit_code)
        self.assertEqual("stdout-value\n", result.stdout)
        self.assertEqual("stderr-value\n", result.stderr)
        self.assertEqual("process_exit", result.terminal_reason)
        self.assertEqual("none", result.termination_stage)
        self.assertTrue(result.cleanup_confirmed)
        self.assertFalse(result.ok)

    def test_supervised_bytes_preserves_nul_and_non_utf8_output(self) -> None:
        source = (
            "import sys;"
            "data=sys.stdin.buffer.read();"
            "sys.stdout.buffer.write(data+b'\\x00\\xff');"
            "sys.stderr.buffer.write(b'\\x00\\xfe')"
        )
        result = run_supervised_bytes(
            (sys.executable, "-c", source),
            cwd=Path.cwd(),
            input_bytes=b"input\x00\xff",
            timeout_seconds=5,
        )

        self.assertTrue(result.ok, result.to_dict())
        self.assertIsInstance(result.stdout, bytes)
        self.assertIsInstance(result.stderr, bytes)
        self.assertEqual(b"input\x00\xff\x00\xff", result.stdout)
        self.assertEqual(b"\x00\xfe", result.stderr)

    def test_git_query_timeout_cleans_descendants(self) -> None:
        source = (
            "import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
            "time.sleep(60)"
        )
        started = time.monotonic()
        result = run_supervised_bytes(
            (sys.executable, "-c", source),
            cwd=Path.cwd(),
            timeout_seconds=0.2,
            grace_seconds=0.2,
        )
        elapsed = time.monotonic() - started

        self.assertTrue(result.timed_out, result.to_dict())
        self.assertTrue(result.cleanup_confirmed, result.to_dict())
        self.assertEqual((), result.descendant_process_ids)
        self.assertLess(elapsed, 0.2 + 0.2 + 5.0)

    def test_git_observation_has_one_total_deadline(self) -> None:
        calls: list[float] = []
        clock = [0.0]

        class Completed:
            timed_out = False
            cleanup_confirmed = True
            exit_code = 0
            terminal_reason = "process_exit"
            stdout = b""
            stderr = b""

        def fake_query(*args, **kwargs):
            calls.append(float(kwargs["timeout_seconds"]))
            clock[0] += 0.6
            return Completed()

        with (
            mock.patch.object(ownership.time, "monotonic", side_effect=lambda: clock[0]),
            mock.patch.object(ownership, "run_supervised_bytes", side_effect=fake_query),
            ownership.git_observation_budget(timeout_seconds=1.0),
        ):
            ownership._git_bytes(Path.cwd(), "first")
            ownership._git_bytes(Path.cwd(), "second")
            with self.assertRaises(ownership.GitQueryTimeout) as raised:
                ownership._git_bytes(Path.cwd(), "third")

        self.assertEqual(2, len(calls))
        self.assertEqual("source_observation_timeout", raised.exception.code)
        self.assertEqual("third", raised.exception.query_category)

    def test_git_query_timeout_does_not_fallback_to_filesystem_walk(self) -> None:
        class TimedOut:
            timed_out = True
            cleanup_confirmed = True
            exit_code = None
            terminal_reason = "timeout"
            stdout = b""
            stderr = b""
            cancelled = False
            interrupted = False

        with (
            mock.patch.object(ownership, "run_supervised_bytes", return_value=TimedOut()),
            mock.patch.object(
                Path,
                "glob",
                side_effect=AssertionError("unbounded filesystem fallback"),
            ),
        ):
            with self.assertRaises(ownership.GitQueryTimeout) as raised:
                ownership.resolve_input_manifest(Path.cwd(), ("flowguard/**/*.py",))

        self.assertEqual("git_query_timeout", raised.exception.code)

    def test_timeout_terminates_spawned_grandchild(self) -> None:
        source = (
            "import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
            "time.sleep(60)"
        )
        result = run_supervised(
            (sys.executable, "-c", source),
            cwd=Path.cwd(),
            timeout_seconds=0.5,
            grace_seconds=0.2,
        )
        self.assertTrue(result.timed_out, result.to_dict())
        self.assertTrue(result.cleanup_confirmed, result.to_dict())
        self.assertEqual((), result.descendant_process_ids)
        self.assertFalse(result.ok)

    def test_root_exit_with_detached_grandchild_is_cleaned_but_not_passed(
        self,
    ) -> None:
        # Popen returning a launcher PID does not prove that its Python body
        # started. Require the real child to enter its long-lived body before
        # the root exits; an unstarted fixture cannot exercise orphan cleanup.
        child_source = (
            "import json,os,sys,time;from pathlib import Path;"
            "ready=Path(sys.argv[1]);temporary=ready.with_suffix('.tmp');"
            "temporary.write_text(json.dumps({'pid':os.getpid(),"
            "'ppid':os.getppid(),'executable':sys.executable}),encoding='utf-8');"
            "temporary.replace(ready);"
            "time.sleep(60)"
        )
        source = "\n".join((
            "import subprocess,sys,time;from pathlib import Path",
            "ready=Path(sys.argv[1])",
            "with Path(sys.argv[2]).open('wb') as child_stderr:",
            "    child=subprocess.Popen([sys.executable,'-c',sys.argv[3],str(ready)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=child_stderr)",
            "    deadline=time.monotonic()+3.0",
            "    while not ready.is_file():",
            "        if child.poll() is not None:",
            "            raise RuntimeError('detached fixture child exited before READY')",
            "        if time.monotonic() >= deadline:",
            "            raise RuntimeError('detached fixture child READY deadline exhausted')",
            "        time.sleep(0.01)",
            "    if child.poll() is not None:",
            "        raise RuntimeError('detached fixture child exited after READY')",
            "    print(child.pid)",
        ))
        with tempfile.TemporaryDirectory() as temporary:
            ready = Path(temporary) / 'child-ready.json'
            child_stderr = Path(temporary) / 'child-stderr.log'
            result = run_supervised(
                (sys.executable, "-c", source, str(ready), str(child_stderr), child_source),
                cwd=Path.cwd(),
                timeout_seconds=5,
                grace_seconds=0.2,
            )
            diagnostics = {
                'supervised_result': result.to_dict(),
                'child_stderr': child_stderr.read_text(encoding='utf-8', errors='replace') if child_stderr.is_file() else None,
                'ready': ready.read_text(encoding='utf-8') if ready.is_file() else None,
            }
            self.assertEqual(0, result.exit_code, diagnostics)
            self.assertTrue(ready.is_file(), diagnostics)
            child_runtime = json.loads(ready.read_text(encoding='utf-8'))
            self.assertGreater(child_runtime['pid'], 0)
            self.assertGreater(child_runtime['ppid'], 0)
            self.assertEqual(Path(sys.executable).resolve(), Path(child_runtime['executable']).resolve())
            self.assertEqual("descendants_after_root_exit", result.terminal_reason, diagnostics)
            self.assertIn(result.termination_stage, {"terminate", "force_kill"})
            self.assertTrue(result.cleanup_confirmed, diagnostics)
            self.assertEqual((), result.descendant_process_ids)
            self.assertFalse(result.ok)

    def test_terminal_artifact_is_complete_json(self) -> None:
        result = run_supervised(
            (sys.executable, "-c", "raise SystemExit(3)"),
            cwd=Path.cwd(),
            timeout_seconds=5,
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = write_terminal_artifact(
                Path(temporary) / "terminal.json",
                result,
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(3, payload["exit_code"])
        self.assertTrue(payload["cleanup_confirmed"])
        self.assertEqual("blocked", payload["status"])


if __name__ == "__main__":
    unittest.main()
