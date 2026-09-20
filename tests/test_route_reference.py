import json
from contextlib import redirect_stdout
from io import StringIO

from flowguard.__main__ import main


def _run(*argv: str) -> tuple[int, dict]:
    stream = StringIO()
    with redirect_stdout(stream):
        status = main(list(argv))
    return status, json.loads(stream.getvalue())


def test_route_reference_returns_one_public_capsule_without_catalog():
    status, payload = _run("route-reference", "model_first_function_flow", "--json")

    assert status == 0
    assert payload["route"]["route_id"] == "model_first_function_flow"
    assert payload["route"]["reference_edges"]
    assert "current_route_registry" not in payload


def test_route_reference_blocks_stale_or_unknown_route():
    status, payload = _run("route-reference", "not-a-current-route", "--json")

    assert status == 1
    assert payload["status"] == "blocked"
    assert payload["route"] == {}
