import copy
import json
from pathlib import Path

import flowguard.behavior_surface_audit as surface_audit
from scripts.audit_public_behavior_surface import main as audit_main
from scripts.discover_behavior_inventory import load_discovery_manifest
from flowguard.behavior_surface_audit import (
    IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED,
    IMPLEMENTATION_SURFACE_CLASSES,
    IMPLEMENTATION_SURFACE_MAP_SCHEMA,
    PUBLIC_BEHAVIOR_SURFACE_CLASSES,
    PUBLIC_BEHAVIOR_SURFACE_GAP_SCHEMA,
    audit_implementation_behavior_surface,
    build_public_behavior_surface_gap_report,
    compact_implementation_behavior_surface_audit,
    discover_implementation_surface_shard,
    discover_implementation_behavior_surfaces,
    merge_implementation_surface_shards,
    plan_implementation_surface_shards,
    _surface_hash,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "flowguard_behavior_inventory_manifest.json"


def test_compact_reverse_audit_projection_is_bounded_and_deterministic():
    discovery = {
        "status": "passed",
        "discovery_fingerprint": "sha256:discovery",
        "source_paths": ["a.py"],
        "surfaces": [{"surface_id": "surface:1"}, {"surface_id": "surface:2"}],
        "call_graph": [
            {"resolution": "resolved"},
            {"resolution": "resolved"},
            {"resolution": "resolved_external_contract"},
        ],
        "external_contracts": ["external:1"],
        "unbound_surface_ids": [],
        "findings": [
            {"code": "z", "severity": "blocker", "message": "z"},
            {"code": "a", "severity": "blocker", "message": "a"},
        ],
    }
    audit = {
        "status": "passed",
        "reverse_closure_complete": True,
        "discovered_surface_count": 2,
        "mapping_input_surface_row_count": 2,
        "mapping_surface_count": 2,
        "mapping_component_group_count": 1,
        "mapping_component_group_member_count": 2,
        "surface_group_count": 1,
        "component_grouped_surface_count": 2,
        "individual_surface_count": 0,
        "model_obligation_inventory_count": 1,
        "unmapped_surface_ids": [],
        "orphan_mapping_surface_ids": [],
        "unmapped_model_obligation_ids": [],
        "unmodeled_ui_like_action_ids": [],
        "duplicate_primary_owner_surface_ids": [],
        "current_authority_join": {"status": "current"},
        "current_behavior_ledger_join": {"status": "current"},
        "evidence_fingerprint": "sha256:audit",
        "findings": [{"code": "audit_code", "severity": "blocker", "message": "x"}],
        "surfaces": [{"surface_id": "should-not-be-copied"}],
        "component_groups": [{"group_id": "should-not-be-copied"}],
    }
    first = compact_implementation_behavior_surface_audit(
        discovery,
        audit,
        discovery_artifact="discovery.json",
        surface_map_artifact="map.json",
        full_artifact="audit.json",
        max_finding_samples=1,
    )
    second = compact_implementation_behavior_surface_audit(
        discovery,
        audit,
        discovery_artifact="discovery.json",
        surface_map_artifact="map.json",
        full_artifact="audit.json",
        max_finding_samples=1,
    )
    assert first == second
    assert first["discovery"]["surface_count"] == 2
    assert first["discovery"]["call_resolution_counts"] == {
        "resolved": 2,
        "resolved_external_contract": 1,
    }
    assert first["audit"]["mapping_surface_count"] == 2
    assert first["audit"]["finding_samples"] == [
        {"code": "audit_code", "severity": "blocker", "message": "x"}
    ]
    assert first["audit"]["omitted_finding_count"] == 0
    assert "surfaces" not in first
    assert "call_graph" not in first
    assert "component_groups" not in first
    assert first["artifact_refs"] == {
        "discovery": "discovery.json",
        "surface_map": "map.json",
        "full_audit": "audit.json",
    }


def test_public_surface_cli_default_terminal_output_is_bounded(tmp_path, capsys):
    output = tmp_path / "public_surface_gap.json"
    assert audit_main(
        [
            "--root",
            str(ROOT),
            "--manifest",
            str(MANIFEST),
            "--output",
            str(output),
            "--authority-status",
            "blocked",
        ]
    ) == 1
    terminal = json.loads(capsys.readouterr().out)
    assert terminal["schema_version"] == "flowguard.public_behavior_surface_gap_compact.v1"
    assert terminal["artifact_ref"] == str(output.resolve())
    assert "materialized_behavior_rows" not in terminal
    full = json.loads(output.read_text(encoding="utf-8"))
    assert full["status"] == "blocked"


def test_public_surface_audit_stays_fail_closed_without_authority_even_with_explicit_rows():
    manifest = load_discovery_manifest(MANIFEST, root=ROOT)
    report = build_public_behavior_surface_gap_report(
        root=ROOT,
        manifest_evidence=manifest,
        manifest_path=MANIFEST,
        authority_status="blocked",
        authority_reason="project-audit: model_authority_invalid",
    )

    assert report["schema_version"] == PUBLIC_BEHAVIOR_SURFACE_GAP_SCHEMA
    assert report["status"] == "blocked"
    assert report["manifest"]["materialized_behavior_count"] == 10
    assert report["generated_behavior_ids"] == []
    assert len(report["materialized_behavior_rows"]) == 10
    assert report["denominator_expansion"] == "explicit_manifest"
    assert report["complete_public_surface_claim_licensed"] is False
    assert report["unresolved_surface_classes"] == []
    codes = {finding["code"] for finding in report["findings"]}
    assert "behavior_discovery_current_authority_not_green" in codes
    assert report["declaration_summary"]["declarations"]["python_public_import"][
        "declared_name_count"
    ] > 0
    # The compact parser intentionally dispatches one fixed tuple rather than
    # constructing a second argparse command registry.  The public operation
    # inventory is asserted by the lifecycle tests and the unknown-operation
    # boundary below; a zero literal parser declaration is therefore current.
    assert report["declaration_summary"]["declarations"]["cli_command"][
        "literal_parser_declarations"
    ]["declared_count"] == 0
    assert all(
        identity["source_path"] in {"flowguard/__init__.py", "flowguard/__main__.py", "pyproject.toml"}
        for identity in report["declaration_summary"]["source_identities"]
    )
    assert report["evidence_fingerprint"].startswith("sha256:")


def test_public_surface_audit_cli_serializes_blocked_report(tmp_path):
    output = tmp_path / "public_surface_gap.json"
    assert audit_main(
        [
            "--root",
            str(ROOT),
            "--manifest",
            str(MANIFEST),
            "--output",
            str(output),
            "--authority-status",
            "blocked",
            "--authority-reason",
            "project-audit: model_authority_invalid",
        ]
    ) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "blocked"
    assert report["generated_behavior_ids"] == []
    assert all(
        finding["code"] != "behavior_discovery_cli_surface_not_manifested"
        for finding in report["findings"]
    )
    assert any(
        finding["code"] == "behavior_discovery_current_authority_not_green"
        for finding in report["findings"]
    )


def test_public_surface_cli_does_not_hide_reverse_denominator_when_map_is_missing(tmp_path):
    root = tmp_path / "reverse"
    root.mkdir()
    root = _write_reverse_surface_fixture(root)
    discovery = discover_implementation_behavior_surfaces(root)
    discovery_path = tmp_path / "discovery.json"
    discovery_path.write_text(json.dumps(discovery), encoding="utf-8")
    output = tmp_path / "public_surface_gap.json"

    assert audit_main(
        [
            "--root",
            str(root),
            "--manifest",
            str(MANIFEST),
            "--output",
            str(output),
            "--surface-discovery",
            str(discovery_path),
        ]
    ) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    reverse = report["implementation_surface_audit"]
    assert reverse["discovered_surface_count"] == len(discovery["surfaces"])
    assert any(
        finding["code"] == "implementation_surface_mapping_missing"
        for finding in reverse["findings"]
    )
    assert report["complete_public_surface_claim_licensed"] is False


def test_empty_supplied_discovery_is_not_replaced_by_a_fresh_observation(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)

    blocked = audit_implementation_behavior_surface(root, mapping, discovery={})
    codes = {item["code"] for item in blocked["findings"]}

    assert blocked["status"] == "blocked"
    assert "implementation_surface_discovery_schema_invalid" in codes
    assert "implementation_surface_discovery_not_current" in codes


def _write_reverse_surface_fixture(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text(
        """
__all__ = [\"run\"]
API_SURFACE = {\"run\": [\"run\"]}

def run(value):
    if value < 0:
        raise ValueError(\"negative\")
    if value == 0:
        retry_run()
    button(\"Run\")
    return Path(\"out.txt\").write_text(str(value))

def retry_run():
    return None

def button(label):
    return label

def placeholder():
    pass  # TODO: implement the real action
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "settings.toml").write_text("enabled = true\n", encoding="utf-8")
    (tmp_path / "proof.txt").write_text(
        "unbound-boundary\n",
        encoding="utf-8",
    )
    (tmp_path / "receipt.txt").write_text(
        "surface-pass\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(
        "def test_surface_smoke():\n    assert True\n",
        encoding="utf-8",
    )
    return tmp_path


def _complete_reverse_map(discovery: dict) -> dict:
    obligation_rows = [
        {
            "obligation_id": f"obligation:{row['surface_id']}",
            "disposition": "governed",
            "surface_ids": [row["surface_id"]],
        }
        for row in discovery["surfaces"]
    ]
    return {
        "schema_version": IMPLEMENTATION_SURFACE_MAP_SCHEMA,
        "inventory_id": "fixture-reverse-surface",
        "project_boundary": "fixture production source",
        "current_revision": "fixture-v1",
        "discovery_fingerprint": discovery["discovery_fingerprint"],
        "claim_boundary": "fixture reverse source-to-intent/model/test closure",
        "surfaces": [
            {
                    "surface_id": row["surface_id"],
                    "intent_id": f"intent:{row['surface_id']}",
                    "model_owner_id": f"model:{row['surface_id']}",
                    "model_obligation_ids": [f"obligation:{row['surface_id']}"],
                    "owner": "fixture-owner",
                    "test_refs": ["tests/test_app.py#test_surface_smoke"],
                    "receipt_refs": ["receipt.txt#surface-pass"],
                    "disposition": IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED,
                }
            for row in discovery["surfaces"]
        ],
        "model_obligations": obligation_rows,
    }


def _write_component_group_fixture(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text(
        """
__all__ = ["entry"]

def entry(value):
    return _helper(value)

def _helper(value):
    return value + 1
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "proof.txt").write_text("component-proof\n", encoding="utf-8")
    (tmp_path / "receipt.txt").write_text(
        "surface-pass\ncomponent-pass\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(
        "def test_surface_smoke():\n    assert True\n\n"
        "def test_component_surface():\n    assert True\n",
        encoding="utf-8",
    )
    return tmp_path


def _component_group_map(discovery: dict) -> tuple[dict, list[str]]:
    mapping = _complete_reverse_map(discovery)
    component_rows = [
        row
        for row in discovery["surfaces"]
        if row["review_granularity"] == "component"
        and row["surface_kind"] in {"module", "function", "class"}
    ]
    assert component_rows
    group_ids = {row["review_group_id"] for row in component_rows}
    assert len(group_ids) == 1
    group_id = next(iter(group_ids))
    members = sorted(row["surface_id"] for row in component_rows)
    member_set = set(members)
    shared_obligation_id = "obligation:component-group"
    mapping["surfaces"] = [
        row for row in mapping["surfaces"] if row["surface_id"] not in member_set
    ]
    mapping["model_obligations"] = [
        row
        for row in mapping["model_obligations"]
        if not set(row["surface_ids"]) & member_set
    ]
    mapping["model_obligations"].append(
        {
            "obligation_id": shared_obligation_id,
            "disposition": "governed",
            "surface_ids": members,
        }
    )
    mapping["component_groups"] = [
        {
            "review_group_id": group_id,
            "review_granularity": "component",
            "surface_ids": members,
            "intent_id": "intent:component-group",
            "model_owner_id": "model:component-group",
            "model_obligation_ids": [shared_obligation_id],
            "owner": "fixture-owner",
            "test_refs": ["tests/test_app.py#test_component_surface"],
            "receipt_refs": ["receipt.txt#component-pass"],
            "disposition": IMPLEMENTATION_SURFACE_DISPOSITION_GOVERNED,
        }
    ]
    return mapping, members


def test_reverse_surface_discovery_is_source_only_and_deterministic(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    first = discover_implementation_behavior_surfaces(root)
    second = discover_implementation_behavior_surfaces(root)

    assert first["status"] == "passed"
    assert first["discovery_fingerprint"] == second["discovery_fingerprint"]
    assert [row["surface_id"] for row in first["surfaces"]] == [
        row["surface_id"] for row in second["surfaces"]
    ]
    assert [row["surface_fingerprint"] for row in first["surfaces"]] == [
        row["surface_fingerprint"] for row in second["surfaces"]
    ]
    kinds = {row["surface_kind"] for row in first["surfaces"]}
    assert {"api", "export", "effect", "error", "recovery", "placeholder", "ui_like_action", "config"} <= kinds
    assert first["call_graph"]
    assert first["unbound_surface_ids"]
    assert all(row["surface_class"] in IMPLEMENTATION_SURFACE_CLASSES for row in first["surfaces"])
    assert {row["surface_class"] for row in first["surfaces"]} >= {
        "code",
        "api",
        "effect",
        "fault",
        "recovery",
        "ui_like",
        "config",
    }
    assert any(
        row["surface_kind"] == "unreachable_or_unbound"
        for row in first["surfaces"]
    )


def test_repeated_dynamic_observations_keep_mergeable_fingerprints(tmp_path):
    (tmp_path / "dynamic.py").write_text(
        """
def resolve_one(value):
    return getattr(value, \"one\")

def resolve_two(value):
    return getattr(value, \"two\")
""",
        encoding="utf-8",
    )
    discovery = discover_implementation_behavior_surfaces(tmp_path)
    dynamic_rows = [
        row for row in discovery["surfaces"] if row["surface_kind"] == "dynamic"
    ]
    assert len(dynamic_rows) == 2
    for row in dynamic_rows:
        assert row["surface_fingerprint"] == _surface_hash(
            {key: value for key, value in row.items() if key != "surface_fingerprint"}
        )


def test_reverse_surface_requires_mapping_and_closes_every_observed_row(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)

    missing = audit_implementation_behavior_surface(root, None, discovery=discovery)
    assert missing["status"] == "blocked"
    assert any(item["code"] == "implementation_surface_mapping_missing" for item in missing["findings"])

    complete = audit_implementation_behavior_surface(
        root,
        _complete_reverse_map(discovery),
        discovery=discovery,
    )
    assert complete["status"] == "passed", complete["findings"]
    assert complete["reverse_closure_complete"] is True


def test_reverse_surface_groups_internal_observations_without_grouping_external_actions(
    tmp_path,
):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    groups = {row["review_group_id"]: [] for row in discovery["surfaces"]}
    for row in discovery["surfaces"]:
        groups[row["review_group_id"]].append(row)

    assert all(row["review_granularity"] in {"surface", "component"} for row in discovery["surfaces"])
    component_rows = [
        row for row in discovery["surfaces"] if row["review_granularity"] == "component"
    ]
    individual_rows = [
        row for row in discovery["surfaces"] if row["review_granularity"] == "surface"
    ]
    assert component_rows
    assert individual_rows
    assert any(len(rows) > 1 for rows in groups.values())
    assert all(
        row["surface_class"] in {
            "api",
            "cli",
            "ui_like",
            "config",
            "effect",
            "fault",
            "recovery",
            "install",
            "code",
        }
        for row in individual_rows
    )
    # Dynamic/plugin/placeholder/unbound observations remain individual so a
    # component-level governed proof cannot conceal a non-governable static
    # boundary.  Their call-graph edges are resolved contracts, not typed
    # uncertainty rows.
    assert all(
        row["review_granularity"] == "surface"
        for row in discovery["surfaces"]
        if row["surface_kind"]
        in {"dynamic", "plugin", "placeholder", "unreachable_or_unbound"}
    )


def test_component_group_mapping_expands_one_binding_to_all_internal_members(
    tmp_path,
):
    root = _write_component_group_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping, members = _component_group_map(discovery)

    accepted = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
    )

    assert accepted["status"] == "passed", accepted["findings"]
    assert accepted["reverse_closure_complete"] is True
    assert accepted["mapping_input_surface_row_count"] < accepted[
        "mapping_surface_count"
    ]
    assert accepted["mapping_component_group_count"] == 1
    assert accepted["mapping_component_group_member_count"] == len(members)
    assert accepted["mapping_surface_count"] == accepted["discovered_surface_count"]


def test_component_group_reverse_obligation_binding_covers_every_expanded_member(
    tmp_path,
):
    root = _write_component_group_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping, members = _component_group_map(discovery)
    obligation = next(
        row
        for row in mapping["model_obligations"]
        if row["obligation_id"] == "obligation:component-group"
    )

    # The component group itself is complete, but the reverse model row omits
    # one expanded member.  The effective member-level contract must remain
    # conserved instead of accepting the compressed input row count.
    obligation["surface_ids"] = members[:-1]

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
    )

    assert blocked["status"] == "blocked"
    assert "implementation_surface_model_obligation_reverse_mismatch" in {
        item["code"] for item in blocked["findings"]
    }
    assert blocked["mapping_input_surface_row_count"] < blocked["mapping_surface_count"]
    assert blocked["mapping_surface_count"] == blocked["discovered_surface_count"]


def test_component_group_mapping_requires_complete_internal_boundary(tmp_path):
    root = _write_component_group_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping, members = _component_group_map(discovery)
    mapping["component_groups"][0]["surface_ids"] = members[:-1]

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
    )

    assert blocked["status"] == "blocked"
    assert "implementation_surface_component_group_membership_mismatch" in {
        item["code"] for item in blocked["findings"]
    }


