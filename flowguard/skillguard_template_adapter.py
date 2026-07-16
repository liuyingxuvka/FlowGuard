"""Target-owned projection from FlowGuard file templates to SkillGuard.

FlowGuard remains the only owner of template factories and route
applicability.  The returned projection is neutral interchange data; it does
not let SkillGuard infer a FlowGuard route or validate a FlowGuard model.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from . import templates as native_templates
from .__main__ import FILE_TEMPLATE_COMMANDS
from .risk_templates import builtin_risk_templates
from .template_packs import (
    HardPredicate,
    TemplatePack,
    TemplatePackManifest,
    seal_template_pack_manifest,
    select_template_packs,
    validate_template_pack_manifest,
)


PROJECTION_SCHEMA = "skillguard.target_template_projection.v1"
FAMILY_ID = "flowguard"
NATIVE_OWNER_ID = "flowguard.file-template-router"
CATALOG_ID = "flowguard.file-template-packs"
BASE_TEMPLATE_ID = "flowguard.template.base-project"
BASE_ROUTE_ID = "route:flowguard-template:base"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _identity(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _text_identity(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _route_id(template_name: str) -> str:
    return f"route:flowguard-template:{template_name.replace('_', '-')}"


def _output_key(template_name: str) -> str:
    return "files_" + template_name.replace("-", "_")


def _native_manifest() -> tuple[TemplatePackManifest, dict[str, dict[str, Any]]]:
    metadata: dict[str, dict[str, Any]] = {}
    packs: list[TemplatePack] = []
    base_files = native_templates.project_template_files()
    base_value = tuple({"path": item.path, "content": item.content} for item in base_files)
    packs.append(
        TemplatePack(
            template_id=BASE_TEMPLATE_ID,
            version="1",
            base=True,
            owned_fields=("files_base_project",),
            template={"files_base_project": base_value},
        )
    )
    metadata[BASE_TEMPLATE_ID] = {
        "route_id": BASE_ROUTE_ID,
        "template_name": "project",
        "factory_name": "project_template_files",
        "builder_entrypoint": "flowguard.templates:project_template_files",
        "files": base_files,
    }
    for index, command in enumerate(FILE_TEMPLATE_COMMANDS, start=1):
        template_id = f"flowguard.template.{command.template_name.replace('_', '-')}"
        if template_id == BASE_TEMPLATE_ID:
            continue
        factory = getattr(native_templates, command.factory_name)
        files = factory()
        route_id = _route_id(command.template_name)
        output_key = _output_key(command.template_name)
        packs.append(
            TemplatePack(
                template_id=template_id,
                version="1",
                priority=index,
                predicates=(HardPredicate("route_id", "equals", route_id),),
                composable=False,
                owned_fields=(output_key,),
                template={
                    output_key: tuple(
                        {"path": item.path, "content": item.content}
                        for item in files
                    )
                },
            )
        )
        metadata[template_id] = {
            "route_id": route_id,
            "template_name": command.template_name,
            "factory_name": command.factory_name,
            "builder_entrypoint": f"flowguard.templates:{command.factory_name}",
            "files": files,
        }
    next_priority = len(packs) + 1
    for offset, risk_template in enumerate(builtin_risk_templates()):
        template_id = f"flowguard.risk.{risk_template.template_id.replace('_', '-')}"
        route_id = f"route:flowguard-risk-template:{risk_template.template_id.replace('_', '-')}"
        output_key = "risk_template_" + risk_template.template_id.replace("-", "_")
        content = json.dumps(risk_template.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        files = (
            native_templates.TemplateFile(
                f"risk_templates/{risk_template.template_id}.json",
                content,
            ),
        )
        packs.append(
            TemplatePack(
                template_id=template_id,
                version="1",
                priority=next_priority + offset,
                predicates=(HardPredicate("route_id", "equals", route_id),),
                composable=False,
                owned_fields=(output_key,),
                template={output_key: risk_template.to_dict()},
            )
        )
        metadata[template_id] = {
            "route_id": route_id,
            "template_name": risk_template.template_id,
            "factory_name": f"risk-template-{risk_template.template_id}",
            "builder_entrypoint": (
                "flowguard.risk_templates:builtin_risk_templates#"
                + risk_template.template_id
            ),
            "files": files,
        }
    manifest = seal_template_pack_manifest(
        TemplatePackManifest(
            manifest_id=CATALOG_ID,
            version="1",
            templates=tuple(packs),
        )
    )
    validation = validate_template_pack_manifest(manifest)
    if not validation.ok:
        raise ValueError("invalid FlowGuard template manifest: " + "; ".join(validation.findings))
    return manifest, metadata


def _parameter_schema(required_parameters: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {item: {} for item in required_parameters},
        "required": list(required_parameters),
        "additionalProperties": False,
    }


def build_skillguard_template_projection(
    *,
    target_id: str,
    route_id: str,
    request_fingerprint: str,
) -> dict[str, Any]:
    """Return a complete projection after exact native FlowGuard selection."""

    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("target_id must be a non-empty string")
    if not SHA256_RE.fullmatch(str(request_fingerprint)):
        raise ValueError("request_fingerprint must be a lowercase sha256 identity")
    manifest, metadata = _native_manifest()
    declared_routes = {str(item["route_id"]) for item in metadata.values()}
    if route_id not in declared_routes:
        raise ValueError(f"unknown FlowGuard template route: {route_id}")
    selection = select_template_packs(manifest, {"route_id": route_id})
    if selection.disposition not in {"selected", "base_selected"}:
        raise ValueError(f"FlowGuard native template selection blocked: {selection.disposition}")
    matched = set(selection.matched_template_ids)
    selected = set(selection.selected_template_ids)
    adapter_identity = _identity(
        {
            "adapter": Path(__file__).read_text(encoding="utf-8"),
            "native_manifest_digest": manifest.manifest_digest,
        }
    )
    templates: list[dict[str, Any]] = []
    applicability: list[dict[str, Any]] = []
    for order, pack in enumerate(manifest.templates):
        info = metadata[pack.template_id]
        is_base = bool(pack.base)
        failure_ids = (
            f"failure:{pack.template_id}:native-selection-stale",
            f"failure:{pack.template_id}:native-validation",
        )
        artifact_rows = [
            {
                "artifact_id": f"artifact:{pack.template_id}:{index}",
                "path_template": item.path,
                "content_template_hash": _text_identity(item.content),
            }
            for index, item in enumerate(info["files"], start=1)
        ]
        templates.append(
            {
                "schema_version": "skillguard.template_manifest.v1",
                "template_id": pack.template_id,
                "revision": pack.version,
                "template_kind": "base" if is_base else "profile",
                "native_owner_id": NATIVE_OWNER_ID,
                "family_id": FAMILY_ID,
                "route_ids": [str(info["route_id"])],
                "applicability_predicate_ids": [
                    "predicate:flowguard-validated-base"
                    if is_base
                    else f"predicate:flowguard-route:{info['route_id']}"
                ],
                "forbidden_condition_ids": [],
                "dependencies": [],
                "compatible_with": [],
                "conflicts_with": [],
                "dominates_template_ids": [],
                "composable": False,
                "composition_order": order,
                "is_validated_base": is_base,
                "field_ownership": list(pack.owned_fields),
                "parameter_schema": _parameter_schema(pack.required_parameters),
                "artifacts": artifact_rows,
                "builder": {
                    "builder_id": f"builder:flowguard:{info['factory_name']}",
                    "entrypoint": str(info["builder_entrypoint"]),
                    "content_hash": _identity(
                        {
                            "factory": info["factory_name"],
                            "artifacts": artifact_rows,
                            "native_manifest_digest": manifest.manifest_digest,
                        }
                    ),
                },
                "validators": [
                    {
                        "validator_id": "validator:flowguard:template-pack-native",
                        "check_id": "check:flowguard:template-packs",
                        "evidence_domain": "flowguard-template-pack",
                        "content_hash": adapter_identity,
                    }
                ],
                "prompt_fragments": [],
                "protected_failure_ids": list(failure_ids),
                "fixtures": {
                    "known_good_ids": [f"fixture:flowguard:good:{pack.template_id}"],
                    "known_bad_by_failure": {
                        failure_id: [f"fixture:flowguard:bad:{failure_id}"]
                        for failure_id in failure_ids
                    },
                    "ambiguity_ids": ["fixture:flowguard:ambiguous-template-selection"],
                    "stale_ids": ["fixture:flowguard:stale-native-manifest"],
                },
                "claim_boundary": (
                    "FlowGuard owns route meaning, model fields, generated files, and native validation; "
                    "the projection is not model or completion evidence."
                ),
            }
        )
        eligible = is_base or pack.template_id in matched
        applicability.append(
            {
                "template_id": pack.template_id,
                "eligible": eligible,
                "predicate_evidence_ids": [
                    f"evidence:flowguard:base-current:{manifest.manifest_digest}"
                    if is_base
                    else f"evidence:flowguard:native-match:{selection.selection_digest}:{pack.template_id}"
                ],
                "forbidden_clearance_evidence_ids": [],
                "reasons": [] if eligible else [f"native_route_not_applicable:{route_id}"],
            }
        )
    if selected != ({BASE_TEMPLATE_ID} if route_id == BASE_ROUTE_ID else matched):
        raise ValueError("FlowGuard native selection receipt does not match projected applicability")
    return {
        "schema_version": PROJECTION_SCHEMA,
        "target_id": target_id.strip(),
        "native_owner_id": NATIVE_OWNER_ID,
        "family_id": FAMILY_ID,
        "route_id": route_id,
        "request_fingerprint": request_fingerprint,
        "catalog": {
            "schema_version": "skillguard.template_catalog.v1",
            "catalog_id": CATALOG_ID,
            "revision": manifest.version,
            "native_owner_id": NATIVE_OWNER_ID,
            "family_id": FAMILY_ID,
            "base_template_id": BASE_TEMPLATE_ID,
            "templates": templates,
            "harvest_policy": {
                "required": True,
                "allowed_dispositions": ["reused", "created", "not_harvestable"],
            },
            "claim_boundary": (
                "FlowGuard file templates are starter artifacts only; current executable models and checks "
                "remain required for behavior, closure, release, or installation claims."
            ),
        },
        "applicability_results": applicability,
        "claim_boundary": (
            "The FlowGuard router and native manifest produced this candidate accounting. "
            "SkillGuard may seal and supervise it but cannot select FlowGuard semantics."
        ),
    }


__all__ = [
    "BASE_ROUTE_ID",
    "BASE_TEMPLATE_ID",
    "CATALOG_ID",
    "FAMILY_ID",
    "NATIVE_OWNER_ID",
    "PROJECTION_SCHEMA",
    "build_skillguard_template_projection",
]
