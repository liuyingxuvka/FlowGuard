"""Shared ownership vocabulary for the mesh capabilities.

Plain string constants used by model-mesh (hierarchy) and the structure-split
review.  Keeping them here lets each capability import four strings without
loading the other.
"""

from __future__ import annotations

OWNERSHIP_CHILD = "child"
OWNERSHIP_PARENT = "parent"
OWNERSHIP_READ_ONLY = "read_only"
OWNERSHIP_SHARED_KERNEL = "shared_kernel"

__all__ = [
    "OWNERSHIP_CHILD",
    "OWNERSHIP_PARENT",
    "OWNERSHIP_READ_ONLY",
    "OWNERSHIP_SHARED_KERNEL",
]
