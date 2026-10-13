"""Shared ownership and evidence-tier vocabulary for the mesh capabilities.

Plain string constants used by model-mesh (hierarchy), structure-mesh and
test-mesh.  Keeping them here lets each capability import ten strings without
loading the others.
"""

from __future__ import annotations

OWNERSHIP_CHILD = "child"
OWNERSHIP_PARENT = "parent"
OWNERSHIP_READ_ONLY = "read_only"
OWNERSHIP_SHARED_KERNEL = "shared_kernel"

EVIDENCE_CANDIDATE_ONLY = "candidate_only"
EVIDENCE_ABSTRACT_GREEN = "abstract_green"
EVIDENCE_HAZARD_GREEN = "hazard_green"
EVIDENCE_LIVE_CURRENT_GREEN = "live_current_green"
EVIDENCE_CONFORMANCE_GREEN = "conformance_green"
EVIDENCE_MESH_GREEN = "mesh_green"

__all__ = [
    "EVIDENCE_ABSTRACT_GREEN",
    "EVIDENCE_CANDIDATE_ONLY",
    "EVIDENCE_CONFORMANCE_GREEN",
    "EVIDENCE_HAZARD_GREEN",
    "EVIDENCE_LIVE_CURRENT_GREEN",
    "EVIDENCE_MESH_GREEN",
    "OWNERSHIP_CHILD",
    "OWNERSHIP_PARENT",
    "OWNERSHIP_READ_ONLY",
    "OWNERSHIP_SHARED_KERNEL",
]
