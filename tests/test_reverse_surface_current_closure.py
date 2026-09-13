from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_PATH = ROOT / ".flowguard/structure/reverse-surfaces/current-discovery.json"
MAP_PATH = ROOT / ".flowguard/structure/reverse-surfaces/implementation-surface-map.json"


def _current() -> tuple[dict, dict]:
    discovery = json.loads(DISCOVERY_PATH.read_text(encoding="utf-8"))
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    return discovery, mapping


def _expanded(mapping: dict) -> list[dict]:
    rows = list(mapping.get("surfaces", []))
    for group in mapping.get("component_groups", []):
        for surface_id in group["surface_ids"]:
            rows.append({**group, "surface_id": surface_id})
    return rows


def test_current_reverse_surface_ui_like_actions_are_explicitly_governed() -> None:
    discovery, mapping = _current()
    discovered_ui = {
        row["surface_id"]
        for row in discovery["surfaces"]
        if row["surface_kind"] == "ui_like_action"
    }
    mapped = {
        row["surface_id"]: row
        for row in _expanded(mapping)
        if row["surface_id"] in discovered_ui
    }
    # The current source observation includes the four UI-like action
    # surfaces added by the forward/reverse closure work.  Keep this explicit
    # denominator tied to the checked-in current discovery artifact.
    assert len(discovered_ui) == 95
    assert set(mapped) == discovered_ui
    assert all(
        row["disposition"] in {"governed", "internal_proven"}
        and row.get("intent_id")
        and row.get("model_owner_id")
        and row.get("model_obligation_ids")
        for row in mapped.values()
    )


def test_dynamic_and_unbound_boundaries_have_current_resolved_disposition() -> None:
    discovery, mapping = _current()
    special_ids = {
        row["surface_id"]
        for row in discovery["surfaces"]
        if row["surface_kind"]
        in {"dynamic", "plugin", "placeholder", "unreachable_or_unbound"}
    }
    mapped = {
        row["surface_id"]: row
        for row in _expanded(mapping)
        if row["surface_id"] in special_ids
    }
    assert set(mapped) == special_ids
    assert all(
        row["disposition"] in {"governed", "internal_proven", "retired_proven"}
        for row in mapped.values()
    )
    assert all(
        row.get("intent_id")
        and row.get("model_obligation_ids")
        and row.get("owner")
        and row.get("test_refs")
        and row.get("receipt_refs")
        for row in mapped.values()
        if row["disposition"] == "governed"
    )


def test_examples_are_explicitly_outside_runtime_boundary() -> None:
    discovery, mapping = _current()
    example_ids = {
        row["surface_id"]
        for row in discovery["surfaces"]
        if row["source_path"].startswith("examples/")
        and row["surface_kind"] != "ui_like_action"
    }
    mapped = {
        row["surface_id"]: row
        for row in _expanded(mapping)
        if row["surface_id"] in example_ids
    }
    assert set(mapped) == example_ids
    assert all(
        row["disposition"]
        in {"governed", "internal_proven", "retired_proven", "not_applicable_proven"}
        for row in mapped.values()
    )
    assert all(
        (
            "examples" in row.get("reason", "").lower()
            if row["disposition"] == "not_applicable_proven"
            else row.get("intent_id")
            and row.get("model_obligation_ids")
            and row.get("owner")
            and row.get("test_refs")
            and row.get("receipt_refs")
        )
        for row in mapped.values()
    )


def test_current_reverse_surface_map_has_no_blocked_or_unmodeled_rows() -> None:
    discovery, mapping = _current()
    discovered_ids = {row["surface_id"] for row in discovery["surfaces"]}
    expanded = _expanded(mapping)
    discovery_by_id = {row["surface_id"]: row for row in discovery["surfaces"]}
    # The current denominator is the exact source observation after the
    # module/class/function call-graph closure repair.  The current direct
    # source freeze contains 15,517 explicitly authored observations; no
    # predecessor denominator is inherited.
    assert len(expanded) == len(discovered_ids) == 15517
    assert {row["surface_id"] for row in expanded} == discovered_ids
    assert not any(row["disposition"] == "blocked_gap" for row in expanded)
    assert not any(
        discovery_by_id[row["surface_id"]]["surface_kind"] == "ui_like_action"
        and row["disposition"] not in {"governed", "internal_proven"}
        for row in expanded
    )


def test_current_model_obligations_are_two_way_conserved() -> None:
    discovery, mapping = _current()
    expanded = _expanded(mapping)
    discovered_ids = {row["surface_id"] for row in discovery["surfaces"]}
    bindings = {
        obligation_id: {
            row["surface_id"]
            for row in expanded
            if obligation_id in row.get("model_obligation_ids", [])
        }
        for obligation_id in {
            obligation_id
            for row in expanded
            for obligation_id in row.get("model_obligation_ids", [])
        }
    }
    for obligation in mapping["model_obligations"]:
        if obligation["disposition"] == "governed":
            assert obligation["surface_ids"]
            assert set(obligation["surface_ids"]) <= discovered_ids
            assert set(obligation["surface_ids"]) == bindings[obligation["obligation_id"]]
