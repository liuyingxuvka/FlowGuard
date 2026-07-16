"""Validated, digest-bound template-pack selection and instantiation.

This module is intentionally independent from the public template facade and
the risk-template library.  It provides one current manifest schema, a bounded
predicate language, explicit zero/one/many selection, and immutable receipts.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence


TEMPLATE_PACK_MANIFEST_SCHEMA = "flowguard.template-pack-manifest.v1"
TEMPLATE_PACK_SELECTION_RECEIPT_SCHEMA = "flowguard.template-pack-selection-receipt.v1"
TEMPLATE_PACK_INSTANCE_RECEIPT_SCHEMA = "flowguard.template-pack-instance-receipt.v1"

PREDICATE_OPERATORS = ("equals", "one_of", "contains", "contains_all", "exists")
SELECTABLE_DISPOSITIONS = ("base_selected", "selected", "composed")
SELECTION_DISPOSITIONS = SELECTABLE_DISPOSITIONS + (
    "no_match",
    "conflict",
    "invalid_manifest",
)
INSTANCE_STATUSES = ("instantiated", "blocked")

_PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.-]*)\}")
_FULL_PLACEHOLDER_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_.-]*)\}$")
_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            frozen[key] = _freeze_json(item)
        return MappingProxyType(dict(sorted(frozen.items())))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if isinstance(value, _JSON_SCALAR_TYPES):
        # Reject NaN and infinities through the same canonical JSON boundary.
        json.dumps(value, allow_nan=False)
        return value
    raise TypeError(f"value is not JSON-compatible: {type(value).__name__}")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _thaw_json(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _digest(value: Any) -> str:
    encoded = _canonical_json(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _json_equal(left: Any, right: Any) -> bool:
    return _canonical_json(left) == _canonical_json(right)


def _tuple_of_text(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value).strip() for value in values)


def _json_mapping(value: Mapping[str, Any], *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a JSON object")
    frozen = _freeze_json(value)
    if not isinstance(frozen, Mapping):  # pragma: no cover - guarded above
        raise TypeError(f"{label} must be a JSON object")
    return frozen


def _text_duplicates(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def _placeholder_names(value: Any) -> tuple[str, ...]:
    names: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for nested in item.values():
                visit(nested)
        elif isinstance(item, tuple):
            for nested in item:
                visit(nested)
        elif isinstance(item, str):
            names.update(_PLACEHOLDER_PATTERN.findall(item))

    visit(value)
    return tuple(sorted(names))


@dataclass(frozen=True)
class HardPredicate:
    """One bounded predicate over a top-level selection-context key."""

    key: str
    operator: str
    expected: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", str(self.key).strip())
        object.__setattr__(self, "operator", str(self.operator).strip().lower())
        object.__setattr__(self, "expected", _freeze_json(self.expected))

    def to_dict(self) -> dict[str, Any]:
        expected = _thaw_json(self.expected)
        if self.operator in ("one_of", "contains_all") and isinstance(expected, list):
            expected = sorted(expected, key=_canonical_json)
        return {
            "key": self.key,
            "operator": self.operator,
            "expected": expected,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HardPredicate":
        return cls(
            key=str(data.get("key", "")),
            operator=str(data.get("operator", "")),
            expected=data.get("expected"),
        )


@dataclass(frozen=True)
class TemplatePack:
    """One selectable template entry and its exact output ownership."""

    template_id: str
    version: str
    template: Mapping[str, Any]
    predicates: tuple[HardPredicate, ...] = ()
    priority: int = 0
    base: bool = False
    composable: bool = False
    owned_fields: tuple[str, ...] = ()
    required_parameters: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "template_id", str(self.template_id).strip())
        object.__setattr__(self, "version", str(self.version).strip())
        object.__setattr__(self, "template", _json_mapping(self.template, label="template"))
        object.__setattr__(
            self,
            "predicates",
            tuple(
                item if isinstance(item, HardPredicate) else HardPredicate.from_dict(item)
                if isinstance(item, Mapping)
                else item
                for item in self.predicates
            ),
        )
        object.__setattr__(self, "owned_fields", _tuple_of_text(self.owned_fields))
        object.__setattr__(self, "required_parameters", _tuple_of_text(self.required_parameters))

    def to_dict(self) -> dict[str, Any]:
        predicates = sorted(
            (predicate.to_dict() for predicate in self.predicates),
            key=_canonical_json,
        )
        return {
            "template_id": self.template_id,
            "version": self.version,
            "priority": self.priority,
            "base": self.base,
            "composable": self.composable,
            "predicates": predicates,
            "owned_fields": sorted(self.owned_fields),
            "required_parameters": sorted(self.required_parameters),
            "template": _thaw_json(self.template),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TemplatePack":
        predicates = data.get("predicates", ())
        if not isinstance(predicates, Sequence) or isinstance(predicates, (str, bytes)):
            raise TypeError("predicates must be a sequence")
        return cls(
            template_id=str(data.get("template_id", "")),
            version=str(data.get("version", "")),
            priority=data.get("priority", 0),
            base=data.get("base", False),
            composable=data.get("composable", False),
            predicates=tuple(
                item if isinstance(item, HardPredicate) else HardPredicate.from_dict(item)
                for item in predicates
            ),
            owned_fields=tuple(data.get("owned_fields", ())),
            required_parameters=tuple(data.get("required_parameters", ())),
            template=data.get("template", {}),
        )


@dataclass(frozen=True)
class TemplatePackManifest:
    """The sole current template-pack manifest authority."""

    manifest_id: str
    version: str
    templates: tuple[TemplatePack, ...]
    schema_version: str = TEMPLATE_PACK_MANIFEST_SCHEMA
    manifest_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_id", str(self.manifest_id).strip())
        object.__setattr__(self, "version", str(self.version).strip())
        object.__setattr__(
            self,
            "templates",
            tuple(
                item if isinstance(item, TemplatePack) else TemplatePack.from_dict(item)
                if isinstance(item, Mapping)
                else item
                for item in self.templates
            ),
        )
        object.__setattr__(self, "schema_version", str(self.schema_version).strip())
        object.__setattr__(self, "manifest_digest", str(self.manifest_digest).strip())

    def semantic_dict(self) -> dict[str, Any]:
        templates = sorted(
            (template.to_dict() for template in self.templates),
            key=_canonical_json,
        )
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "version": self.version,
            "templates": templates,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "manifest_digest": self.manifest_digest}

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TemplatePackManifest":
        templates = data.get("templates", ())
        if not isinstance(templates, Sequence) or isinstance(templates, (str, bytes)):
            raise TypeError("templates must be a sequence")
        return cls(
            manifest_id=str(data.get("manifest_id", "")),
            version=str(data.get("version", "")),
            templates=tuple(
                item if isinstance(item, TemplatePack) else TemplatePack.from_dict(item)
                for item in templates
            ),
            schema_version=str(data.get("schema_version", "")),
            manifest_digest=str(data.get("manifest_digest", data.get("digest", ""))),
        )


@dataclass(frozen=True)
class ManifestValidation:
    manifest_digest: str
    findings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "manifest_digest": self.manifest_digest,
            "findings": list(self.findings),
        }


@dataclass(frozen=True)
class TemplatePackSelectionReceipt:
    manifest_digest: str
    context_digest: str
    matched_template_ids: tuple[str, ...]
    selected_template_ids: tuple[str, ...]
    disposition: str
    findings: tuple[str, ...] = ()
    schema_version: str = TEMPLATE_PACK_SELECTION_RECEIPT_SCHEMA
    selection_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_digest", str(self.manifest_digest).strip())
        object.__setattr__(self, "context_digest", str(self.context_digest).strip())
        object.__setattr__(self, "matched_template_ids", _tuple_of_text(self.matched_template_ids))
        object.__setattr__(self, "selected_template_ids", _tuple_of_text(self.selected_template_ids))
        object.__setattr__(self, "disposition", str(self.disposition).strip())
        object.__setattr__(self, "findings", _tuple_of_text(self.findings))
        object.__setattr__(self, "schema_version", str(self.schema_version).strip())
        object.__setattr__(self, "selection_digest", str(self.selection_digest).strip())

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_digest": self.manifest_digest,
            "context_digest": self.context_digest,
            "matched_template_ids": list(self.matched_template_ids),
            "selected_template_ids": list(self.selected_template_ids),
            "disposition": self.disposition,
            "findings": list(self.findings),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "selection_digest": self.selection_digest}

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TemplatePackSelectionReceipt":
        return cls(
            manifest_digest=str(data.get("manifest_digest", "")),
            context_digest=str(data.get("context_digest", "")),
            matched_template_ids=tuple(str(item) for item in data.get("matched_template_ids", ())),
            selected_template_ids=tuple(str(item) for item in data.get("selected_template_ids", ())),
            disposition=str(data.get("disposition", "")),
            findings=tuple(str(item) for item in data.get("findings", ())),
            schema_version=str(data.get("schema_version", "")),
            selection_digest=str(data.get("selection_digest", "")),
        )


@dataclass(frozen=True)
class TemplatePackInstanceReceipt:
    manifest_digest: str
    selection_digest: str
    parameter_digest: str
    selected_template_ids: tuple[str, ...]
    status: str
    rendered_template: Mapping[str, Any] = field(default_factory=dict)
    findings: tuple[str, ...] = ()
    schema_version: str = TEMPLATE_PACK_INSTANCE_RECEIPT_SCHEMA
    instance_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_digest", str(self.manifest_digest).strip())
        object.__setattr__(self, "selection_digest", str(self.selection_digest).strip())
        object.__setattr__(self, "parameter_digest", str(self.parameter_digest).strip())
        object.__setattr__(self, "selected_template_ids", _tuple_of_text(self.selected_template_ids))
        object.__setattr__(self, "status", str(self.status).strip())
        object.__setattr__(self, "findings", _tuple_of_text(self.findings))
        object.__setattr__(self, "schema_version", str(self.schema_version).strip())
        object.__setattr__(self, "instance_digest", str(self.instance_digest).strip())
        object.__setattr__(
            self,
            "rendered_template",
            _json_mapping(self.rendered_template, label="rendered_template"),
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_digest": self.manifest_digest,
            "selection_digest": self.selection_digest,
            "parameter_digest": self.parameter_digest,
            "selected_template_ids": list(self.selected_template_ids),
            "status": self.status,
            "rendered_template": _thaw_json(self.rendered_template),
            "findings": list(self.findings),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "instance_digest": self.instance_digest}

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TemplatePackInstanceReceipt":
        return cls(
            manifest_digest=str(data.get("manifest_digest", "")),
            selection_digest=str(data.get("selection_digest", "")),
            parameter_digest=str(data.get("parameter_digest", "")),
            selected_template_ids=tuple(str(item) for item in data.get("selected_template_ids", ())),
            status=str(data.get("status", "")),
            rendered_template=data.get("rendered_template", {}),
            findings=tuple(str(item) for item in data.get("findings", ())),
            schema_version=str(data.get("schema_version", "")),
            instance_digest=str(data.get("instance_digest", "")),
        )


@dataclass(frozen=True)
class ReceiptValidation:
    status: str
    expected_digest: str
    observed_digest: str
    findings: tuple[str, ...] = ()

    @property
    def current(self) -> bool:
        return self.status == "current"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "current": self.current,
            "expected_digest": self.expected_digest,
            "observed_digest": self.observed_digest,
            "findings": list(self.findings),
        }


def template_pack_manifest_digest(manifest: TemplatePackManifest) -> str:
    return _digest(manifest.semantic_dict())


def seal_template_pack_manifest(manifest: TemplatePackManifest) -> TemplatePackManifest:
    return replace(manifest, manifest_digest=template_pack_manifest_digest(manifest))


def _predicate_findings(predicate: HardPredicate, template_id: str, index: int) -> tuple[str, ...]:
    prefix = f"predicate:{template_id}:{index}"
    findings: list[str] = []
    if not predicate.key:
        findings.append(f"{prefix}:missing_key")
    if predicate.operator not in PREDICATE_OPERATORS:
        findings.append(f"{prefix}:unsupported_operator:{predicate.operator or '(empty)'}")
        return tuple(findings)
    expected = predicate.expected
    if predicate.operator == "exists" and not isinstance(expected, bool):
        findings.append(f"{prefix}:exists_expected_must_be_boolean")
    elif predicate.operator in ("one_of", "contains_all"):
        if not isinstance(expected, tuple) or not expected:
            findings.append(f"{prefix}:{predicate.operator}_expected_must_be_nonempty_array")
        elif any(isinstance(item, (Mapping, tuple)) for item in expected):
            findings.append(f"{prefix}:{predicate.operator}_items_must_be_scalars")
    elif predicate.operator == "contains" and isinstance(expected, (Mapping, tuple)):
        findings.append(f"{prefix}:contains_expected_must_be_scalar")
    return tuple(findings)


def validate_template_pack_manifest(manifest: TemplatePackManifest) -> ManifestValidation:
    actual_digest = template_pack_manifest_digest(manifest)
    findings: list[str] = []
    if manifest.schema_version != TEMPLATE_PACK_MANIFEST_SCHEMA:
        findings.append(f"unsupported_manifest_schema:{manifest.schema_version or '(empty)'}")
    if not manifest.manifest_id:
        findings.append("missing_manifest_id")
    if not manifest.version:
        findings.append("missing_manifest_version")
    if not manifest.templates:
        findings.append("empty_template_pack_manifest")
    if not manifest.manifest_digest:
        findings.append("missing_manifest_digest")
    elif manifest.manifest_digest != actual_digest:
        findings.append("manifest_digest_mismatch")

    template_ids = tuple(template.template_id for template in manifest.templates)
    for duplicate in _text_duplicates(template_ids):
        findings.append(f"duplicate_template_id:{duplicate or '(empty)'}")

    bases = tuple(template for template in manifest.templates if template.base)
    if len(bases) > 1:
        findings.append("multiple_base_templates")

    for index, template in enumerate(manifest.templates):
        label = template.template_id or f"index-{index}"
        if not template.template_id:
            findings.append(f"missing_template_id:{index}")
        if not template.version:
            findings.append(f"missing_template_version:{label}")
        if not isinstance(template.priority, int) or isinstance(template.priority, bool):
            findings.append(f"priority_must_be_integer:{label}")
        if not isinstance(template.base, bool):
            findings.append(f"base_must_be_boolean:{label}")
        if not isinstance(template.composable, bool):
            findings.append(f"composable_must_be_boolean:{label}")
        if template.base:
            if template.predicates:
                findings.append(f"base_predicates_not_allowed:{label}")
            if template.composable:
                findings.append(f"base_composable_not_allowed:{label}")
        elif not template.predicates:
            findings.append(f"specialized_predicates_required:{label}")

        for predicate_index, predicate in enumerate(template.predicates):
            if not isinstance(predicate, HardPredicate):
                findings.append(f"predicate_must_be_hard_predicate:{label}:{predicate_index}")
                continue
            findings.extend(_predicate_findings(predicate, label, predicate_index))

        if not template.owned_fields:
            findings.append(f"owned_fields_required:{label}")
        for duplicate in _text_duplicates(template.owned_fields):
            findings.append(f"duplicate_owned_field:{label}:{duplicate or '(empty)'}")
        template_fields = tuple(sorted(template.template.keys()))
        declared_fields = tuple(sorted(set(template.owned_fields)))
        if declared_fields != template_fields:
            findings.append(
                f"owned_fields_mismatch:{label}:declared={','.join(declared_fields)}:template={','.join(template_fields)}"
            )

        for duplicate in _text_duplicates(template.required_parameters):
            findings.append(f"duplicate_required_parameter:{label}:{duplicate or '(empty)'}")
        placeholders = _placeholder_names(template.template)
        declared_parameters = tuple(sorted(set(template.required_parameters)))
        if declared_parameters != placeholders:
            findings.append(
                f"required_parameters_mismatch:{label}:declared={','.join(declared_parameters)}:placeholders={','.join(placeholders)}"
            )

    return ManifestValidation(actual_digest, tuple(findings))


def _predicate_matches(predicate: HardPredicate, context: Mapping[str, Any]) -> bool:
    present = predicate.key in context
    if predicate.operator == "exists":
        return present is predicate.expected
    if not present:
        return False
    candidate = context[predicate.key]
    if predicate.operator == "equals":
        return _json_equal(candidate, predicate.expected)
    if predicate.operator == "one_of":
        return any(_json_equal(candidate, expected) for expected in predicate.expected)
    if predicate.operator == "contains":
        if isinstance(candidate, str):
            return isinstance(predicate.expected, str) and predicate.expected in candidate
        if isinstance(candidate, Mapping):
            return predicate.expected in candidate
        if isinstance(candidate, tuple):
            return any(_json_equal(predicate.expected, item) for item in candidate)
        return False
    if predicate.operator == "contains_all":
        if isinstance(candidate, str):
            return all(isinstance(item, str) and item in candidate for item in predicate.expected)
        if isinstance(candidate, Mapping):
            return all(item in candidate for item in predicate.expected)
        if isinstance(candidate, tuple):
            return all(
                any(_json_equal(expected, item) for item in candidate)
                for expected in predicate.expected
            )
        return False
    return False


def _template_matches(template: TemplatePack, context: Mapping[str, Any]) -> bool:
    return all(_predicate_matches(predicate, context) for predicate in template.predicates)


def _ordered_templates(templates: Sequence[TemplatePack]) -> tuple[TemplatePack, ...]:
    return tuple(sorted(templates, key=lambda item: (item.priority, item.template_id)))


def _field_conflicts(templates: Sequence[TemplatePack]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    owners: dict[str, list[str]] = {}
    for template in templates:
        for owned_field in template.owned_fields:
            owners.setdefault(owned_field, []).append(template.template_id)
    return tuple(
        (field_name, tuple(sorted(template_ids)))
        for field_name, template_ids in sorted(owners.items())
        if len(template_ids) > 1
    )


def _seal_selection_receipt(
    *,
    manifest_digest: str,
    context_digest: str,
    matched_template_ids: Sequence[str],
    selected_template_ids: Sequence[str],
    disposition: str,
    findings: Sequence[str] = (),
) -> TemplatePackSelectionReceipt:
    receipt = TemplatePackSelectionReceipt(
        manifest_digest=manifest_digest,
        context_digest=context_digest,
        matched_template_ids=tuple(matched_template_ids),
        selected_template_ids=tuple(selected_template_ids),
        disposition=disposition,
        findings=tuple(findings),
    )
    return replace(receipt, selection_digest=_digest(receipt.semantic_dict()))


def select_template_packs(
    manifest: TemplatePackManifest,
    context: Mapping[str, Any],
) -> TemplatePackSelectionReceipt:
    frozen_context = _json_mapping(context, label="selection context")
    context_digest = _digest(frozen_context)
    validation = validate_template_pack_manifest(manifest)
    if not validation.ok:
        return _seal_selection_receipt(
            manifest_digest=validation.manifest_digest,
            context_digest=context_digest,
            matched_template_ids=(),
            selected_template_ids=(),
            disposition="invalid_manifest",
            findings=validation.findings,
        )

    specialized = tuple(template for template in manifest.templates if not template.base)
    base_templates = tuple(template for template in manifest.templates if template.base)
    matched = _ordered_templates(
        tuple(template for template in specialized if _template_matches(template, frozen_context))
    )
    matched_ids = tuple(template.template_id for template in matched)

    if not matched:
        if base_templates:
            base = base_templates[0]
            return _seal_selection_receipt(
                manifest_digest=validation.manifest_digest,
                context_digest=context_digest,
                matched_template_ids=(),
                selected_template_ids=(base.template_id,),
                disposition="base_selected",
            )
        return _seal_selection_receipt(
            manifest_digest=validation.manifest_digest,
            context_digest=context_digest,
            matched_template_ids=(),
            selected_template_ids=(),
            disposition="no_match",
        )

    if len(matched) == 1:
        return _seal_selection_receipt(
            manifest_digest=validation.manifest_digest,
            context_digest=context_digest,
            matched_template_ids=matched_ids,
            selected_template_ids=matched_ids,
            disposition="selected",
        )

    non_composable = tuple(template.template_id for template in matched if not template.composable)
    conflicts = _field_conflicts(matched)
    findings: list[str] = []
    if non_composable:
        findings.append("non_composable_matches:" + ",".join(non_composable))
    if conflicts:
        rendered_conflicts = ";".join(
            f"{field_name}={'|'.join(template_ids)}"
            for field_name, template_ids in conflicts
        )
        findings.append("field_owner_conflict:" + rendered_conflicts)
    if findings:
        return _seal_selection_receipt(
            manifest_digest=validation.manifest_digest,
            context_digest=context_digest,
            matched_template_ids=matched_ids,
            selected_template_ids=(),
            disposition="conflict",
            findings=findings,
        )
    return _seal_selection_receipt(
        manifest_digest=validation.manifest_digest,
        context_digest=context_digest,
        matched_template_ids=matched_ids,
        selected_template_ids=matched_ids,
        disposition="composed",
    )


def validate_template_pack_selection_receipt(
    manifest: TemplatePackManifest,
    context: Mapping[str, Any],
    receipt: TemplatePackSelectionReceipt,
) -> ReceiptValidation:
    expected = select_template_packs(manifest, context)
    if receipt == expected:
        return ReceiptValidation(
            "current",
            expected.selection_digest,
            receipt.selection_digest,
        )
    return ReceiptValidation(
        "stale",
        expected.selection_digest,
        receipt.selection_digest,
        ("selection_receipt_stale",),
    )


def _render_value(value: Any, parameters: Mapping[str, Any]) -> Any:
    if isinstance(value, Mapping):
        return {key: _render_value(item, parameters) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_render_value(item, parameters) for item in value]
    if not isinstance(value, str):
        return value
    full_match = _FULL_PLACEHOLDER_PATTERN.fullmatch(value)
    if full_match:
        return _thaw_json(parameters[full_match.group(1)])

    def replacement(match: re.Match[str]) -> str:
        parameter = parameters[match.group(1)]
        if isinstance(parameter, (Mapping, tuple)):
            return _canonical_json(parameter)
        if parameter is None:
            return "null"
        if isinstance(parameter, bool):
            return "true" if parameter else "false"
        return str(parameter)

    return _PLACEHOLDER_PATTERN.sub(replacement, value)


def _seal_instance_receipt(
    *,
    manifest_digest: str,
    selection_digest: str,
    parameter_digest: str,
    selected_template_ids: Sequence[str],
    status: str,
    rendered_template: Mapping[str, Any] | None = None,
    findings: Sequence[str] = (),
) -> TemplatePackInstanceReceipt:
    receipt = TemplatePackInstanceReceipt(
        manifest_digest=manifest_digest,
        selection_digest=selection_digest,
        parameter_digest=parameter_digest,
        selected_template_ids=tuple(selected_template_ids),
        status=status,
        rendered_template=rendered_template or {},
        findings=tuple(findings),
    )
    return replace(receipt, instance_digest=_digest(receipt.semantic_dict()))


def instantiate_template_packs(
    manifest: TemplatePackManifest,
    context: Mapping[str, Any],
    selection_receipt: TemplatePackSelectionReceipt,
    parameters: Mapping[str, Any],
) -> TemplatePackInstanceReceipt:
    frozen_parameters = _json_mapping(parameters, label="template parameters")
    parameter_digest = _digest(frozen_parameters)
    actual_manifest_digest = template_pack_manifest_digest(manifest)
    selection_validation = validate_template_pack_selection_receipt(
        manifest,
        context,
        selection_receipt,
    )
    if not selection_validation.current:
        return _seal_instance_receipt(
            manifest_digest=actual_manifest_digest,
            selection_digest=selection_receipt.selection_digest,
            parameter_digest=parameter_digest,
            selected_template_ids=selection_receipt.selected_template_ids,
            status="blocked",
            findings=selection_validation.findings,
        )
    if selection_receipt.disposition not in SELECTABLE_DISPOSITIONS:
        return _seal_instance_receipt(
            manifest_digest=actual_manifest_digest,
            selection_digest=selection_receipt.selection_digest,
            parameter_digest=parameter_digest,
            selected_template_ids=selection_receipt.selected_template_ids,
            status="blocked",
            findings=(f"selection_not_selectable:{selection_receipt.disposition}",),
        )

    by_id = {template.template_id: template for template in manifest.templates}
    selected = tuple(by_id[template_id] for template_id in selection_receipt.selected_template_ids)
    required_parameters = {
        parameter
        for template in selected
        for parameter in template.required_parameters
    }
    supplied_parameters = set(frozen_parameters.keys())
    missing = tuple(sorted(required_parameters - supplied_parameters))
    unexpected = tuple(sorted(supplied_parameters - required_parameters))
    parameter_findings: list[str] = []
    if missing:
        parameter_findings.append("missing_parameters:" + ",".join(missing))
    if unexpected:
        parameter_findings.append("unexpected_parameters:" + ",".join(unexpected))
    if parameter_findings:
        return _seal_instance_receipt(
            manifest_digest=actual_manifest_digest,
            selection_digest=selection_receipt.selection_digest,
            parameter_digest=parameter_digest,
            selected_template_ids=selection_receipt.selected_template_ids,
            status="blocked",
            findings=parameter_findings,
        )

    rendered: dict[str, Any] = {}
    for template in selected:
        rendered_fields = _render_value(template.template, frozen_parameters)
        for field_name, value in rendered_fields.items():
            if field_name in rendered:
                return _seal_instance_receipt(
                    manifest_digest=actual_manifest_digest,
                    selection_digest=selection_receipt.selection_digest,
                    parameter_digest=parameter_digest,
                    selected_template_ids=selection_receipt.selected_template_ids,
                    status="blocked",
                    findings=(f"field_owner_conflict_at_instantiation:{field_name}",),
                )
            rendered[field_name] = value

    return _seal_instance_receipt(
        manifest_digest=actual_manifest_digest,
        selection_digest=selection_receipt.selection_digest,
        parameter_digest=parameter_digest,
        selected_template_ids=selection_receipt.selected_template_ids,
        status="instantiated",
        rendered_template=rendered,
    )


def validate_template_pack_instance_receipt(
    manifest: TemplatePackManifest,
    context: Mapping[str, Any],
    selection_receipt: TemplatePackSelectionReceipt,
    parameters: Mapping[str, Any],
    receipt: TemplatePackInstanceReceipt,
) -> ReceiptValidation:
    expected = instantiate_template_packs(
        manifest,
        context,
        selection_receipt,
        parameters,
    )
    if receipt == expected:
        return ReceiptValidation(
            "current",
            expected.instance_digest,
            receipt.instance_digest,
        )
    return ReceiptValidation(
        "stale",
        expected.instance_digest,
        receipt.instance_digest,
        ("instance_receipt_stale",),
    )


@dataclass(frozen=True)
class ValidatedTemplatePackRegistry:
    """Small convenience owner for one already sealed, valid manifest."""

    manifest: TemplatePackManifest

    def __post_init__(self) -> None:
        validation = validate_template_pack_manifest(self.manifest)
        if not validation.ok:
            raise ValueError("invalid template-pack manifest: " + "; ".join(validation.findings))

    def select(self, context: Mapping[str, Any]) -> TemplatePackSelectionReceipt:
        return select_template_packs(self.manifest, context)

    def instantiate(
        self,
        context: Mapping[str, Any],
        selection_receipt: TemplatePackSelectionReceipt,
        parameters: Mapping[str, Any],
    ) -> TemplatePackInstanceReceipt:
        return instantiate_template_packs(
            self.manifest,
            context,
            selection_receipt,
            parameters,
        )

    def validate_selection(
        self,
        context: Mapping[str, Any],
        receipt: TemplatePackSelectionReceipt,
    ) -> ReceiptValidation:
        return validate_template_pack_selection_receipt(self.manifest, context, receipt)

    def validate_instance(
        self,
        context: Mapping[str, Any],
        selection_receipt: TemplatePackSelectionReceipt,
        parameters: Mapping[str, Any],
        receipt: TemplatePackInstanceReceipt,
    ) -> ReceiptValidation:
        return validate_template_pack_instance_receipt(
            self.manifest,
            context,
            selection_receipt,
            parameters,
            receipt,
        )


__all__ = [
    "HardPredicate",
    "INSTANCE_STATUSES",
    "ManifestValidation",
    "PREDICATE_OPERATORS",
    "ReceiptValidation",
    "SELECTABLE_DISPOSITIONS",
    "SELECTION_DISPOSITIONS",
    "TEMPLATE_PACK_INSTANCE_RECEIPT_SCHEMA",
    "TEMPLATE_PACK_MANIFEST_SCHEMA",
    "TEMPLATE_PACK_SELECTION_RECEIPT_SCHEMA",
    "TemplatePack",
    "TemplatePackInstanceReceipt",
    "TemplatePackManifest",
    "TemplatePackSelectionReceipt",
    "ValidatedTemplatePackRegistry",
    "instantiate_template_packs",
    "seal_template_pack_manifest",
    "select_template_packs",
    "template_pack_manifest_digest",
    "validate_template_pack_instance_receipt",
    "validate_template_pack_manifest",
    "validate_template_pack_selection_receipt",
]
