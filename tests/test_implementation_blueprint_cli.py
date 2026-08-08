from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.implementation_inventory import (
    ImplementationFileDisposition,
    ImplementationSurfaceInventory,
    SoftwareBoundary,
    write_implementation_surface_inventory,
)


ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "flowguard", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize("retired_command", ("model-blueprint-check", "model-blueprint-export"))
def test_raw_manifest_blueprint_authority_is_not_a_public_command(
    retired_command: str,
) -> None:
    result = _run(retired_command)

    assert result.returncode == 2
    assert "invalid choice" in result.stderr
    assert "project-blueprint-audit" in result.stderr
    assert "project-blueprint-export" in result.stderr


def test_inventory_audit_is_read_only(tmp_path: Path):
    inventory = ImplementationSurfaceInventory(
        inventory_id="inventory:read-only",
        boundary=SoftwareBoundary(
            boundary_id="boundary:demo",
            subject_revision="revision:one",
            production_patterns=("src/**",),
        ),
        manifest_fingerprint="fp:manifest",
        file_dispositions=(
            ImplementationFileDisposition(
                path="src/retired.py",
                category="production",
                content_fingerprint="fp:file",
                disposition="dead_retire",
                reason="retired from the current implementation boundary",
            ),
        ),
        surfaces=(),
        findings=(),
        claim_boundary="structural inventory only",
    )
    path = write_implementation_surface_inventory(inventory, tmp_path / "inventory.json")
    before = path.read_bytes()

    result = _run(
        "implementation-inventory-audit",
        "--inventory",
        str(path),
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["status"] == "complete"
    assert path.read_bytes() == before