def test_component_group_mapping_cannot_absorb_public_surface(tmp_path):
    root = _write_component_group_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping, members = _component_group_map(discovery)
    public_id = next(
        row["surface_id"]
        for row in discovery["surfaces"]
        if row["review_granularity"] == "surface"
    )
    mapping["component_groups"][0]["surface_ids"] = [*members, public_id]

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
    )

    assert blocked["status"] == "blocked"
    assert "implementation_surface_component_group_external_member" in {
        item["code"] for item in blocked["findings"]
    }


def test_component_group_mapping_null_shape_is_not_treated_as_omitted(tmp_path):
    root = _write_component_group_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping, _members = _component_group_map(discovery)
    mapping["component_groups"] = None

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
    )

    assert blocked["status"] == "blocked"
    assert "implementation_surface_component_groups_invalid" in {
        item["code"] for item in blocked["findings"]
    }


def test_registered_template_is_an_individual_review_boundary(tmp_path):
    (tmp_path / "template.py").write_text(
        "def register_template(name):\n    return name\n\nregister_template('run')\n",
        encoding="utf-8",
    )
    discovery = discover_implementation_behavior_surfaces(tmp_path)
    template_rows = [
        row for row in discovery["surfaces"] if row["surface_kind"] == "template"
    ]

    assert template_rows
    assert all(row["review_granularity"] == "surface" for row in template_rows)


