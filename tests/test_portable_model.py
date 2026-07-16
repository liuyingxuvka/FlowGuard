from __future__ import annotations

from copy import deepcopy
import unittest

from flowguard.portable_model import (
    PORTABLE_MODEL_SCHEMA_VERSION,
    PortableModel,
    PortableModelError,
    PortableState,
    PortableTransition,
    canonical_json_bytes,
    validate_portable_model,
)


def sample_model() -> PortableModel:
    return PortableModel(
        model_id="portable-sample",
        states=(PortableState("new", {"count": 0}), PortableState("done", {"count": 1})),
        transitions=(
            PortableTransition("complete-a", "new", {"kind": "go"}, "ok", "done"),
            PortableTransition("complete-b", "new", {"kind": "go"}, "cached", "done"),
        ),
        initial_state_ids=("new",),
        terminal_state_ids=("done",),
        assumptions=("request.valid",),
        guarantees=("request.completed",),
        metadata={"owner": "test"},
    )


class PortableModelTests(unittest.TestCase):
    def test_current_model_round_trips_with_stable_identity(self):
        model = sample_model()
        restored = PortableModel.from_dict(model.to_dict())
        self.assertEqual(PORTABLE_MODEL_SCHEMA_VERSION, restored.schema_version)
        self.assertEqual(model.fingerprint, restored.fingerprint)
        self.assertEqual(model.canonical_bytes, restored.canonical_bytes)

    def test_object_key_order_and_whitespace_do_not_change_identity(self):
        model = sample_model()
        payload = model.to_dict()
        reordered = {key: payload[key] for key in reversed(tuple(payload))}
        self.assertEqual(model.fingerprint, PortableModel.from_dict(reordered).fingerprint)
        self.assertEqual(canonical_json_bytes(payload), canonical_json_bytes(reordered))

    def test_semantic_transition_change_stales_identity(self):
        payload = sample_model().to_dict()
        changed = deepcopy(payload)
        changed["transitions"][0]["output_symbol"] = "different"
        self.assertNotEqual(
            PortableModel.from_dict(payload).fingerprint,
            PortableModel.from_dict(changed).fingerprint,
        )

    def test_nondeterministic_relation_is_preserved(self):
        model = PortableModel.from_dict(sample_model().to_dict())
        branches = [
            transition
            for transition in model.transitions
            if transition.source_state == "new" and transition.input_symbol == {"kind": "go"}
        ]
        self.assertEqual(2, len(branches))
        self.assertEqual({"ok", "cached"}, {item.output_symbol for item in branches})

    def test_retired_or_unknown_schema_is_rejected(self):
        payload = sample_model().to_dict()
        payload["schema_version"] = "flowguard.portable_model.v0"
        with self.assertRaisesRegex(PortableModelError, "schema_version"):
            PortableModel.from_dict(payload)

    def test_unknown_field_is_rejected(self):
        payload = sample_model().to_dict()
        payload["fallback_schema"] = "v0"
        with self.assertRaisesRegex(PortableModelError, "unknown fields"):
            PortableModel.from_dict(payload)

    def test_dangling_state_reference_is_rejected(self):
        payload = sample_model().to_dict()
        payload["transitions"][0]["target_state"] = "missing"
        with self.assertRaisesRegex(PortableModelError, "not declared"):
            PortableModel.from_dict(payload)

    def test_direct_invalid_model_reports_all_structural_errors(self):
        model = PortableModel(
            model_id="invalid",
            states=(PortableState("only"),),
            transitions=(PortableTransition("bad", "only", "go", "x", "missing"),),
            initial_state_ids=("absent",),
        )
        errors = validate_portable_model(model)
        self.assertTrue(any("initial state" in item for item in errors))
        self.assertTrue(any("target" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
