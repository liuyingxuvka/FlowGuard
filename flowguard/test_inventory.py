"""Strict, content-addressed inventories of project test structure.

The inventory is a static source artifact.  It records independently
discovered files, executable-node candidates, parameterization markers, calls,
and assertions.  Collection identities, execution receipts, and aggregate
suite results stay external evidence; an aggregate parent evidence reference
never creates or completes a child node here.
"""

from __future__ import annotations

__test__ = False

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from .portable_model import canonical_identity, canonical_json_bytes
from .source_identity import source_file_fingerprint
from .validation_ownership import resolve_input_manifest


TEST_INVENTORY_SCHEMA_VERSION = "flowguard.project_test_inventory.v2"

TEST_DISPOSITION_REQUIRED = "required"
TEST_DISPOSITION_SUPPORTING = "supporting"
TEST_DISPOSITION_SCOPED_OUT = "scoped_out"
TEST_DISPOSITION_GENERATED = "generated"
TEST_DISPOSITION_EXTERNAL = "external"
TEST_DISPOSITION_UNRESOLVED = "unresolved"
TEST_DISPOSITIONS = (
    TEST_DISPOSITION_REQUIRED,
    TEST_DISPOSITION_SUPPORTING,
    TEST_DISPOSITION_SCOPED_OUT,
    TEST_DISPOSITION_GENERATED,
    TEST_DISPOSITION_EXTERNAL,
    TEST_DISPOSITION_UNRESOLVED,
)
TERMINAL_TEST_DISPOSITIONS = frozenset(
    set(TEST_DISPOSITIONS) - {TEST_DISPOSITION_UNRESOLVED}
)

TEST_ASSERTION_KINDS = (
    "assert",
    "raises",
    "warns",
    "unittest_assertion",
    "fail",
)
TEST_FINDING_SEVERITIES = ("info", "warning", "blocker")


class TestInventoryError(ValueError):
    """Raised when a project test inventory is not exact current format."""

    __test__ = False


