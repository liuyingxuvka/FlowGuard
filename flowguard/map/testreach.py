"""One isolated pytest invocation observing each selected item's own call window."""

from __future__ import annotations

import json
import sys
import traceback
from contextlib import nullcontext
from pathlib import Path

from .facts import AnchorWatch


def main() -> int:
    root, request_path, result_path = (Path(value) for value in sys.argv[1:])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    try:
        import pytest
    except ImportError as exc:
        result_path.write_text(json.dumps({"error": f"pytest is required to check TESTED_BY: {exc}"}), encoding="utf-8")
        return 2

    class Reach:
        def __init__(self):
            self.records = {}
            self.import_errors = []

        def record(self, nodeid):
            return self.records.setdefault(nodeid, {"nodeid": nodeid, "entered": False,
                "call_passed": False, "failed": False, "consulted": []})

        @pytest.hookimpl(hookwrapper=True, tryfirst=True)
        def pytest_runtest_call(self, item):
            record = self.record(item.nodeid)
            record["entered"] = True
            monitoring = getattr(sys, "monitoring", None)
            if monitoring is not None:
                monitoring.restart_events()  # DISABLE decisions belong to one test item only
            watch = AnchorWatch(root, request["anchors"], test_call=True)
            try:
                with watch:
                    yield
            finally:
                record["consulted"] = sorted(watch.consulted())

        def pytest_runtest_logreport(self, report):
            record = self.record(report.nodeid)
            record["failed"] |= report.failed
            # Subtest failures must survive a later passing parent call report.
            if report.when == "call" and not hasattr(report, "context"):
                record["call_passed"] |= report.passed

        def pytest_sessionfinish(self, session, exitstatus):
            for item in session.items:
                self.record(item.nodeid)

        def pytest_exception_interact(self, node, call, report):
            if "view" not in request:
                return
            exception, seen = call.excinfo.value, set()
            while exception is not None and id(exception) not in seen:
                seen.add(id(exception))
                if isinstance(exception, ImportError):
                    self.import_errors.append({"type": type(exception).__name__, "name": exception.name,
                        "phase": call.when, "nodeid": node.nodeid, "message": str(exception)})
                    break
                exception = exception.__cause__ or exception.__context__

    plugin = Reach()
    try:
        namespace = nullcontext()
        if "view" in request:
            from .proof import model_namespace
            from .targetfile import ModelView
            namespace = model_namespace(ModelView.from_payload(request["view"]))
        # Exactly one pytest.main in this new process, never inside a model process.
        with namespace:
            code = pytest.main(["-q", "-p", "no:cacheprovider", "--rootdir", str(root),
                                *request["nodes"]], plugins=[plugin])
        payload = {"complete": True, "exit_code": int(code), "items": list(plugin.records.values())}
        if "view" in request:
            payload["import_errors"] = plugin.import_errors
    except BaseException:
        payload, code = {"error": traceback.format_exc(limit=5)}, 2
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