def test_reverse_surface_rejects_a_merged_snapshot_that_omits_new_source(
    tmp_path,
):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    (root / "new_entry.py").write_text(
        "def new_entry():\n    return 'new'\n",
        encoding="utf-8",
    )

    merged = copy.deepcopy(discovery)
    merged.update(
        {
            "shard_id": "merged",
            "shard_ids": ["fixture-shard-0000"],
            "shard_plan_fingerprint": "sha256:" + "1" * 64,
        }
    )
    canonical = {
        "schema_version": merged["schema_version"],
        "shard_id": merged["shard_id"],
        "source_paths": sorted(merged["source_paths"]),
        "source_identities": sorted(
            merged["source_identities"], key=lambda row: row["source_path"]
        ),
        "surfaces": sorted(
            merged["surfaces"], key=lambda row: row["surface_id"]
        ),
        "call_graph": sorted(
            merged["call_graph"],
            key=lambda row: (
                row["caller_surface_id"],
                row["callee_name"],
                row["resolution"],
            ),
        ),
        "unbound_surface_ids": sorted(merged["unbound_surface_ids"]),
        "shard_plan_fingerprint": merged["shard_plan_fingerprint"],
        "shard_ids": merged["shard_ids"],
    }
    merged["discovery_fingerprint"] = _surface_hash(canonical)
    mapping["discovery_fingerprint"] = merged["discovery_fingerprint"]

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=merged,
    )

    assert blocked["status"] == "blocked"
    assert "implementation_surface_discovery_merged_source_boundary_mismatch" in {
        item["code"] for item in blocked["findings"]
    }


