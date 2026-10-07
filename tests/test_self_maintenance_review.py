"""The private wrapper composes one mocked native builder, never a real full."""

import json
from types import SimpleNamespace

import pytest

from scripts import check_self_maintenance_review as command


@pytest.mark.parametrize(("bundle_ok", "review_ok", "expected"), [
    (True, True, 0), (False, True, 1), (True, False, 1),
])
def test_composed_builder_is_called_once(monkeypatch, capsys, bundle_ok, review_ok, expected):
    calls = []
    bundle, review = SimpleNamespace(ok=bundle_ok), SimpleNamespace(ok=review_ok)
    def build(root, **kwargs):
        calls.append((root, kwargs))
        return bundle, review
    monkeypatch.setattr(command, "build_flowguard_self_architecture_reduction_review", build)
    monkeypatch.setattr(command.BlueprintCompactProjection, "self_qualification", lambda value: {"ok": value.ok})
    monkeypatch.setattr(command.BlueprintCompactProjection, "reduction", lambda value: {
        "ok": value.ok, "review_fingerprint": "review", "projection_fingerprint": "projection",
    })
    assert command.main(["--root", "chosen-root", "--model-receipt-dir", "chosen-store", "--require-executed-evidence", "--json"]) == expected
    assert calls == [("chosen-root", {"require_executed_evidence": True, "model_receipt_dir": "chosen-store"})]
    payload = json.loads(capsys.readouterr().out)
    assert payload["composed_self_maintenance_review"] is True
    assert payload["architecture_reduction_review"]["projection_fingerprint"] == "projection"


@pytest.mark.parametrize("error", [command.FlowGuardSelfBlueprintError("bad"), OSError("bad"), ValueError("bad")])
def test_builder_errors_are_invalid_not_success(monkeypatch, capsys, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(command, "build_flowguard_self_architecture_reduction_review", fail)
    assert command.main(["--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["findings"][0]["code"] == "flowguard_self_blueprint_invalid"
