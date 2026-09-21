import json
from contextlib import redirect_stdout
from io import StringIO

from flowguard.__main__ import main


def _run(*argv: str) -> tuple[int, dict]:
    stream = StringIO()
    with redirect_stdout(stream):
        status = main(list(argv))
    return status, json.loads(stream.getvalue())


def test_retired_route_reference_command_is_rejected_without_a_producer():
    status, payload = _run("route-reference", "model_first_function_flow", "--json")

    assert status == 2
    assert payload["status"] == "blocked"
    assert payload["decision"] == "block"
    assert payload["producer_count"] == 0
    assert payload["error"] == "unknown operation: route-reference"
    assert payload["allowed_operations"] == ["read", "change", "release"]


def test_retired_route_reference_command_rejects_unknown_route_without_parsing_it():
    status, payload = _run("route-reference", "not-a-current-route", "--json")

    assert status == 2
    assert payload["status"] == "blocked"
    assert payload["decision"] == "block"
    assert payload["producer_count"] == 0
    assert payload["error"] == "unknown operation: route-reference"