def test_reverse_surface_rejects_tampered_review_group_metadata(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mutated = copy.deepcopy(discovery)
    row = mutated["surfaces"][0]
    row["review_group_id"] = "group:component:forged"
    row["review_granularity"] = "component"

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=mutated,
    )

    assert blocked["status"] == "blocked"
    assert "implementation_surface_discovery_review_group_invalid" in {
        item["code"] for item in blocked["findings"]
    }


def test_reverse_surface_mutations_block_stale_or_incomplete_closure(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)

    mapping["surfaces"] = mapping["surfaces"][:-1]
    missing = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    assert missing["status"] == "blocked"
    assert "implementation_surface_mapping_missing" in {item["code"] for item in missing["findings"]}

    mapping = _complete_reverse_map(discovery)
    mapping["surfaces"][0]["owner"] = ""
    owner_gap = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    assert "implementation_surface_owner_missing" in {item["code"] for item in owner_gap["findings"]}

    mapping = _complete_reverse_map(discovery)
    mapping["surfaces"][0]["test_refs"] = ["tests/test_app.py#test_deleted"]
    test_gap = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    assert "implementation_surface_orphan_test_reference" in {item["code"] for item in test_gap["findings"]}

    mapping = _complete_reverse_map(discovery)
    mapping["model_obligations"] = mapping["model_obligations"][:-1]
    model_gap = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    assert "implementation_surface_model_obligation_unmapped" in {
        item["code"] for item in model_gap["findings"]
    }

    mapping = _complete_reverse_map(discovery)
    (root / "app.py").write_text((root / "app.py").read_text(encoding="utf-8") + "\n# mutation\n", encoding="utf-8")
    mutated_discovery = discover_implementation_behavior_surfaces(root)
    stale = audit_implementation_behavior_surface(root, mapping, discovery=mutated_discovery)
    assert "implementation_surface_mapping_stale" in {item["code"] for item in stale["findings"]}

    unbound_root = tmp_path / "unbound_case"
    unbound_root.mkdir()
    _write_reverse_surface_fixture(unbound_root)
    unbound_discovery = discover_implementation_behavior_surfaces(unbound_root)
    mapping = _complete_reverse_map(unbound_discovery)
    unbound_id = next(
        row["surface_id"]
        for row in unbound_discovery["surfaces"]
        if row["surface_kind"] == "unreachable_or_unbound"
    )
    unbound_row = next(
        row for row in mapping["surfaces"] if row["surface_id"] == unbound_id
    )
    unbound_row.update(
        {
            "disposition": "not_applicable_proven",
            "proof_ref": "proof.txt#unbound-boundary",
            "not_applicable_reason": "legacy typed boundary must be re-authored",
        }
    )
    unbound_gap = audit_implementation_behavior_surface(
        unbound_root,
        mapping,
        discovery=unbound_discovery,
    )
    assert "implementation_surface_unbound_current_disposition_required" in {
        item["code"] for item in unbound_gap["findings"]
    }


