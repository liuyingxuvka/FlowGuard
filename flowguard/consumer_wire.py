"""Small, cross-project wire identity for ``consumer-release.json``.

The consumer release manifest crosses the FlowGuard/SkillGuard repository
boundary. Keep its serialization and digest rules in one tiny module so the
producer can be compared directly with the independent SkillGuard auditor
without importing either project's author-side runtime.
"""

from __future__ import annotations

import hashlib
import json
import re


CONSUMER_RELEASE_WIRE_POLICY_ID = "consumer.skill_distribution.wire.current"
CONSUMER_RELEASE_WIRE_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def consumer_release_canonical_json_bytes(payload: object) -> bytes:
    """Serialize one release identity with the current compact wire rules."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def consumer_release_wire_hash_bytes(payload: bytes) -> str:
    """Hash wire bytes as lowercase ``sha256:<64 hex>``."""

    return "sha256:" + hashlib.sha256(payload).hexdigest()


def consumer_release_wire_hash(payload: object) -> str:
    """Hash one JSON value under the current consumer-release policy."""

    return consumer_release_wire_hash_bytes(
        consumer_release_canonical_json_bytes(payload)
    )


def is_consumer_release_wire_hash(value: object) -> bool:
    """Return whether a value is a current lowercase wire digest."""

    return (
        isinstance(value, str)
        and CONSUMER_RELEASE_WIRE_HASH_PATTERN.fullmatch(value) is not None
    )


__all__ = [
    "CONSUMER_RELEASE_WIRE_POLICY_ID",
    "CONSUMER_RELEASE_WIRE_HASH_PATTERN",
    "consumer_release_canonical_json_bytes",
    "consumer_release_wire_hash",
    "consumer_release_wire_hash_bytes",
    "is_consumer_release_wire_hash",
]
