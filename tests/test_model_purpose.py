import copy
import tempfile
import unittest
from pathlib import Path

from flowguard.model_purpose import (
    ModelPurposeClosure,
    ModelPurposeError,
    build_model_purpose_closure,
    file_fingerprint,
    validate_unique_model_instances,
)


class ModelPurposeClosureTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.model = self.root / "model.py"
        self.runner = self.root / "run_checks.py"
        self.model.write_text("STATE = 'current'\n", encoding="utf-8")
        self.runner.write_text("print('native good and bad checks passed')\n", encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def make(self, *, instance="instance:one", failures=("failure:first",)):
        bindings = tuple(
            {
                "failure_id": failure,
                "known_bad_case_id": f"case:bad:{index}",
                "oracle_id": "native:route:oracle",
            }
            for index, failure in enumerate(failures)
        )
        return build_model_purpose_closure(
            model_instance_id=instance,
            reusable_model_type_id="reusable:model-type",
            task_intent_id=f"task:{instance.replace(':', '-')}",
            guarded_purpose="Prevent the current route from accepting missing or stale terminal evidence as a completed outcome.",
            protected_failure_ids=failures,
            known_good_case_id="case:known-good",
            failure_bindings=bindings,
            claim_boundary="This closure proves only the exact temporary candidate and native proof cases declared by this unit test.",
            evidence_check_ids=("check:native:route",),
            model_sha256=file_fingerprint(self.model),
            runner_sha256=file_fingerprint(self.runner),
        )

    def test_one_or_many_failures_close_under_one_instance(self):
        one = self.make()
        many = self.make(failures=("failure:first", "failure:second"))
        self.assertEqual(1, len(one.failure_bindings))
        self.assertEqual(2, len(many.failure_bindings))
        many.validate_current_files(self.root, model_path="model.py", runner_path="run_checks.py")

    def test_reusable_type_can_have_different_task_specific_instances(self):
        first = self.make(instance="instance:first")
        second = self.make(instance="instance:second", failures=("failure:other",))
        validate_unique_model_instances((first, second))
        self.assertEqual(first.reusable_model_type_id, second.reusable_model_type_id)
        self.assertNotEqual(first.task_intent_id, second.task_intent_id)

    def test_duplicate_instance_is_rejected(self):
        closure = self.make()
        with self.assertRaisesRegex(ModelPurposeError, "duplicate model_instance_id"):
            validate_unique_model_instances((closure, closure))

    def test_missing_good_or_bad_coverage_is_rejected(self):
        payload = self.make(failures=("failure:first", "failure:second")).to_dict()
        payload["failure_bindings"] = payload["failure_bindings"][:1]
        with self.assertRaisesRegex(ModelPurposeError, "exactly one known-bad"):
            ModelPurposeClosure.from_dict(payload)
        payload = self.make().to_dict()
        payload["known_good_case_id"] = ""
        with self.assertRaisesRegex(ModelPurposeError, "known_good_case_id"):
            ModelPurposeClosure.from_dict(payload)

    def test_post_hoc_or_placeholder_declaration_is_rejected(self):
        payload = self.make().to_dict()
        payload["declaration_phase"] = "after_candidate"
        with self.assertRaisesRegex(ModelPurposeError, "before candidate"):
            ModelPurposeClosure.from_dict(payload)
        payload = self.make().to_dict()
        payload["guarded_purpose"] = "todo"
        with self.assertRaisesRegex(ModelPurposeError, "non-placeholder"):
            ModelPurposeClosure.from_dict(payload)

    def test_unknown_fields_and_stale_fingerprints_are_rejected(self):
        payload = self.make().to_dict()
        payload["optional_mode"] = "shallow"
        with self.assertRaisesRegex(ModelPurposeError, "unknown purpose closure fields"):
            ModelPurposeClosure.from_dict(payload)
        closure = self.make()
        self.model.write_text("STATE = 'changed'\n", encoding="utf-8")
        with self.assertRaisesRegex(ModelPurposeError, "model candidate fingerprint is stale"):
            closure.validate_current_files(self.root, model_path="model.py", runner_path="run_checks.py")

    def test_disconnected_or_stale_declaration_identity_is_rejected(self):
        payload = copy.deepcopy(self.make().to_dict())
        payload["failure_bindings"][0]["failure_id"] = "failure:other"
        with self.assertRaisesRegex(ModelPurposeError, "exactly match"):
            ModelPurposeClosure.from_dict(payload)
        payload = self.make().to_dict()
        payload["claim_boundary"] += " changed"
        with self.assertRaisesRegex(ModelPurposeError, "declaration_fingerprint"):
            ModelPurposeClosure.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