def test_supplied_discovery_snapshot_is_replayed_against_current_sources(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)

    # A caller-authored discovery artifact can otherwise carry matching
    # self-reported hashes after the source moved.  The reverse denominator
    # must be re-established from the current bounded source selection.
    (root / "app.py").write_text(
        (root / "app.py").read_text(encoding="utf-8") + "\n# source mutation\n",
        encoding="utf-8",
    )
    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
    )
    codes = {item["code"] for item in blocked["findings"]}

    assert blocked["status"] == "blocked"
    assert "implementation_surface_discovery_source_identity_stale" in codes
    assert "implementation_surface_discovery_replay_mismatch" in codes


def test_full_reverse_audit_reuses_one_complete_source_replay(tmp_path, monkeypatch):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    original = surface_audit.discover_implementation_behavior_surfaces
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def counted(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(
        surface_audit,
        "discover_implementation_behavior_surfaces",
        counted,
    )
    accepted = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
        currentness_profile="full",
    )

    assert accepted["status"] == "passed", accepted["findings"]
    assert len(calls) == 1
    assert "source_paths" not in calls[0][1]


def test_supplied_discovery_cannot_omit_a_new_source_file(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    (root / "new_entry.py").write_text(
        "def newly_added():\n    return True\n",
        encoding="utf-8",
    )

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
    )
    codes = {item["code"] for item in blocked["findings"]}

    assert blocked["status"] == "blocked"
    assert "implementation_surface_discovery_full_replay_mismatch" in codes


