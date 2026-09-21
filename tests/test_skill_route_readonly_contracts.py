"""Current single-skill/read-path contract checks.

The public distribution has one ``flowguard`` skill.  Domain material remains
on-demand reference content and the only public lifecycle operations are
``read``, ``change``, and ``release``.  These checks protect that boundary and
the zero-producer read path without treating retired satellite skills as
current authorities.
"""

from pathlib import Path
import re

from flowguard.skill_suite import FLOWGUARD_SKILL_ROOT, validate_skill_suite


ROOT = Path(__file__).resolve().parents[1]


def _route_dirs() -> tuple[Path, ...]:
    inventory = validate_skill_suite(ROOT)
    assert inventory.ok, inventory.to_dict()
    assert inventory.declared_member_ids == ("flowguard",)
    return tuple(ROOT / FLOWGUARD_SKILL_ROOT / member_id for member_id in inventory.declared_member_ids)


def test_single_public_skill_has_lazy_reference_contracts():
    for route_dir in _route_dirs():
        skill = route_dir / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        assert "route" in text.lower(), route_dir.name
        assert "selected" in text.lower() or "admission" in text.lower(), route_dir.name
        refs = sorted(
            set(re.findall(r"`(references/[^`]+?\.md)`", text))
        )
        assert refs, route_dir.name
        for relative in refs:
            assert (route_dir / relative).is_file(), (route_dir.name, relative)


def test_shared_contract_declares_lifecycle_zero_producer_and_stop_policy():
    kernel = (ROOT / ".agents/skills/flowguard/SKILL.md").read_text(encoding="utf-8")
    shared = (ROOT / ".agents/skills/flowguard/references/route_execution_contract.md").read_text(
        encoding="utf-8"
    )
    for marker in ("one public skill", "read", "change", "release", "No mode/fallback"):
        assert marker in kernel, marker
    for marker in (
        "Domain folders under `references/domains/` are on-demand reference material",
        "There is no compatibility alias, fallback route, alternate reader",
        "does not reserve a lease",
        "producer count remains zero",
        "non-authoritative",
        "release-excluded",
        "Cleanup is a",
        "source, model, contract, toolchain, or environment drift",
    ):
        assert marker in shared, marker


def test_bcl_uses_singular_path_authority_and_rejects_legacy_plural():
    protocol = (
        ROOT
        / ".agents/skills/flowguard/references/domains/behavior-commitment-ledger/references/behavior_commitment_ledger_protocol.md"
    ).read_text(encoding="utf-8")
    assert "path_sensitive=true" in protocol
    assert "primary_path_id" in protocol
    assert "legacy plural `primary_path_ids` input is retired and rejected" in protocol
    assert "Accept legacy `primary_path_ids` input" not in protocol


def test_conditional_details_are_split_and_referenced_only_on_trigger():
    architecture_root = ROOT / ".agents/skills/flowguard/references/domains/architecture-reduction"
    architecture_main = (
        architecture_root / "references/architecture_reduction_protocol.md"
    ).read_text(encoding="utf-8")
    architecture_proof = (
        architecture_root / "references/architecture_reduction_proof_details.md"
    ).read_text(encoding="utf-8")
    architecture_hazards = (
        architecture_root / "references/architecture_reduction_hazard_details.md"
    ).read_text(encoding="utf-8")
    assert "Conditional proof details" in architecture_main
    assert "Conditional hazard and path details" in architecture_main
    assert "## Observable Contract" not in architecture_main
    assert "## Required Hazards" not in architecture_main
    assert "## Observable Contract" in architecture_proof
    assert "## Required Hazards" in architecture_hazards
    assert "## Bounded path preference" in architecture_hazards

    preflight_root = ROOT / ".agents/skills/flowguard/references/domains/existing-model-preflight"
    preflight_main = (
        preflight_root / "references/existing_model_preflight_protocol.md"
    ).read_text(encoding="utf-8")
    preflight_details = (
        preflight_root / "references/existing_model_preflight_change_details.md"
    ).read_text(encoding="utf-8")
    assert "Conditional detailed preflight" in preflight_main
    assert "## Path-Quality Lookup And Handoff" not in preflight_main
    assert "## Required Hazards" not in preflight_main
    for heading in (
        "## Path-Quality Lookup And Handoff",
        "## Required Hazards",
        "## Executable composition handoff",
        "## Maturation Handoff Boundary",
        "## Blueprint Layer Contribution",
    ):
        assert heading in preflight_details, heading
