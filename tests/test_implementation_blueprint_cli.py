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
    audit_implementation_surface_inventory,
    write_implementation_surface_inventory,
)
from flowguard.source_identity import source_file_fingerprint


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
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["decision"] == "block"
    assert payload["producer_count"] == 0
    assert payload["error"] == f"unknown operation: {retired_command}"
    assert payload["allowed_operations"] == ["read", "change", "release"]


def test_inventory_audit_is_read_only(tmp_path: Path):
    source = tmp_path / "src" / "retired.py"
    source.parent.mkdir(parents=True)
    source.write_text("# retired fixture\n", encoding="utf-8")
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
                content_fingerprint=source_file_fingerprint(source),
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

    report = audit_implementation_surface_inventory(path, root=tmp_path)
    assert report.ok
    assert report.status == "complete"
    assert path.read_bytes() == before