def _strict_object(
    value: Any,
    *,
    context: str,
    required: Sequence[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TestInventoryError(f"{context} must be an object")
    if set(value) != set(required):
        difference = sorted(set(value) ^ set(required))
        raise TestInventoryError(
            f"{context} fields differ from the current schema: {difference}"
        )
    return value


def _text(value: Any, *, context: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise TestInventoryError(f"{context} must be {qualifier}")
    return value


def _strings(
    value: Any,
    *,
    context: str,
    allow_duplicates: bool = False,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise TestInventoryError(f"{context} must be an array")
    result = tuple(
        _text(item, context=f"{context}[]", allow_empty=allow_empty)
        for item in value
    )
    if not allow_duplicates and len(result) != len(set(result)):
        raise TestInventoryError(f"{context} contains duplicate values")
    return result


def _normalized_strings(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _ordered_strings(values: Sequence[str], *, context: str) -> tuple[str, ...]:
    return _strings(
        tuple(values),
        context=context,
        allow_duplicates=True,
    )


def _relative_path(value: Any, *, context: str) -> str:
    text = _text(value, context=context).replace("\\", "/")
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise TestInventoryError(
            f"{context} must remain inside the declared repository boundary"
        )
    return candidate.as_posix()


def _pattern(value: Any, *, context: str) -> str:
    text = _text(value, context=context).replace("\\", "/")
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise TestInventoryError(f"{context} must be a repository-relative pattern")
    return text


def _pytest_nodeid(value: Any, *, context: str) -> str:
    nodeid = _text(value, context=context).replace("\\", "/")
    path = nodeid.split("::", 1)[0]
    _relative_path(path, context=f"{context}.path")
    if "::" not in nodeid:
        raise TestInventoryError(f"{context} must identify an executable test node")
    return nodeid


def test_node_id(pytest_nodeid: str) -> str:
    """Return the stable identity for one declared or discovered pytest node."""

    normalized = _pytest_nodeid(pytest_nodeid, context="pytest_nodeid")
    return f"test-node:{canonical_identity({'pytest_nodeid': normalized}).split(':', 1)[1]}"


def test_assertion_id(
    pytest_nodeid: str,
    assertion_kind: str,
    target: str,
    line_start: int,
    column_offset: int,
) -> str:
    """Return a stable identity for one source assertion."""

    payload = {
        "pytest_nodeid": _pytest_nodeid(pytest_nodeid, context="pytest_nodeid"),
        "assertion_kind": _text(assertion_kind, context="assertion_kind"),
        "target": _text(target, context="assertion_target"),
        "line_start": int(line_start),
        "column_offset": int(column_offset),
    }
    return f"test-assertion:{canonical_identity(payload).split(':', 1)[1]}"


@dataclass(frozen=True)
class TestFileDisposition:
    __test__ = False

    path: str
    source_fingerprint: str
    disposition: str
    reason: str = ""
    adapter_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _relative_path(self.path, context="file.path"))
        _text(
            self.source_fingerprint,
            context=f"file:{self.path}.source_fingerprint",
        )
        if self.disposition not in TEST_DISPOSITIONS:
            raise TestInventoryError(f"unknown test disposition: {self.disposition}")
        if not isinstance(self.reason, str):
            raise TestInventoryError(f"file:{self.path}.reason must be a string")
        if not isinstance(self.adapter_id, str):
            raise TestInventoryError(f"file:{self.path}.adapter_id must be a string")
        if self.disposition in {TEST_DISPOSITION_REQUIRED, TEST_DISPOSITION_SUPPORTING}:
            if not self.adapter_id:
                raise TestInventoryError(
                    f"file:{self.path} requires an explicit discovery adapter id"
                )
        if self.disposition in {
            TEST_DISPOSITION_SUPPORTING,
            TEST_DISPOSITION_SCOPED_OUT,
            TEST_DISPOSITION_GENERATED,
            TEST_DISPOSITION_EXTERNAL,
        } and not self.reason.strip():
            raise TestInventoryError(
                f"file:{self.path} disposition {self.disposition} requires a reason"
            )

    @property
    def terminal(self) -> bool:
        return self.disposition in TERMINAL_TEST_DISPOSITIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "source_fingerprint": self.source_fingerprint,
            "disposition": self.disposition,
            "reason": self.reason,
            "adapter_id": self.adapter_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TestFileDisposition":
        fields = (
            "path",
            "source_fingerprint",
            "disposition",
            "reason",
            "adapter_id",
        )
        data = _strict_object(value, context="test file disposition", required=fields)
        return cls(**{name: data[name] for name in fields})


@dataclass(frozen=True)
class TestNodeDisposition:
    __test__ = False

    pytest_nodeid: str
    disposition: str
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pytest_nodeid",
            _pytest_nodeid(self.pytest_nodeid, context="node_disposition.pytest_nodeid"),
        )
        if self.disposition not in TEST_DISPOSITIONS:
            raise TestInventoryError(f"unknown test disposition: {self.disposition}")
        if not isinstance(self.reason, str):
            raise TestInventoryError("node disposition reason must be a string")
        if self.disposition in {
            TEST_DISPOSITION_SUPPORTING,
            TEST_DISPOSITION_SCOPED_OUT,
            TEST_DISPOSITION_GENERATED,
            TEST_DISPOSITION_EXTERNAL,
        } and not self.reason.strip():
            raise TestInventoryError(
                f"node {self.pytest_nodeid} disposition {self.disposition} requires a reason"
            )

    @property
    def node_id(self) -> str:
        return test_node_id(self.pytest_nodeid)

    @property
    def terminal(self) -> bool:
        return self.disposition in TERMINAL_TEST_DISPOSITIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "pytest_nodeid": self.pytest_nodeid,
            "disposition": self.disposition,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TestNodeDisposition":
        fields = ("pytest_nodeid", "disposition", "reason")
        data = _strict_object(value, context="test node disposition", required=fields)
        return cls(**{name: data[name] for name in fields})


@dataclass(frozen=True)
class TestParameterizationMarker:
    __test__ = False

    marker_id: str
    argument_names: tuple[str, ...]
    case_count: int
    case_ids: tuple[str, ...]
    dynamic: bool
    structure_fingerprint: str
    line_start: int
    line_end: int

    def __post_init__(self) -> None:
        _text(self.marker_id, context="parameterization.marker_id")
        object.__setattr__(
            self,
            "argument_names",
            _strings(self.argument_names, context="parameterization.argument_names"),
        )
        object.__setattr__(
            self,
            "case_ids",
            _strings(self.case_ids, context="parameterization.case_ids"),
        )
        if not isinstance(self.case_count, int) or self.case_count < -1:
            raise TestInventoryError("parameterization.case_count must be -1 or greater")
        if not isinstance(self.dynamic, bool):
            raise TestInventoryError("parameterization.dynamic must be boolean")
        if self.dynamic and self.case_count != -1:
            raise TestInventoryError("dynamic parameterization must use case_count -1")
        if not self.dynamic and self.case_count < 0:
            raise TestInventoryError("static parameterization requires a known case count")
        _text(
            self.structure_fingerprint,
            context=f"parameterization:{self.marker_id}.structure_fingerprint",
        )
        if not isinstance(self.line_start, int) or not isinstance(self.line_end, int):
            raise TestInventoryError("parameterization line values must be integers")
        if self.line_start < 1 or self.line_end < self.line_start:
            raise TestInventoryError("parameterization line range is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker_id": self.marker_id,
            "argument_names": list(self.argument_names),
            "case_count": self.case_count,
            "case_ids": list(self.case_ids),
            "dynamic": self.dynamic,
            "structure_fingerprint": self.structure_fingerprint,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TestParameterizationMarker":
        fields = (
            "marker_id",
            "argument_names",
            "case_count",
            "case_ids",
            "dynamic",
            "structure_fingerprint",
            "line_start",
            "line_end",
        )
        data = _strict_object(value, context="parameterization marker", required=fields)
        return cls(
            marker_id=data["marker_id"],
            argument_names=_strings(
                data["argument_names"],
                context="parameterization.argument_names",
            ),
            case_count=data["case_count"],
            case_ids=_strings(data["case_ids"], context="parameterization.case_ids"),
            dynamic=data["dynamic"],
            structure_fingerprint=data["structure_fingerprint"],
            line_start=data["line_start"],
            line_end=data["line_end"],
        )


@dataclass(frozen=True)
class TestAssertion:
    __test__ = False

    assertion_id: str
    assertion_kind: str
    target: str
    structure_fingerprint: str
    line_start: int
    line_end: int
    column_offset: int = 0

    def __post_init__(self) -> None:
        _text(self.assertion_id, context="assertion.assertion_id")
        if self.assertion_kind not in TEST_ASSERTION_KINDS:
            raise TestInventoryError(
                f"unknown test assertion kind: {self.assertion_kind}"
            )
        _text(self.target, context=f"assertion:{self.assertion_id}.target")
        _text(
            self.structure_fingerprint,
            context=f"assertion:{self.assertion_id}.structure_fingerprint",
        )
        for name in ("line_start", "line_end", "column_offset"):
            if not isinstance(getattr(self, name), int):
                raise TestInventoryError(f"assertion.{name} must be an integer")
        if self.line_start < 1 or self.line_end < self.line_start:
            raise TestInventoryError("assertion line range is invalid")
        if self.column_offset < 0:
            raise TestInventoryError("assertion.column_offset cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "assertion_id": self.assertion_id,
            "assertion_kind": self.assertion_kind,
            "target": self.target,
            "structure_fingerprint": self.structure_fingerprint,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "column_offset": self.column_offset,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TestAssertion":
        fields = (
            "assertion_id",
            "assertion_kind",
            "target",
            "structure_fingerprint",
            "line_start",
            "line_end",
            "column_offset",
        )
        data = _strict_object(value, context="test assertion", required=fields)
        return cls(**{name: data[name] for name in fields})


@dataclass(frozen=True)
class TestNode:
    __test__ = False

    node_id: str
    pytest_nodeid: str
    path: str
    class_name: str
    function_name: str
    source_fingerprint: str
    structure_fingerprint: str
    disposition: str
    disposition_reason: str
    fixture_names: tuple[str, ...] = ()
    parameterization_markers: tuple[TestParameterizationMarker, ...] = ()
    calls: tuple[str, ...] = ()
    assertions: tuple[TestAssertion, ...] = ()
    line_start: int = 0
    line_end: int = 0
    discovery_adapter_id: str = ""

    def __post_init__(self) -> None:
        _text(self.node_id, context="test_node.node_id")
        object.__setattr__(
            self,
            "pytest_nodeid",
            _pytest_nodeid(self.pytest_nodeid, context="test_node.pytest_nodeid"),
        )
        expected_id = test_node_id(self.pytest_nodeid)
        if self.node_id != expected_id:
            raise TestInventoryError(
                f"test node identity mismatch for {self.pytest_nodeid}"
            )
        object.__setattr__(self, "path", _relative_path(self.path, context="test_node.path"))
        if self.pytest_nodeid.split("::", 1)[0] != self.path:
            raise TestInventoryError("test node path and pytest node id disagree")
        if not isinstance(self.class_name, str):
            raise TestInventoryError("test_node.class_name must be a string")
        _text(self.function_name, context=f"test_node:{self.node_id}.function_name")
        _text(
            self.source_fingerprint,
            context=f"test_node:{self.node_id}.source_fingerprint",
        )
        _text(
            self.structure_fingerprint,
            context=f"test_node:{self.node_id}.structure_fingerprint",
        )
        if self.disposition not in TEST_DISPOSITIONS:
            raise TestInventoryError(f"unknown test disposition: {self.disposition}")
        if not isinstance(self.disposition_reason, str):
            raise TestInventoryError("test_node.disposition_reason must be a string")
        object.__setattr__(
            self,
            "fixture_names",
            _normalized_strings(
                _strings(self.fixture_names, context="test_node.fixture_names")
            ),
        )
        if not isinstance(self.parameterization_markers, tuple):
            object.__setattr__(
                self,
                "parameterization_markers",
                tuple(self.parameterization_markers),
            )
        marker_ids = tuple(item.marker_id for item in self.parameterization_markers)
        if len(marker_ids) != len(set(marker_ids)):
            raise TestInventoryError("test node has duplicate parameterization markers")
        object.__setattr__(
            self,
            "calls",
            _ordered_strings(self.calls, context=f"test_node:{self.node_id}.calls"),
        )
        if not isinstance(self.assertions, tuple):
            object.__setattr__(self, "assertions", tuple(self.assertions))
        assertion_ids = tuple(item.assertion_id for item in self.assertions)
        if len(assertion_ids) != len(set(assertion_ids)):
            raise TestInventoryError("test node has duplicate assertion ids")
        for name in ("line_start", "line_end"):
            if not isinstance(getattr(self, name), int):
                raise TestInventoryError(f"test_node.{name} must be an integer")
        if self.line_start < 1 or self.line_end < self.line_start:
            raise TestInventoryError("test node line range is invalid")
        _text(
            self.discovery_adapter_id,
            context=f"test_node:{self.node_id}.discovery_adapter_id",
        )

    @property
    def terminal(self) -> bool:
        return self.disposition in TERMINAL_TEST_DISPOSITIONS

    @property
    def assertion_count(self) -> int:
        return len(self.assertions)

    @property
    def assertion_kinds(self) -> tuple[str, ...]:
        return tuple(item.assertion_kind for item in self.assertions)

    @property
    def assertion_targets(self) -> tuple[str, ...]:
        return tuple(item.target for item in self.assertions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "pytest_nodeid": self.pytest_nodeid,
            "path": self.path,
            "class_name": self.class_name,
            "function_name": self.function_name,
            "source_fingerprint": self.source_fingerprint,
            "structure_fingerprint": self.structure_fingerprint,
            "disposition": self.disposition,
            "disposition_reason": self.disposition_reason,
            "fixture_names": list(self.fixture_names),
            "parameterization_markers": [
                item.to_dict() for item in self.parameterization_markers
            ],
            "calls": list(self.calls),
            "assertions": [item.to_dict() for item in self.assertions],
            "assertion_count": self.assertion_count,
            "assertion_kinds": list(self.assertion_kinds),
            "assertion_targets": list(self.assertion_targets),
            "line_start": self.line_start,
            "line_end": self.line_end,
            "discovery_adapter_id": self.discovery_adapter_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TestNode":
        fields = (
            "node_id",
            "pytest_nodeid",
            "path",
            "class_name",
            "function_name",
            "source_fingerprint",
            "structure_fingerprint",
            "disposition",
            "disposition_reason",
            "fixture_names",
            "parameterization_markers",
            "calls",
            "assertions",
            "assertion_count",
            "assertion_kinds",
            "assertion_targets",
            "line_start",
            "line_end",
            "discovery_adapter_id",
        )
        data = _strict_object(value, context="test node", required=fields)
        if not isinstance(data["parameterization_markers"], list):
            raise TestInventoryError("test_node.parameterization_markers must be an array")
        if not isinstance(data["assertions"], list):
            raise TestInventoryError("test_node.assertions must be an array")
        node = cls(
            node_id=data["node_id"],
            pytest_nodeid=data["pytest_nodeid"],
            path=data["path"],
            class_name=data["class_name"],
            function_name=data["function_name"],
            source_fingerprint=data["source_fingerprint"],
            structure_fingerprint=data["structure_fingerprint"],
            disposition=data["disposition"],
            disposition_reason=data["disposition_reason"],
            fixture_names=_strings(
                data["fixture_names"], context="test_node.fixture_names"
            ),
            parameterization_markers=tuple(
                TestParameterizationMarker.from_dict(item)
                for item in data["parameterization_markers"]
            ),
            calls=_strings(
                data["calls"],
                context="test_node.calls",
                allow_duplicates=True,
            ),
            assertions=tuple(TestAssertion.from_dict(item) for item in data["assertions"]),
            line_start=data["line_start"],
            line_end=data["line_end"],
            discovery_adapter_id=data["discovery_adapter_id"],
        )
        if not isinstance(data["assertion_count"], int):
            raise TestInventoryError("test node assertion count projection must be an integer")
        projected_kinds = _strings(
            data["assertion_kinds"],
            context="test_node.assertion_kinds",
            allow_duplicates=True,
        )
        projected_targets = _strings(
            data["assertion_targets"],
            context="test_node.assertion_targets",
            allow_duplicates=True,
        )
        if data["assertion_count"] != node.assertion_count:
            raise TestInventoryError("test node assertion count projection mismatch")
        if projected_kinds != node.assertion_kinds:
            raise TestInventoryError("test node assertion kinds projection mismatch")
        if projected_targets != node.assertion_targets:
            raise TestInventoryError("test node assertion targets projection mismatch")
        return node


@dataclass(frozen=True)
class TestFileRecord:
    __test__ = False

    path: str
    source_fingerprint: str
    structure_fingerprint: str
    test_class_names: tuple[str, ...]
    test_function_names: tuple[str, ...]
    node_ids: tuple[str, ...]
    discovery_adapter_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _relative_path(self.path, context="test_file.path"))
        _text(
            self.source_fingerprint,
            context=f"test_file:{self.path}.source_fingerprint",
        )
        _text(
            self.structure_fingerprint,
            context=f"test_file:{self.path}.structure_fingerprint",
        )
        for name in ("test_class_names", "test_function_names", "node_ids"):
            object.__setattr__(self, name, _normalized_strings(getattr(self, name)))
        _text(
            self.discovery_adapter_id,
            context=f"test_file:{self.path}.discovery_adapter_id",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "source_fingerprint": self.source_fingerprint,
            "structure_fingerprint": self.structure_fingerprint,
            "test_class_names": list(self.test_class_names),
            "test_function_names": list(self.test_function_names),
            "node_ids": list(self.node_ids),
            "discovery_adapter_id": self.discovery_adapter_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TestFileRecord":
        fields = (
            "path",
            "source_fingerprint",
            "structure_fingerprint",
            "test_class_names",
            "test_function_names",
            "node_ids",
            "discovery_adapter_id",
        )
        data = _strict_object(value, context="test file record", required=fields)
        return cls(
            path=data["path"],
            source_fingerprint=data["source_fingerprint"],
            structure_fingerprint=data["structure_fingerprint"],
            test_class_names=_strings(
                data["test_class_names"], context="test_file.test_class_names"
            ),
            test_function_names=_strings(
                data["test_function_names"], context="test_file.test_function_names"
            ),
            node_ids=_strings(data["node_ids"], context="test_file.node_ids"),
            discovery_adapter_id=data["discovery_adapter_id"],
        )


@dataclass(frozen=True)
class TestInventoryFinding:
    __test__ = False

    code: str
    message: str
    severity: str = "blocker"
    path: str = ""
    node_id: str = ""

    def __post_init__(self) -> None:
        _text(self.code, context="finding.code")
        _text(self.message, context=f"finding:{self.code}.message")
        if self.severity not in TEST_FINDING_SEVERITIES:
            raise TestInventoryError(f"unknown finding severity: {self.severity}")
        if self.path:
            object.__setattr__(self, "path", _relative_path(self.path, context="finding.path"))
        if not isinstance(self.node_id, str):
            raise TestInventoryError("finding.node_id must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "path": self.path,
            "node_id": self.node_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "TestInventoryFinding":
        fields = ("code", "message", "severity", "path", "node_id")
        data = _strict_object(value, context="test inventory finding", required=fields)
        return cls(**{name: data[name] for name in fields})


@dataclass(frozen=True)
class TestDiscoveryResult:
    __test__ = False

    adapter_id: str
    path: str
    file_record: TestFileRecord | None = None
    nodes: tuple[TestNode, ...] = ()
    findings: tuple[TestInventoryFinding, ...] = ()

    def __post_init__(self) -> None:
        _text(self.adapter_id, context="test_discovery.adapter_id")
        object.__setattr__(
            self,
            "path",
            _relative_path(self.path, context="test_discovery.path"),
        )
        if self.file_record is not None and not isinstance(self.file_record, TestFileRecord):
            raise TestInventoryError("test_discovery.file_record has the wrong type")
        if not isinstance(self.nodes, tuple):
            object.__setattr__(self, "nodes", tuple(self.nodes))
        if not isinstance(self.findings, tuple):
            object.__setattr__(self, "findings", tuple(self.findings))


@dataclass(frozen=True)
class ProjectTestInventory:
    __test__ = False

    inventory_id: str
    subject_revision: str
    test_patterns: tuple[str, ...]
    manifest_fingerprint: str
    file_dispositions: tuple[TestFileDisposition, ...]
    node_dispositions: tuple[TestNodeDisposition, ...]
    files: tuple[TestFileRecord, ...]
    nodes: tuple[TestNode, ...]
    aggregate_parent_evidence_ids: tuple[str, ...]
    findings: tuple[TestInventoryFinding, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        _text(self.inventory_id, context="test_inventory.inventory_id")
        _text(self.subject_revision, context="test_inventory.subject_revision")
        patterns = tuple(
            _pattern(item, context="test_inventory.test_patterns")
            for item in self.test_patterns
        )
        if not patterns:
            raise TestInventoryError("test inventory must declare at least one test pattern")
        if len(patterns) != len(set(patterns)):
            raise TestInventoryError("test inventory contains duplicate test patterns")
        object.__setattr__(self, "test_patterns", patterns)
        _text(self.manifest_fingerprint, context="test_inventory.manifest_fingerprint")
        for name in (
            "file_dispositions",
            "node_dispositions",
            "files",
            "nodes",
            "findings",
        ):
            if not isinstance(getattr(self, name), tuple):
                object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(
            self,
            "file_dispositions",
            tuple(sorted(self.file_dispositions, key=lambda item: item.path)),
        )
        object.__setattr__(
            self,
            "node_dispositions",
            tuple(sorted(self.node_dispositions, key=lambda item: item.pytest_nodeid)),
        )
        object.__setattr__(
            self,
            "files",
            tuple(sorted(self.files, key=lambda item: item.path)),
        )
        object.__setattr__(
            self,
            "nodes",
            tuple(sorted(self.nodes, key=lambda item: item.pytest_nodeid)),
        )
        object.__setattr__(
            self,
            "aggregate_parent_evidence_ids",
            _normalized_strings(
                _strings(
                    self.aggregate_parent_evidence_ids,
                    context="test_inventory.aggregate_parent_evidence_ids",
                )
            ),
        )
        object.__setattr__(
            self,
            "findings",
            tuple(
                sorted(
                    self.findings,
                    key=lambda item: (
                        item.severity,
                        item.code,
                        item.path,
                        item.node_id,
                        item.message,
                    ),
                )
            ),
        )
        _text(self.claim_boundary, context="test_inventory.claim_boundary")

        file_paths = tuple(item.path for item in self.file_dispositions)
        if len(file_paths) != len(set(file_paths)):
            raise TestInventoryError("test inventory contains duplicate file dispositions")
        declared_nodeids = tuple(item.pytest_nodeid for item in self.node_dispositions)
        if len(declared_nodeids) != len(set(declared_nodeids)):
            raise TestInventoryError("test inventory contains duplicate node dispositions")
        recorded_paths = tuple(item.path for item in self.files)
        if len(recorded_paths) != len(set(recorded_paths)):
            raise TestInventoryError("test inventory contains duplicate file records")
        node_ids = tuple(item.node_id for item in self.nodes)
        nodeids = tuple(item.pytest_nodeid for item in self.nodes)
        if len(node_ids) != len(set(node_ids)) or len(nodeids) != len(set(nodeids)):
            raise TestInventoryError("test inventory contains duplicate test nodes")
        known_files = set(recorded_paths)
        if any(node.path not in known_files for node in self.nodes):
            raise TestInventoryError("test inventory node references an unknown file record")

    @property
    def required_pytest_nodeids(self) -> tuple[str, ...]:
        return tuple(
            item.pytest_nodeid
            for item in self.node_dispositions
            if item.disposition == TEST_DISPOSITION_REQUIRED
        )

    @property
    def required_node_ids(self) -> tuple[str, ...]:
        return tuple(test_node_id(item) for item in self.required_pytest_nodeids)

    @property
    def inventory_fingerprint(self) -> str:
        return canonical_identity(self._identity_payload())

    @property
    def fingerprint(self) -> str:
        return self.inventory_fingerprint

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": TEST_INVENTORY_SCHEMA_VERSION,
            "inventory_id": self.inventory_id,
            "subject_revision": self.subject_revision,
            "test_patterns": list(self.test_patterns),
            "manifest_fingerprint": self.manifest_fingerprint,
            "file_dispositions": [item.to_dict() for item in self.file_dispositions],
            "node_dispositions": [item.to_dict() for item in self.node_dispositions],
            "files": [item.to_dict() for item in self.files],
            "nodes": [item.to_dict() for item in self.nodes],
            "aggregate_parent_evidence_ids": list(self.aggregate_parent_evidence_ids),
            "findings": [item.to_dict() for item in self.findings],
            "claim_boundary": self.claim_boundary,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._identity_payload(),
            "inventory_fingerprint": self.inventory_fingerprint,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ProjectTestInventory":
        fields = (
            "schema_version",
            "inventory_id",
            "subject_revision",
            "test_patterns",
            "manifest_fingerprint",
            "file_dispositions",
            "node_dispositions",
            "files",
            "nodes",
            "aggregate_parent_evidence_ids",
            "findings",
            "claim_boundary",
            "inventory_fingerprint",
        )
        data = _strict_object(value, context="project test inventory", required=fields)
        if data["schema_version"] != TEST_INVENTORY_SCHEMA_VERSION:
            raise TestInventoryError("project test inventory schema is not current")
        for name in (
            "test_patterns",
            "file_dispositions",
            "node_dispositions",
            "files",
            "nodes",
            "aggregate_parent_evidence_ids",
            "findings",
        ):
            if not isinstance(data[name], list):
                raise TestInventoryError(f"test_inventory.{name} must be an array")
        inventory = cls(
            inventory_id=data["inventory_id"],
            subject_revision=data["subject_revision"],
            test_patterns=_strings(data["test_patterns"], context="test_patterns"),
            manifest_fingerprint=data["manifest_fingerprint"],
            file_dispositions=tuple(
                TestFileDisposition.from_dict(item) for item in data["file_dispositions"]
            ),
            node_dispositions=tuple(
                TestNodeDisposition.from_dict(item) for item in data["node_dispositions"]
            ),
            files=tuple(TestFileRecord.from_dict(item) for item in data["files"]),
            nodes=tuple(TestNode.from_dict(item) for item in data["nodes"]),
            aggregate_parent_evidence_ids=_strings(
                data["aggregate_parent_evidence_ids"],
                context="aggregate_parent_evidence_ids",
            ),
            findings=tuple(TestInventoryFinding.from_dict(item) for item in data["findings"]),
            claim_boundary=data["claim_boundary"],
        )
        expected = _text(data["inventory_fingerprint"], context="inventory_fingerprint")
        if inventory.inventory_fingerprint != expected:
            raise TestInventoryError("project test inventory fingerprint mismatch")
        return inventory


@dataclass(frozen=True)
class TestInventoryAuditReport:
    __test__ = False

    ok: bool
    status: str
    inventory_fingerprint: str
    required_node_ids: tuple[str, ...]
    required_pytest_nodeids: tuple[str, ...]
    findings: tuple[TestInventoryFinding, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        if not isinstance(self.ok, bool):
            raise TestInventoryError("test inventory audit ok must be boolean")
        if self.status not in {"complete", "blocked"}:
            raise TestInventoryError("test inventory audit status must be complete or blocked")
        _text(self.inventory_fingerprint, context="test_inventory_audit.inventory_fingerprint")
        object.__setattr__(self, "required_node_ids", _normalized_strings(self.required_node_ids))
        object.__setattr__(
            self,
            "required_pytest_nodeids",
            _normalized_strings(self.required_pytest_nodeids),
        )
        if not isinstance(self.findings, tuple):
            object.__setattr__(self, "findings", tuple(self.findings))
        _text(self.claim_boundary, context="test_inventory_audit.claim_boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "inventory_fingerprint": self.inventory_fingerprint,
            "required_node_ids": list(self.required_node_ids),
            "required_pytest_nodeids": list(self.required_pytest_nodeids),
            "findings": [item.to_dict() for item in self.findings],
            "claim_boundary": self.claim_boundary,
        }


TestDiscoveryAdapter = Callable[..., TestDiscoveryResult]


def _manifest(
    root: Path,
    patterns: Sequence[str],
) -> tuple[dict[str, str], str]:
    rows = resolve_input_manifest(root, patterns)
    by_path = {row["path"]: row["sha256"] for row in rows}
    fingerprint = canonical_identity(
        [{"path": path, "sha256": by_path[path]} for path in sorted(by_path)]
    )
    return by_path, fingerprint


def build_project_test_inventory(
    root: str | Path,
    *,
    inventory_id: str,
    subject_revision: str,
    test_patterns: Sequence[str],
    file_dispositions: Sequence[TestFileDisposition],
    node_dispositions: Sequence[TestNodeDisposition],
    aggregate_parent_evidence_ids: Sequence[str] = (),
    discovery_adapters: Mapping[str, TestDiscoveryAdapter] | None = None,
    claim_boundary: str = (
        "Static project-test discovery and disposition only. Collection, selection, "
        "execution, environment, toolchain, immutable receipt, model-obligation binding, "
        "and assertion sufficiency for a claimed contract require separate current evidence. "
        "Aggregate parent evidence never creates child-node evidence."
    ),
) -> ProjectTestInventory:
    """Build one exact static inventory without running or collecting tests."""

    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise TestInventoryError(f"test inventory root is not a directory: {root_path}")
    _text(inventory_id, context="inventory_id")
    _text(subject_revision, context="subject_revision")
    normalized_patterns = tuple(
        _pattern(item, context="test_patterns") for item in test_patterns
    )
    if not normalized_patterns:
        raise TestInventoryError("test inventory must declare at least one test pattern")
    manifest, manifest_fingerprint = _manifest(root_path, normalized_patterns)
    findings: list[TestInventoryFinding] = []
    if not manifest:
        findings.append(
            TestInventoryFinding(
                "empty_test_manifest",
                "declared test patterns resolve to no current source files",
            )
        )

    supplied_files: dict[str, TestFileDisposition] = {}
    for item in file_dispositions:
        if item.path in supplied_files:
            findings.append(
                TestInventoryFinding(
                    "duplicate_test_file_disposition",
                    "test file has more than one supplied disposition",
                    path=item.path,
                )
            )
            continue
        supplied_files[item.path] = item

    admitted_files: list[TestFileDisposition] = []
    for path in sorted(manifest):
        supplied = supplied_files.get(path)
        if supplied is None:
            supplied = TestFileDisposition(
                path=path,
                source_fingerprint=manifest[path],
                disposition=TEST_DISPOSITION_UNRESOLVED,
                reason="missing explicit test file disposition",
            )
            findings.append(
                TestInventoryFinding(
                    "missing_test_file_disposition",
                    "admitted test source has no explicit disposition",
                    path=path,
                )
            )
        elif supplied.source_fingerprint != manifest[path]:
            findings.append(
                TestInventoryFinding(
                    "stale_test_source_fingerprint",
                    "declared test source fingerprint differs from current content",
                    path=path,
                )
            )
        admitted_files.append(supplied)

    for path in sorted(set(supplied_files) - set(manifest)):
        findings.append(
            TestInventoryFinding(
                "test_file_outside_manifest",
                "supplied test file disposition is outside the current test manifest",
                path=path,
            )
        )

    supplied_nodes: dict[str, TestNodeDisposition] = {}
    admitted_node_dispositions: list[TestNodeDisposition] = []
    for item in node_dispositions:
        if item.pytest_nodeid in supplied_nodes:
            findings.append(
                TestInventoryFinding(
                    "duplicate_test_node_disposition",
                    "pytest node has more than one supplied disposition",
                    path=item.pytest_nodeid.split("::", 1)[0],
                    node_id=item.node_id,
                )
            )
            continue
        supplied_nodes[item.pytest_nodeid] = item
        admitted_node_dispositions.append(item)
        node_path = item.pytest_nodeid.split("::", 1)[0]
        if node_path not in manifest:
            findings.append(
                TestInventoryFinding(
                    "test_node_outside_manifest",
                    "declared pytest node belongs to no current admitted test source",
                    path=node_path,
                    node_id=item.node_id,
                )
            )

    adapters = dict(discovery_adapters or {})
    files: list[TestFileRecord] = []
    nodes: list[TestNode] = []
    seen_file_paths: set[str] = set()
    seen_nodeids: set[str] = set()
    for item in admitted_files:
        if not item.terminal:
            findings.append(
                TestInventoryFinding(
                    "unresolved_test_file_disposition",
                    "test file disposition remains unresolved",
                    path=item.path,
                )
            )
        if not item.adapter_id:
            if item.disposition in {TEST_DISPOSITION_REQUIRED, TEST_DISPOSITION_SUPPORTING}:
                findings.append(
                    TestInventoryFinding(
                        "missing_test_discovery_adapter",
                        "required or supporting test file has no discovery adapter",
                        path=item.path,
                    )
                )
            continue
        adapter = adapters.get(item.adapter_id)
        if adapter is None:
            findings.append(
                TestInventoryFinding(
                    "missing_test_discovery_adapter",
                    f"test discovery adapter is unavailable: {item.adapter_id}",
                    path=item.path,
                )
            )
            continue
        try:
            result = adapter(
                root=root_path,
                file_disposition=item,
                node_dispositions=supplied_nodes,
            )
        except Exception as exc:  # adapters are an explicit untrusted boundary
            findings.append(
                TestInventoryFinding(
                    "test_discovery_adapter_failure",
                    f"{item.adapter_id} failed: {exc.__class__.__name__}: {exc}",
                    path=item.path,
                )
            )
            continue
        if not isinstance(result, TestDiscoveryResult):
            findings.append(
                TestInventoryFinding(
                    "test_discovery_adapter_result_invalid",
                    "test discovery adapter did not return the current result type",
                    path=item.path,
                )
            )
            continue
        if result.adapter_id != item.adapter_id or result.path != item.path:
            findings.append(
                TestInventoryFinding(
                    "test_discovery_adapter_identity_mismatch",
                    "adapter result does not bind the requested adapter and file",
                    path=item.path,
                )
            )
            continue
        findings.extend(result.findings)
        identity_gaps: list[str] = []
        if result.file_record is None and result.nodes:
            identity_gaps.append("nodes were emitted without a containing file record")
        if result.file_record is not None:
            if result.file_record.path != item.path:
                identity_gaps.append("file record path differs from requested path")
            if result.file_record.discovery_adapter_id != item.adapter_id:
                identity_gaps.append("file record adapter differs from requested adapter")
            if result.file_record.source_fingerprint != manifest[item.path]:
                identity_gaps.append("file record source differs from current manifest")
            if set(result.file_record.node_ids) != {
                node.node_id for node in result.nodes
            }:
                identity_gaps.append("file record node projection differs from emitted nodes")
        for node in result.nodes:
            if node.path != item.path:
                identity_gaps.append(
                    f"node {node.node_id} belongs to a different source path"
                )
            if node.discovery_adapter_id != item.adapter_id:
                identity_gaps.append(
                    f"node {node.node_id} names a different discovery adapter"
                )
            if node.source_fingerprint != manifest[item.path]:
                identity_gaps.append(
                    f"node {node.node_id} names a different source fingerprint"
                )
        if identity_gaps:
            findings.append(
                TestInventoryFinding(
                    "test_discovery_record_identity_mismatch",
                    "untrusted adapter output is not bound to the requested current source: "
                    + "; ".join(identity_gaps),
                    path=item.path,
                )
            )
            continue
        if result.file_record is not None:
            if result.file_record.path in seen_file_paths:
                findings.append(
                    TestInventoryFinding(
                        "duplicate_test_file_record",
                        "test discovery emitted a duplicate file record",
                        path=result.file_record.path,
                    )
                )
            else:
                seen_file_paths.add(result.file_record.path)
                files.append(result.file_record)
        for node in result.nodes:
            if node.pytest_nodeid in seen_nodeids:
                findings.append(
                    TestInventoryFinding(
                        "duplicate_test_node",
                        "test discovery emitted a duplicate pytest node",
                        path=node.path,
                        node_id=node.node_id,
                    )
                )
                continue
            seen_nodeids.add(node.pytest_nodeid)
            nodes.append(node)

    for declaration in admitted_node_dispositions:
        if declaration.pytest_nodeid in seen_nodeids:
            continue
        code = (
            "missing_required_test_node"
            if declaration.disposition == TEST_DISPOSITION_REQUIRED
            else "missing_declared_test_node"
        )
        severity = (
            "blocker"
            if declaration.disposition in {
                TEST_DISPOSITION_REQUIRED,
                TEST_DISPOSITION_SUPPORTING,
            }
            else "warning"
        )
        findings.append(
            TestInventoryFinding(
                code,
                "declared pytest node is absent from independent static discovery",
                severity=severity,
                path=declaration.pytest_nodeid.split("::", 1)[0],
                node_id=declaration.node_id,
            )
        )

    return ProjectTestInventory(
        inventory_id=inventory_id,
        subject_revision=subject_revision,
        test_patterns=normalized_patterns,
        manifest_fingerprint=manifest_fingerprint,
        file_dispositions=tuple(admitted_files),
        node_dispositions=tuple(admitted_node_dispositions),
        files=tuple(files),
        nodes=tuple(nodes),
        aggregate_parent_evidence_ids=tuple(aggregate_parent_evidence_ids),
        findings=tuple(findings),
        claim_boundary=claim_boundary,
    )


def review_project_test_inventory(
    inventory: ProjectTestInventory,
    *,
    root: str | Path | None = None,
    discovery_adapters: Mapping[str, TestDiscoveryAdapter] | None = None,
) -> TestInventoryAuditReport:
    """Review static completeness and optionally compare current source structure."""

    findings = list(inventory.findings)
    declarations = {item.pytest_nodeid: item for item in inventory.node_dispositions}
    discovered = {item.pytest_nodeid: item for item in inventory.nodes}
    dispositions_by_path = {item.path: item for item in inventory.file_dispositions}
    files_by_path = {item.path: item for item in inventory.files}
    nodes_by_path: dict[str, set[str]] = {}
    for node in inventory.nodes:
        nodes_by_path.setdefault(node.path, set()).add(node.node_id)

    for item in inventory.file_dispositions:
        if not item.terminal:
            findings.append(
                TestInventoryFinding(
                    "unresolved_test_file_disposition",
                    "test file disposition is not terminal",
                    path=item.path,
                )
            )
        file_record = files_by_path.get(item.path)
        if (
            item.disposition in {TEST_DISPOSITION_REQUIRED, TEST_DISPOSITION_SUPPORTING}
            and file_record is None
        ):
            findings.append(
                TestInventoryFinding(
                    "missing_test_file_record",
                    "required or supporting test source has no discovery record",
                    path=item.path,
                )
            )
        if file_record is not None:
            if file_record.source_fingerprint != item.source_fingerprint:
                findings.append(
                    TestInventoryFinding(
                        "test_file_source_identity_mismatch",
                        "test file discovery and disposition use different source identities",
                        path=item.path,
                    )
                )
            if file_record.discovery_adapter_id != item.adapter_id:
                findings.append(
                    TestInventoryFinding(
                        "test_file_adapter_identity_mismatch",
                        "test file discovery and disposition use different adapter identities",
                        path=item.path,
                    )
                )
        if (
            item.disposition == TEST_DISPOSITION_REQUIRED
            and item.path in files_by_path
            and not nodes_by_path.get(item.path)
        ):
            findings.append(
                TestInventoryFinding(
                    "required_test_file_without_nodes",
                    "required test file contains no independently discovered executable node",
                    path=item.path,
                )
            )

    for declaration in inventory.node_dispositions:
        if not declaration.terminal:
            findings.append(
                TestInventoryFinding(
                    "unresolved_test_node_disposition",
                    "declared pytest node disposition is not terminal",
                    path=declaration.pytest_nodeid.split("::", 1)[0],
                    node_id=declaration.node_id,
                )
            )
        if (
            declaration.disposition == TEST_DISPOSITION_REQUIRED
            and declaration.pytest_nodeid not in discovered
        ):
            findings.append(
                TestInventoryFinding(
                    "missing_required_test_node",
                    "required pytest node is absent from independent static discovery",
                    path=declaration.pytest_nodeid.split("::", 1)[0],
                    node_id=declaration.node_id,
                )
            )

    for node in inventory.nodes:
        declaration = declarations.get(node.pytest_nodeid)
        if declaration is None:
            findings.append(
                TestInventoryFinding(
                    "orphan_test_node",
                    "discovered pytest node has no explicit project disposition",
                    path=node.path,
                    node_id=node.node_id,
                )
            )
        elif (
            node.disposition != declaration.disposition
            or node.disposition_reason != declaration.reason
        ):
            findings.append(
                TestInventoryFinding(
                    "test_node_disposition_mismatch",
                    "discovered node disposition differs from its declared disposition",
                    path=node.path,
                    node_id=node.node_id,
                )
            )
        if not node.terminal:
            findings.append(
                TestInventoryFinding(
                    "unresolved_test_node_disposition",
                    "discovered pytest node disposition remains unresolved",
                    path=node.path,
                    node_id=node.node_id,
                )
            )
        file_record = files_by_path.get(node.path)
        if (
            file_record is not None
            and node.source_fingerprint != file_record.source_fingerprint
        ):
            findings.append(
                TestInventoryFinding(
                    "test_node_source_identity_mismatch",
                    "test node and containing file use different source identities",
                    path=node.path,
                    node_id=node.node_id,
                )
            )
        if (
            file_record is not None
            and node.discovery_adapter_id != file_record.discovery_adapter_id
        ):
            findings.append(
                TestInventoryFinding(
                    "test_node_adapter_identity_mismatch",
                    "test node and containing file use different discovery adapters",
                    path=node.path,
                    node_id=node.node_id,
                )
            )
        if node.disposition == TEST_DISPOSITION_REQUIRED and node.assertion_count == 0:
            findings.append(
                TestInventoryFinding(
                    "assertion_free_required_test_node",
                    "required pytest node has no independently discovered oracle-bearing assertion",
                    path=node.path,
                    node_id=node.node_id,
                )
            )
        for marker in node.parameterization_markers:
            if marker.dynamic:
                findings.append(
                    TestInventoryFinding(
                        "dynamic_test_parameterization",
                        "parameterized cases cannot be enumerated from current static source",
                        path=node.path,
                        node_id=node.node_id,
                    )
                )

    for file_record in inventory.files:
        if file_record.path not in dispositions_by_path:
            findings.append(
                TestInventoryFinding(
                    "orphan_test_file_record",
                    "test file discovery record has no admitted file disposition",
                    path=file_record.path,
                )
            )
        expected_node_ids = nodes_by_path.get(file_record.path, set())
        if set(file_record.node_ids) != expected_node_ids:
            findings.append(
                TestInventoryFinding(
                    "test_file_node_projection_mismatch",
                    "test file node projection differs from discovered nodes",
                    path=file_record.path,
                )
            )

    projected_manifest_fingerprint = canonical_identity(
        [
            {"path": item.path, "sha256": item.source_fingerprint}
            for item in inventory.file_dispositions
        ]
    )
    if projected_manifest_fingerprint != inventory.manifest_fingerprint:
        findings.append(
            TestInventoryFinding(
                "test_manifest_projection_mismatch",
                "inventory manifest identity differs from admitted file dispositions",
            )
        )

    if root is not None:
        root_path = Path(root).resolve()
        adapters = dict(discovery_adapters or {})
        current_manifest, current_manifest_fingerprint = _manifest(
            root_path,
            inventory.test_patterns,
        )
        inventoried_paths = {item.path for item in inventory.file_dispositions}
        if current_manifest_fingerprint != inventory.manifest_fingerprint:
            findings.append(
                TestInventoryFinding(
                    "stale_test_manifest_fingerprint",
                    "current test-source manifest differs from the inventoried manifest",
                )
            )
        for path in sorted(set(current_manifest) - inventoried_paths):
            findings.append(
                TestInventoryFinding(
                    "uninventoried_current_test_file",
                    "current test source matches the boundary but has no inventory disposition",
                    path=path,
                )
            )
        for disposition in inventory.file_dispositions:
            path = (root_path / disposition.path).resolve()
            try:
                path.relative_to(root_path)
            except ValueError:
                findings.append(
                    TestInventoryFinding(
                        "path_escape",
                        "inventoried test path escapes the current project root",
                        path=disposition.path,
                    )
                )
                continue
            if not path.is_file():
                findings.append(
                    TestInventoryFinding(
                        "missing_current_test_file",
                        "inventoried test source is absent from the current project root",
                        path=disposition.path,
                    )
                )
                continue
            current_source_fingerprint = source_file_fingerprint(path)
            if current_source_fingerprint != disposition.source_fingerprint:
                findings.append(
                    TestInventoryFinding(
                        "stale_test_source_fingerprint",
                        "inventoried test source fingerprint differs from current content",
                        path=disposition.path,
                    )
                )
            if not disposition.adapter_id:
                continue
            adapter = adapters.get(disposition.adapter_id)
            if adapter is None:
                findings.append(
                    TestInventoryFinding(
                        "current_test_structure_not_audited",
                        f"current structure adapter is unavailable: {disposition.adapter_id}",
                        path=disposition.path,
                    )
                )
                continue
            current_input = TestFileDisposition(
                path=disposition.path,
                source_fingerprint=current_source_fingerprint,
                disposition=disposition.disposition,
                reason=disposition.reason,
                adapter_id=disposition.adapter_id,
            )
            try:
                current = adapter(
                    root=root_path,
                    file_disposition=current_input,
                    node_dispositions=declarations,
                )
            except Exception as exc:
                findings.append(
                    TestInventoryFinding(
                        "current_test_structure_audit_failure",
                        f"{disposition.adapter_id} failed: {exc.__class__.__name__}: {exc}",
                        path=disposition.path,
                    )
                )
                continue
            findings.extend(current.findings)
            recorded_file = files_by_path.get(disposition.path)
            if recorded_file is None or current.file_record is None:
                findings.append(
                    TestInventoryFinding(
                        "missing_current_test_file_structure",
                        "current or inventoried test file structure record is missing",
                        path=disposition.path,
                    )
                )
                continue
            if (
                current.file_record.structure_fingerprint
                != recorded_file.structure_fingerprint
            ):
                findings.append(
                    TestInventoryFinding(
                        "stale_test_structure_fingerprint",
                        "inventoried test file structure differs from current source",
                        path=disposition.path,
                    )
                )
            current_nodes = {item.pytest_nodeid: item for item in current.nodes}
            recorded_nodes = {
                item.pytest_nodeid: item
                for item in inventory.nodes
                if item.path == disposition.path
            }
            if set(current_nodes) != set(recorded_nodes):
                findings.append(
                    TestInventoryFinding(
                        "stale_test_node_set",
                        "inventoried pytest node set differs from current source",
                        path=disposition.path,
                    )
                )
            for nodeid in sorted(set(current_nodes) & set(recorded_nodes)):
                current_node = current_nodes[nodeid]
                recorded_node = recorded_nodes[nodeid]
                if current_node.structure_fingerprint != recorded_node.structure_fingerprint:
                    findings.append(
                        TestInventoryFinding(
                            "stale_test_structure_fingerprint",
                            "inventoried pytest node structure differs from current source",
                            path=disposition.path,
                            node_id=recorded_node.node_id,
                        )
                    )

    unique = {
        (item.code, item.message, item.severity, item.path, item.node_id): item
        for item in findings
    }
    ordered = tuple(
        unique[key]
        for key in sorted(
            unique,
            key=lambda item: (item[2], item[0], item[3], item[4], item[1]),
        )
    )
    ok = not any(item.severity == "blocker" for item in ordered)
    return TestInventoryAuditReport(
        ok=ok,
        status="complete" if ok else "blocked",
        inventory_fingerprint=inventory.inventory_fingerprint,
        required_node_ids=inventory.required_node_ids,
        required_pytest_nodeids=inventory.required_pytest_nodeids,
        findings=ordered,
        claim_boundary=inventory.claim_boundary,
    )


def serialize_project_test_inventory(inventory: ProjectTestInventory) -> bytes:
    """Return canonical UTF-8 JSON bytes without writing anything."""

    return canonical_json_bytes(inventory.to_dict())


def write_project_test_inventory(
    inventory: ProjectTestInventory,
    path: str | Path,
) -> Path:
    """Explicitly write one canonical project test inventory artifact."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(serialize_project_test_inventory(inventory) + b"\n")
    return target


def load_project_test_inventory(path: str | Path) -> ProjectTestInventory:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TestInventoryError(f"cannot load project test inventory: {exc}") from exc
    return ProjectTestInventory.from_dict(value)


def audit_project_test_inventory(
    path: str | Path,
    *,
    root: str | Path | None = None,
    discovery_adapters: Mapping[str, TestDiscoveryAdapter] | None = None,
) -> TestInventoryAuditReport:
    """Load and audit an inventory without collecting or running tests."""

    inventory = load_project_test_inventory(path)
    return review_project_test_inventory(
        inventory,
        root=root,
        discovery_adapters=discovery_adapters,
    )


__all__ = [
    "TEST_INVENTORY_SCHEMA_VERSION",
    "TEST_DISPOSITION_REQUIRED",
    "TEST_DISPOSITION_SUPPORTING",
    "TEST_DISPOSITION_SCOPED_OUT",
    "TEST_DISPOSITION_GENERATED",
    "TEST_DISPOSITION_EXTERNAL",
    "TEST_DISPOSITION_UNRESOLVED",
    "TEST_DISPOSITIONS",
    "TERMINAL_TEST_DISPOSITIONS",
    "TEST_ASSERTION_KINDS",
    "TestInventoryError",
    "TestFileDisposition",
    "TestNodeDisposition",
    "TestParameterizationMarker",
    "TestAssertion",
    "TestNode",
    "TestFileRecord",
    "TestInventoryFinding",
    "TestDiscoveryResult",
    "ProjectTestInventory",
    "TestInventoryAuditReport",
    "TestDiscoveryAdapter",
    "test_node_id",
    "test_assertion_id",
    "build_project_test_inventory",
    "review_project_test_inventory",
    "serialize_project_test_inventory",
    "write_project_test_inventory",
    "load_project_test_inventory",
    "audit_project_test_inventory",
]
