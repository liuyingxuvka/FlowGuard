"""Measure the bounded, invocation-local cost signals used by A11.

This is deliberately a small fixture, not a second validation runner.  It
records real wall time and byte/scan/decode counters for the JSON object-store
path and records zero-producer assertions from the already-targeted tests.
Provider token usage is not available from the local runtime and is therefore
reported as null rather than estimated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from flowguard.__main__ import _JsonObjectStoreLocator


def _measure_object_store() -> dict[str, object]:
    objects = {f"object:{index}": {"value": index} for index in range(10)}
    with tempfile.TemporaryDirectory(prefix="flowguard-cost-") as directory:
        path = Path(directory) / "objects.json"
        path.write_text(json.dumps(objects, separators=(",", ":")), encoding="utf-8")
        locator = _JsonObjectStoreLocator(path, "A11 object-store fixture")
        scan_count = 0
        decode_count = 0
        original_scan = locator._scan_value_end
        original_decode = locator._decode_slice

        def scan(start: int) -> int:
            nonlocal scan_count
            scan_count += 1
            return original_scan(start)

        def decode(start: int, end: int) -> object:
            nonlocal decode_count
            decode_count += 1
            return original_decode(start, end)

        requested = [f"object:{index}" for index in reversed(range(10))]
        started = time.perf_counter()
        with patch.object(locator, "_scan_value_end", side_effect=scan):
            with patch.object(locator, "_decode_slice", side_effect=decode):
                values = [locator.load(object_id) for object_id in requested]
                # One exact-current cache reuse must not decode again.
                values.append(locator.load(requested[0]))
        wall_time_ms = round((time.perf_counter() - started) * 1000, 3)
        locator.close()
        # One key decode accompanies each indexed member.  The cost claim is
        # about value materialization, so expose that count separately from
        # the lexical-key validation work.
        return {
            "fixture_objects": len(objects),
            "requested_objects": len(requested),
            "reused_objects": 1,
            "store_bytes": path.stat().st_size,
            "scan_value_end_count": scan_count,
            "decode_slice_count": decode_count,
            "indexed_key_decode_count": scan_count,
            "requested_value_decode_count": decode_count - scan_count,
            "loaded_values": len(values),
            "wall_time_ms": wall_time_ms,
            "claim": "one lexical index pass; requested values only are decoded",
        }


def build_report() -> dict[str, object]:
    return {
        "schema_version": "flowguard.route_cost_comparison.v1",
        "measurement_kind": "fixed_local_fixture",
        "generated_by": "scripts/measure_route_costs.py",
        "token_usage": None,
        "token_usage_status": "not_measured",
        "metrics": {
            "affected_map_read": {
                "producer_count": 0,
                "author_assurance_subprocess_count": 0,
                "source": [
                    "tests/test_blueprint_cli_routes.py::test_affected_blueprint_understanding_is_read_only",
                    "tests/test_flowguard_skill_suite_profiles.py::test_light_profile_does_not_spawn_author_assurance",
                ],
                "status": "asserted_by_targeted_tests",
            },
            "json_object_store": _measure_object_store(),
            "affected_child_closure": {
                "unrelated_child_objects_loaded": 0,
                "source": "tests/test_affected_blueprint_reader.py::test_child_seed_propagates_to_ancestor_without_reopening_unrelated_siblings",
                "status": "asserted_by_targeted_test",
            },
        },
        "interpretation": {
            "producer_savings": "read-only map/light paths are zero-producer",
            "index_savings": "10 reverse-order requests use one lexical scan and <=10 value decodes",
            "topology_savings": "unrelated sibling/child objects remain unloaded",
            "token_claim": "provider token consumption is not locally measurable",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
