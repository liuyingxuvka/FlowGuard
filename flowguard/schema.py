"""Stable artifact schema helpers for flowguard reports and traces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .export import to_jsonable
from .trace import Trace


SCHEMA_VERSION = "1.0"
DEFAULT_CREATED_BY = "flowguard"


@dataclass(frozen=True)
class ArtifactEnvelope:
    """Versioned, deterministic wrapper for machine-readable artifacts."""

    artifact_type: str
    payload: Any
    schema_version: str = SCHEMA_VERSION
    created_by: str = DEFAULT_CREATED_BY
    model_name: str = ""
    scenario_name: str = ""
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": self.artifact_type,
            "created_by": self.created_by,
            "model_name": self.model_name,
            "scenario_name": self.scenario_name,
            "trace_id": self.trace_id,
            "payload": to_jsonable(self.payload),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def make_artifact(
    artifact_type: str,
    payload: Any,
    *,
    model_name: str = "",
    scenario_name: str = "",
    trace_id: str = "",
    created_by: str = DEFAULT_CREATED_BY,
) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_type=artifact_type,
        payload=payload,
        created_by=created_by,
        model_name=model_name,
        scenario_name=scenario_name,
        trace_id=trace_id,
    )


def trace_artifact(
    trace: Trace,
    *,
    model_name: str = "",
    scenario_name: str = "",
    trace_id: str = "",
) -> ArtifactEnvelope:
    return make_artifact(
        "trace",
        trace.to_dict(),
        model_name=model_name,
        scenario_name=scenario_name,
        trace_id=trace_id,
    )


def report_artifact(
    report: Any,
    *,
    artifact_type: str = "report",
    model_name: str = "",
    scenario_name: str = "",
    trace_id: str = "",
) -> ArtifactEnvelope:
    payload = report.to_dict() if hasattr(report, "to_dict") else report
    return make_artifact(
        artifact_type,
        payload,
        model_name=model_name,
        scenario_name=scenario_name,
        trace_id=trace_id,
    )


__all__ = [
    "ArtifactEnvelope",
    "DEFAULT_CREATED_BY",
    "SCHEMA_VERSION",
    "make_artifact",
    "report_artifact",
    "trace_artifact",
]
