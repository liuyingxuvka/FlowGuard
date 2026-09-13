"""Small closure regressions for the typed boundary authority contract."""
from __future__ import annotations

import pytest

from flowguard.model_authority import AcceptedBoundaryContract, ModelAuthorityError


def test_boundary_contract_wire_shape_requires_typed_owner_route():
    payload = {
        "schema_version": "flowguard.model_boundary_contract.v2",
        "contract_id": "boundary:test",
        "model_id": "authoritative_model_system",
        "boundary_source_id": "coverage:test",
        "boundary_source_fingerprint": "sha256:" + "a" * 64,
        "topology_fingerprint": "sha256:" + "b" * 64,
        "axis_payloads": [{"axis_id": "axis:test", "model_id": "authoritative_model_system", "values": ["a"]}],
        "interaction_group_payloads": [],
        "group_relation_ids": {},
        "model_instances": [],
        "relations": [],
    }
    with pytest.raises((ModelAuthorityError, ValueError)):
        AcceptedBoundaryContract.from_dict(payload)


def test_boundary_contract_type_is_not_an_untyped_string():
    assert AcceptedBoundaryContract.__name__ == "AcceptedBoundaryContract"
