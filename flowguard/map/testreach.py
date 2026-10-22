"""One isolated pytest invocation observing each selected item's own call window."""

from __future__ import annotations

import json
import sys
import traceback
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

        def record(self, nodeid):
            return self.records.setdefault(nodeid, {"nodeid": nodeid, "entered": False,
                "call_passed": False, "failed": False, "consulted": []})

        @pytest.hookimpl(hookwrapper=True, tryfirst=True)
        def pytest_runtest_call(self, item):
            record = self.record(item.nodeid)
            record["entered"] = True
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

    plugin = Reach()
    try:
        # Exactly one pytest.main in this new process, never inside a model process.
        code = pytest.main(["-q", "-p", "no:cacheprovider", "--rootdir", str(root),
                            *request["nodes"]], plugins=[plugin])
        payload = {"complete": True, "exit_code": int(code), "items": list(plugin.records.values())}
    except BaseException:
        payload, code = {"error": traceback.format_exc(limit=5)}, 2
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