def test_reverse_surface_legacy_alias_cannot_supply_current_test_binding(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mapped = mapping["surfaces"][0]
    mapped.pop("test_refs")
    mapped["tests"] = ["tests/test_app.py#test_surface_smoke"]

    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    codes = {item["code"] for item in blocked["findings"]}

    assert blocked["status"] == "blocked"
    assert "implementation_surface_legacy_field_forbidden" in codes
    assert "implementation_surface_test_missing" in codes


def test_plural_binding_fields_do_not_accept_singular_values(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mapped = mapping["surfaces"][0]
    mapped["test_refs"] = "tests/test_app.py#test_surface_smoke"
    mapped["receipt_refs"] = "receipt.txt#surface-pass"

    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    codes = {item["code"] for item in blocked["findings"]}

    assert blocked["status"] == "blocked"
    assert "implementation_surface_test_missing" in codes
    assert "implementation_surface_receipt_missing" in codes


def test_singleton_list_owner_cannot_be_treated_as_a_scalar_owner(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mapping["surfaces"][0]["owner"] = ["fixture-owner"]

    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    codes = {item["code"] for item in blocked["findings"]}

    assert blocked["status"] == "blocked"
    assert "implementation_surface_owner_ambiguous" in codes
    assert "implementation_surface_owner_missing" in codes


def test_non_test_anchor_cannot_be_used_as_test_coverage(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    (root / "tests" / "test_app.py").write_text(
        "def helper():\n    return True\n",
        encoding="utf-8",
    )
    mapping["surfaces"][0]["test_refs"] = ["tests/test_app.py#helper"]

    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)

    assert blocked["status"] == "blocked"
    assert "implementation_surface_orphan_test_reference" in {
        item["code"] for item in blocked["findings"]
    }


def test_surface_and_model_obligation_dispositions_must_agree(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    target = next(
        row for row in discovery["surfaces"] if row["surface_kind"] != "unreachable_or_unbound"
    )
    target_id = target["surface_id"]

    surface_typed_na = _complete_reverse_map(discovery)
    mapped_na = next(
        row for row in surface_typed_na["surfaces"] if row["surface_id"] == target_id
    )
    mapped_na.update(
        {
            "disposition": "not_applicable_proven",
            "proof_ref": "proof.txt#unbound-boundary",
            "not_applicable_reason": "the fixture surface is outside the product boundary",
        }
    )
    blocked_surface_na = audit_implementation_behavior_surface(
        root,
        surface_typed_na,
        discovery=discovery,
    )
    assert blocked_surface_na["status"] == "blocked"
    assert "implementation_surface_model_obligation_surface_disposition_mismatch" in {
        item["code"] for item in blocked_surface_na["findings"]
    }

    model_typed_na = _complete_reverse_map(discovery)
    obligation = next(
        row
        for row in model_typed_na["model_obligations"]
        if row["obligation_id"] == f"obligation:{target_id}"
    )
    obligation.update(
        {
            "disposition": "not_applicable_proven",
            "surface_ids": [],
            "proof_ref": "proof.txt#unbound-boundary",
            "reason": "the corresponding model obligation is outside the product boundary",
        }
    )
    blocked_model_na = audit_implementation_behavior_surface(
        root,
        model_typed_na,
        discovery=discovery,
    )
    assert blocked_model_na["status"] == "blocked"
    assert "implementation_surface_model_obligation_disposition_mismatch" in {
        item["code"] for item in blocked_model_na["findings"]
    }


def test_reverse_surface_two_way_contract_rejects_one_way_obligation_binding(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    target = next(
        row
        for row in discovery["surfaces"]
        if row["surface_kind"] != "unreachable_or_unbound"
    )
    target_id = target["surface_id"]
    obligation = next(
        row
        for row in mapping["model_obligations"]
        if row["obligation_id"] == f"obligation:{target_id}"
    )
    other = next(
        row
        for row in discovery["surfaces"]
        if row["surface_id"] != target_id
        and row["surface_kind"] != "unreachable_or_unbound"
    )

    # The surface still claims the obligation, but the reverse obligation row
    # points elsewhere.  A row-count comparison could appear complete; the
    # two-way contract must reject the asymmetric binding explicitly.
    obligation["surface_ids"] = [other["surface_id"]]

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=discovery,
    )

    assert blocked["status"] == "blocked"
    assert "implementation_surface_model_obligation_reverse_mismatch" in {
        item["code"] for item in blocked["findings"]
    }
    assert blocked["reverse_closure_complete"] is False


def test_new_command_api_and_ui_like_surface_cannot_hide_behind_old_mapping(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)

    # The independent observation is intentionally taken again after adding
    # production behavior.  A mapping-row count comparison alone could still
    # look superficially plausible; the new source observations must remain
    # visible as missing reverse rows and the map fingerprint must be stale.
    (root / "new_entry.py").write_text(
        """
import argparse

__all__ = ["new_api"]
API_SURFACE = {"new_api": ["new_api"]}

def new_api():
    return button("New")

def button(label):
    return label

def main():
    parser = argparse.ArgumentParser()
    parser.add_subparsers().add_parser("new-command")
    parser.add_argument("--new-ui")
    return parser.parse_args()
""".lstrip(),
        encoding="utf-8",
    )
    mutated_discovery = discover_implementation_behavior_surfaces(root)
    mutated_ids = {row["surface_id"] for row in mutated_discovery["surfaces"]}
    old_ids = {row["surface_id"] for row in discovery["surfaces"]}
    assert mutated_ids - old_ids
    assert any(row["surface_kind"] == "api" for row in mutated_discovery["surfaces"] if row["source_path"] == "new_entry.py")
    assert any(row["surface_kind"] == "cli_command" for row in mutated_discovery["surfaces"] if row["source_path"] == "new_entry.py")
    assert any(row["surface_kind"] == "ui_like_action" for row in mutated_discovery["surfaces"] if row["source_path"] == "new_entry.py")

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=mutated_discovery,
    )
    codes = {item["code"] for item in blocked["findings"]}
    assert blocked["status"] == "blocked"
    assert blocked["mapping_surface_count"] == len(mapping["surfaces"])
    assert blocked["discovered_surface_count"] == len(mutated_discovery["surfaces"])
    assert "implementation_surface_mapping_missing" in codes
    assert "implementation_surface_mapping_stale" in codes


def test_duplicate_primary_owner_claim_is_a_visible_blocker(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mapping["surfaces"][0]["owner"] = ["fixture-owner", "second-owner"]

    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    assert blocked["status"] == "blocked"
    assert "implementation_surface_primary_owner_duplicate" in {
        item["code"] for item in blocked["findings"]
    }
    assert mapping["surfaces"][0]["surface_id"] in blocked["duplicate_primary_owner_surface_ids"]


def test_governed_surface_missing_each_required_binding_cannot_pass(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    required_codes = {
        "intent_id": "implementation_surface_intent_mapping_missing",
        "model_owner_id": "implementation_surface_model_owner_missing",
        "model_obligation_ids": "implementation_surface_model_obligation_mapping_missing",
        "test_refs": "implementation_surface_test_missing",
        "owner": "implementation_surface_owner_missing",
        "receipt_refs": "implementation_surface_receipt_missing",
    }

    for field, expected_code in required_codes.items():
        mapping = _complete_reverse_map(discovery)
        mapping["surfaces"][0].pop(field)
        blocked = audit_implementation_behavior_surface(
            root,
            mapping,
            discovery=discovery,
        )
        assert blocked["status"] == "blocked", field
        assert expected_code in {item["code"] for item in blocked["findings"]}, field


def test_duplicate_discovery_surface_id_cannot_be_collapsed_into_a_pass(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    duplicated_discovery = json.loads(json.dumps(discovery))
    duplicated_discovery["surfaces"].append(dict(duplicated_discovery["surfaces"][0]))
    mapping = _complete_reverse_map(discovery)

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=duplicated_discovery,
    )
    assert blocked["status"] == "blocked"
    assert "implementation_surface_discovery_duplicate_id" in {
        item["code"] for item in blocked["findings"]
    }
    assert blocked["duplicate_discovery_surface_ids"]


def test_retired_surface_requires_current_proof_and_reason(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mapped = mapping["surfaces"][0]
    mapped["disposition"] = "retired_proven"

    missing = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    assert missing["status"] == "blocked"
    assert "implementation_surface_retirement_proof_missing" in {
        item["code"] for item in missing["findings"]
    }

    (root / "retirement-proof.txt").write_text(
        "surface-retired: no supported entrypoint\n",
        encoding="utf-8",
    )
    mapped["proof_ref"] = "retirement-proof.txt#surface-retired"
    mapped["reason"] = "the source surface is intentionally retired and has no supported entrypoint"
    obligation = next(
        row
        for row in mapping["model_obligations"]
        if row["obligation_id"] == f"obligation:{mapped['surface_id']}"
    )
    obligation.update(
        {
            "disposition": "retired_proven",
            "surface_ids": [],
            "proof_ref": "retirement-proof.txt#surface-retired",
            "reason": "the corresponding model obligation is retired with the source surface",
        }
    )
    accepted = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    assert accepted["status"] == "passed", accepted["findings"]


def test_reverse_surface_dispatch_set_is_a_current_closed_observation(tmp_path):
    (tmp_path / "caller.py").write_text(
        "def caller(value):\n    return shared(value)\n",
        encoding="utf-8",
    )
    (tmp_path / "left.py").write_text(
        "def shared(value):\n    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "right.py").write_text(
        "def shared(value):\n    return value\n",
        encoding="utf-8",
    )
    discovery = discover_implementation_behavior_surfaces(tmp_path)
    assert discovery["status"] == "passed"
    assert not discovery["findings"]
    edge = next(edge for edge in discovery["call_graph"] if edge["callee_name"] == "shared")
    assert edge["resolution"] == "resolved_static_dispatch"
    assert len(edge["resolved_surface_ids"]) == 2


def test_reverse_audit_accepts_complete_dispatch_merged_denominator_for_authoring(
    tmp_path,
):
    """A finite dispatch set is a closed call-graph observation."""

    (tmp_path / "caller.py").write_text(
        "def caller(value):\n    return shared(value)\n",
        encoding="utf-8",
    )
    (tmp_path / "left.py").write_text(
        "def shared(value):\n    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "right.py").write_text(
        "def shared(value):\n    return value\n",
        encoding="utf-8",
    )

    plan = plan_implementation_surface_shards(tmp_path, max_rows=10)
    shards = [
        discover_implementation_surface_shard(
            tmp_path,
            plan,
            shard["shard_id"],
        )
        for shard in plan["shards"]
    ]
    merged = merge_implementation_surface_shards(tmp_path, plan, shards)
    assert merged["status"] == "passed"
    assert not merged["findings"]

    audit = audit_implementation_behavior_surface(
        tmp_path,
        None,
        discovery=merged,
    )
    codes = {item["code"] for item in audit["findings"]}
    assert audit["status"] == "blocked"
    assert audit["discovery_observation_status"] == "terminal_pass"
    assert not audit["discovery_observation_findings"]
    assert "implementation_surface_mapping_missing" in codes
    assert "implementation_surface_discovery_not_current" not in codes


def test_reverse_model_obligation_requires_typed_proof_or_surface(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    (root / "model-proof.json").write_text('{"model-only":"proof"}\n', encoding="utf-8")
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mapping["model_obligations"].append(
        {
            "obligation_id": "obligation:unrealized",
            "disposition": "governed",
            "surface_ids": [],
        }
    )
    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    assert blocked["status"] == "blocked"
    assert "implementation_surface_model_obligation_surface_missing" in {
        item["code"] for item in blocked["findings"]
    }

    mapping = _complete_reverse_map(discovery)
    mapping["model_obligations"].append(
        {
            "obligation_id": "obligation:model-only",
            "disposition": "model_only_proven",
            "surface_ids": [],
            "proof_ref": "model-proof.json#model-only",
            "reason": "the model obligation is intentionally abstract and has no implementation surface",
        }
    )
    accepted = audit_implementation_behavior_surface(root, mapping, discovery=discovery)
    assert accepted["status"] == "passed", accepted["findings"]
    assert "obligation:model-only" not in accepted["unmapped_model_obligation_ids"]


def test_reverse_surface_discovery_can_be_planned_and_merged_without_truncation(tmp_path):
    (tmp_path / "a.py").write_text(
        "def alpha(value):\n    return beta(value)\n",
        encoding="utf-8",
    )
    (tmp_path / "b.py").write_text(
        "def beta(value):\n    return value\n",
        encoding="utf-8",
    )

    plan = plan_implementation_surface_shards(tmp_path, max_rows=3)
    assert plan["status"] == "planned", plan["findings"]
    assert len(plan["shards"]) == 2
    assert all(
        shard["estimated_surface_count"] <= 3 for shard in plan["shards"]
    )

    shards = [
        discover_implementation_surface_shard(tmp_path, plan, shard["shard_id"])
        for shard in plan["shards"]
    ]
    assert all(shard["status"] == "passed" for shard in shards)
    merged = merge_implementation_surface_shards(tmp_path, plan, shards)
    assert merged["status"] == "passed", merged["findings"]
    # Child shards each report a local unbound candidate. The merged verifier
    # removes those local projections and recomputes reachability across the
    # complete source boundary.  An unimported cross-file call remains
    # external/unknown, so both functions stay visible as unbound candidates.
    assert merged["surface_count"] == 6
    assert len(merged["source_paths"]) == 2
    assert len(merged["unbound_surface_ids"]) == 2
    assert all(
        row["surface_class"] in IMPLEMENTATION_SURFACE_CLASSES
        for row in merged["surfaces"]
    )

    missing = merge_implementation_surface_shards(tmp_path, plan, shards[:-1])
    assert missing["status"] == "blocked"
    assert "surface_shard_missing" in {
        row["code"] for row in missing["findings"]
    }

    tampered = json.loads(json.dumps(shards))
    tampered[0]["surfaces"][0]["source_fingerprint"] = "sha256:" + "0" * 64
    stale = merge_implementation_surface_shards(tmp_path, plan, tampered)
    assert stale["status"] == "blocked"
    assert "surface_shard_row_source_stale" in {
        row["code"] for row in stale["findings"]
    }


def test_reverse_surface_merge_blocks_when_source_boundary_changes_after_plan(tmp_path):
    """A frozen shard plan cannot silently absorb a newly added source file."""

    (tmp_path / "entry.py").write_text(
        "def entry(value):\n    return value\n",
        encoding="utf-8",
    )

    plan = plan_implementation_surface_shards(tmp_path, max_rows=10)
    assert plan["status"] == "planned", plan["findings"]
    shards = [
        discover_implementation_surface_shard(tmp_path, plan, shard["shard_id"])
        for shard in plan["shards"]
    ]

    # The source boundary is part of the plan identity.  Adding a production
    # file after planning must invalidate the old plan instead of letting the
    # merge treat the new implementation as absent or as historical data.
    (tmp_path / "new_entry.py").write_text(
        "def new_entry(value):\n    return value\n",
        encoding="utf-8",
    )
    merged = merge_implementation_surface_shards(tmp_path, plan, shards)
    assert merged["status"] == "blocked"
    assert "surface_shard_plan_stale" in {
        row["code"] for row in merged["findings"]
    }


def test_dynamic_and_plugin_surfaces_require_typed_na_or_blocked_disposition(
    tmp_path,
):
    (tmp_path / "plugin.py").write_text(
        """
import importlib

def load_plugin(name):
    return importlib.import_module(name)

def resolve_plugin(name):
    return getattr(importlib, name)

def register():
    return register_plugin("demo")
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "proof.txt").write_text(
        "dynamic-boundary plugin-boundary\n",
        encoding="utf-8",
    )
    (tmp_path / "receipt.txt").write_text(
        "surface-pass\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_plugin.py").write_text(
        "def test_plugin_boundary():\n    assert True\n",
        encoding="utf-8",
    )
    discovery = discover_implementation_behavior_surfaces(tmp_path)
    kinds = {row["surface_kind"] for row in discovery["surfaces"]}
    assert "dynamic" in kinds
    assert "plugin" in kinds

    obligations = []
    mapped = []
    for row in discovery["surfaces"]:
        surface_id = row["surface_id"]
        obligation_id = f"obligation:{surface_id}"
        obligations.append(
            {
                "obligation_id": obligation_id,
                "disposition": "governed",
                "surface_ids": [surface_id],
            }
        )
        mapped.append(
            {
                "surface_id": surface_id,
                "intent_id": f"intent:{surface_id}",
                "model_owner_id": f"model:{surface_id}",
                "model_obligation_ids": [obligation_id],
                "owner": "fixture-owner",
                "test_refs": ["tests/test_plugin.py#test_plugin_boundary"],
                "receipt_refs": ["receipt.txt#surface-pass"],
                "disposition": "governed",
            }
        )
    mapping = {
        "schema_version": IMPLEMENTATION_SURFACE_MAP_SCHEMA,
        "inventory_id": "fixture-dynamic-surface",
        "project_boundary": "fixture production source",
        "current_revision": "fixture-v1",
        "discovery_fingerprint": discovery["discovery_fingerprint"],
        "claim_boundary": "current dynamic/plugin contract closure",
        "model_obligations": obligations,
        "surfaces": mapped,
    }
    accepted = audit_implementation_behavior_surface(
        tmp_path,
        mapping,
        discovery=discovery,
    )
    assert accepted["status"] == "passed", accepted["findings"]

    governed_dynamic = json.loads(json.dumps(mapping))
    dynamic_ids = {
        item["surface_id"]
        for item in discovery["surfaces"]
        if item["surface_kind"] in {"dynamic", "plugin"}
    }
    for row in governed_dynamic["surfaces"]:
        if row["surface_id"] in dynamic_ids:
            row["disposition"] = "not_applicable_proven"
            row["proof_ref"] = "proof.txt#dynamic-boundary"
            row["not_applicable_reason"] = "legacy N/A requires current re-authoring"
    blocked = audit_implementation_behavior_surface(
        tmp_path,
        governed_dynamic,
        discovery=discovery,
    )
    assert blocked["status"] == "blocked"
    assert "implementation_surface_dynamic_current_disposition_required" in {
        row["code"] for row in blocked["findings"]
    }


def test_install_surface_class_is_source_observed(tmp_path):
    (tmp_path / "installer.py").write_text(
        """
from pathlib import Path

def install():
    Path('marker').write_text('ok')

def bootstrap():
    return install()
""".lstrip(),
        encoding="utf-8",
    )
    discovery = discover_implementation_behavior_surfaces(tmp_path)
    assert discovery["status"] == "passed", discovery["findings"]
    assert "install" in {row["surface_class"] for row in discovery["surfaces"]}
    assert any(row["surface_kind"] == "install" for row in discovery["surfaces"])


def test_reverse_surface_requires_terminal_receipt(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mapping["surfaces"][0].pop("receipt_refs")

    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)

    assert blocked["status"] == "blocked"
    assert "implementation_surface_receipt_missing" in {
        item["code"] for item in blocked["findings"]
    }


def test_empty_test_reference_is_not_coverage(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    (root / "tests" / "test_app.py").write_text(
        "def test_surface_smoke():\n    pass\n",
        encoding="utf-8",
    )

    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)

    assert blocked["status"] == "blocked"
    assert "implementation_surface_test_empty" in {
        item["code"] for item in blocked["findings"]
    }


def test_zero_mapping_count_can_never_pass(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mapping["surfaces"] = []

    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)

    assert blocked["status"] == "blocked"
    assert blocked["mapping_surface_count"] == 0
    assert "implementation_surface_mapping_zero" in {
        item["code"] for item in blocked["findings"]
    }


def test_internal_surface_requires_typed_proof(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mapped = mapping["surfaces"][0]
    mapped["disposition"] = "internal_proven"

    blocked = audit_implementation_behavior_surface(root, mapping, discovery=discovery)

    assert blocked["status"] == "blocked"
    assert "implementation_surface_internal_proof_missing" in {
        item["code"] for item in blocked["findings"]
    }


def test_duplicate_or_unknown_receipt_and_surface_class_are_blockers(tmp_path):
    root = _write_reverse_surface_fixture(tmp_path)
    discovery = discover_implementation_behavior_surfaces(root)
    mapping = _complete_reverse_map(discovery)
    mapping["surfaces"].append(dict(mapping["surfaces"][0]))
    mapping["surfaces"][1]["receipt_refs"] = ["receipt.txt#missing"]
    mutated_discovery = json.loads(json.dumps(discovery))
    mutated_discovery["surfaces"][0]["surface_class"] = "install"

    blocked = audit_implementation_behavior_surface(
        root,
        mapping,
        discovery=mutated_discovery,
    )
    codes = {item["code"] for item in blocked["findings"]}

    assert blocked["status"] == "blocked"
    assert "implementation_surface_mapping_duplicate_id" in codes
    assert "implementation_surface_orphan_receipt_reference" in codes
    assert "implementation_surface_class_mismatch" in codes
