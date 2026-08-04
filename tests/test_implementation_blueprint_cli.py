from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from flowguard.implementation_blueprint import (
    BlueprintResourceReference,
    ModelImplementationBinding,
    OracleReference,
    SemanticSpecReference,
    SoftwareBlueprintManifest,
    review_model_implementation_bindings,
)
from flowguard.implementation_inventory import (
    ImplementationFileDisposition,
    ImplementationSurface,
    ImplementationSurfaceInventory,
    SoftwareBoundary,
    write_implementation_surface_inventory,
)


ROOT = Path(__file__).resolve().parents[1]


def _artifacts(root: Path) -> tuple[Path, Path, Path, SoftwareBlueprintManifest]:
    semantic = SemanticSpecReference(
        semantic_spec_id="spec:save",
        owner_id="owner:model",
        artifact_id="artifact:spec",
        artifact_fingerprint="fp:spec",
        covered_model_element_ids=("model:save",),
        covered_dimensions=("input", "output", "error"),
        semantics=(
            ("input", "accept a declared save request"),
            ("output", "return the declared save result"),
            ("error", "reject invalid requests without success"),
        ),
        provenance_fingerprints=(("requirements", "fp:requirements"),),
    )
    oracle = OracleReference(
        oracle_id="oracle:save",
        owner_id="owner:test",
        artifact_id="artifact:oracle",
        artifact_fingerprint="fp:oracle",
        covered_model_element_ids=("model:save",),
        covered_dimensions=("input", "output", "error"),
        semantics=(
            ("input", "exercise valid and invalid requests"),
            ("output", "compare with the declared result"),
            ("error", "require invalid requests to remain non-success"),
        ),
    )
    binding = ModelImplementationBinding(
        binding_id="binding:save",
        model_element_id="model:save",
        implementation_surface_id="surface:save",
        relation_kind="implements",
        owner_contract_id="contract:save",
        semantic_spec_ids=(semantic.semantic_spec_id,),
        oracle_ids=(oracle.oracle_id,),
        test_evidence_ids=("test:save",),
        test_evidence_fingerprints=(("test:save", "fp:test:save"),),
        implementation_fingerprint="fp:surface:save",
    )
    inventory = ImplementationSurfaceInventory(
        inventory_id="inventory:one",
        boundary=SoftwareBoundary(
            boundary_id="boundary:demo",
            subject_revision="revision:one",
            production_patterns=("src/**",),
        ),
        manifest_fingerprint="fp:manifest",
        file_dispositions=(
            ImplementationFileDisposition(
                path="src/save.py",
                category="production",
                content_fingerprint="fp:surface:save",
                disposition="model_implementation",
                reason="current implementation owner",
            ),
        ),
        surfaces=(
            ImplementationSurface(
                surface_id="surface:save",
                path="src/save.py",
                symbol="save",
                surface_kind="entrypoint",
                parent_surface_id="",
                content_fingerprint="fp:surface:save",
                structure_fingerprint="fp:structure:save",
                disposition="model_implementation",
                roles=("entrypoint",),
            ),
        ),
        findings=(),
        claim_boundary="structural inventory only",
    )
    report = review_model_implementation_bindings(
        inventory,
        required_model_element_ids=("model:save",),
        bindings=(binding,),
        semantic_specs=(semantic,),
        oracles=(oracle,),
        current_test_evidence_fingerprints={"test:save": "fp:test:save"},
    )
    resource = BlueprintResourceReference(
        resource_id="resource:runtime",
        kind="runtime",
        owner_id="owner:runtime",
        artifact_id="artifact:runtime",
        purpose="execute the declared target",
        lifecycle_role="runtime_dependency",
        artifact_fingerprint="fp:runtime",
        semantics=(("requirement", "provide the declared runtime capability"),),
    )
    manifest = SoftwareBlueprintManifest(
        blueprint_id="blueprint:demo",
        observed_snapshot_id="snapshot:current",
        observed_snapshot_fingerprint="fp:snapshot",
        inventory_id=report.inventory_id,
        inventory_fingerprint=report.inventory_fingerprint,
        binding_report_id="binding-report:current",
        binding_report_fingerprint=report.fingerprint,
        semantic_mesh_id="mesh:current",
        semantic_mesh_fingerprint="fp:mesh",
        test_inventory_id="test-inventory:current",
        test_inventory_fingerprint="fp:test-inventory",
        model_test_alignment_report_id="alignment:current",
        model_test_alignment_report_fingerprint="fp:alignment",
        portable_owner_fingerprints=(("portable:system", "fp:portable"),),
        resources=(resource,),
        oracles=(oracle,),
        required_resource_ids=(resource.resource_id,),
        required_resource_kinds=(resource.kind,),
        required_oracle_ids=(oracle.oracle_id,),
    )
    manifest_path = root / "blueprint.json"
    report_path = root / "bindings.json"
    inventory_path = root / "inventory.json"
    manifest_path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    report_path.write_text(json.dumps(report.to_dict()), encoding="utf-8")
    write_implementation_surface_inventory(inventory, inventory_path)
    return manifest_path, report_path, inventory_path, manifest


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "flowguard", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _current_args() -> tuple[str, ...]:
    return (
        "--observed-snapshot-fingerprint",
        "fp:snapshot",
        "--semantic-mesh-fingerprint",
        "fp:mesh",
        "--test-inventory-fingerprint",
        "fp:test-inventory",
        "--model-test-alignment-report-fingerprint",
        "fp:alignment",
        "--portable-owner-fingerprints",
        '{"portable:system":"fp:portable"}',
        "--resource-fingerprints",
        '{"resource:runtime":"fp:runtime"}',
        "--oracle-fingerprints",
        '{"oracle:save":"fp:oracle"}',
        "--json",
    )


def test_read_only_blueprint_check_keeps_empirical_reconstruction_not_run(tmp_path: Path):
    manifest_path, report_path, inventory_path, _manifest = _artifacts(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    result = _run(
        "model-blueprint-check",
        "--manifest",
        str(manifest_path),
        "--binding-report",
        str(report_path),
        "--inventory",
        str(inventory_path),
        *_current_args(),
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["static_status"] == "complete"
    assert payload["empirical_status"] == "not_run"
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before


def test_explicit_export_writes_deterministic_verified_projection(tmp_path: Path):
    manifest_path, report_path, inventory_path, _manifest = _artifacts(tmp_path)
    output = tmp_path / "export"
    command = (
        "model-blueprint-export",
        "--manifest",
        str(manifest_path),
        "--binding-report",
        str(report_path),
        "--inventory",
        str(inventory_path),
        "--output",
        str(output),
        *_current_args(),
    )

    first = _run(*command)
    assert first.returncode == 0, first.stderr + first.stdout
    first_payload = json.loads(first.stdout)
    first_bytes = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*.json")
    }
    second = _run(*command)
    assert second.returncode == 0, second.stderr + second.stdout
    assert json.loads(second.stdout)["projection_fingerprint"] == first_payload[
        "projection_fingerprint"
    ]
    assert {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*.json")
    } == first_bytes


def test_require_reconstruction_never_runs_missing_owner(tmp_path: Path):
    manifest_path, report_path, inventory_path, _manifest = _artifacts(tmp_path)
    result = _run(
        "model-blueprint-check",
        "--manifest",
        str(manifest_path),
        "--binding-report",
        str(report_path),
        "--inventory",
        str(inventory_path),
        "--require-reconstruction",
        *_current_args(),
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["static_status"] == "complete"
    assert payload["empirical_status"] == "not_run"


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
