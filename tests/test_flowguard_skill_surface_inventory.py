import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUITE_MAP = ROOT / ".skillguard" / "flowguard-suite" / "suite-map.json"
SKILLS = tuple(
    row["name"]
    for row in json.loads(SUITE_MAP.read_text(encoding="utf-8"))["included_skills"]
)


def test_every_flowguard_skill_has_current_two_way_surface_inventory_and_map():
    for skill_id in SKILLS:
        control = ROOT / ".agents" / "skills" / skill_id / ".skillguard"
        inventory = json.loads((control / "surface-inventory.json").read_text(encoding="utf-8"))
        semantic_map = json.loads((control / "surface-semantic-map.json").read_text(encoding="utf-8"))
        full_ids = set(inventory["full_surface_ids"])
        rows = {row["surface_id"]: row for row in inventory["full_surfaces"]}
        obligations = {row["obligation_id"]: row for row in inventory["model_obligations"]}
        assert inventory["target_skill_id"] == skill_id
        assert full_ids == set(inventory["observed_surface_ids"]) == set(rows)
        assert set(inventory["current_obligation_ids"]) == set(obligations)
        assert semantic_map["source_discovery_fingerprint"] == inventory["full_discovery_fingerprint"]
        assert set(semantic_map["current_obligation_ids"]) == set(obligations)
        for surface_id, row in rows.items():
            refs = set(row["model_obligation_ids"])
            assert refs
            for obligation_id in refs:
                assert surface_id in set(obligations[obligation_id]["surface_ids"])
        for obligation_id, row in obligations.items():
            assert row["disposition"] == "governed"
            assert row["surface_ids"]
            for surface_id in row["surface_ids"]:
                assert obligation_id in set(rows[surface_id]["model_obligation_ids"])
