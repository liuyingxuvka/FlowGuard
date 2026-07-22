import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flowguard.portable_model import PortableModel, PortableModelError, PortableState, PortableTransition
from flowguard.portable_system import (
    PortableSystemDefinition,
    SystemComponentRef,
    SystemCompositionRequest,
    SystemDependency,
    SystemProperty,
    SystemStatePattern,
    SystemStep,
    SystemTransitionRef,
    derive_system_slice,
    write_portable_system,
    write_system_composition_request,
)
from flowguard.system_composition import check_system_composition


def component(model_id: str, source: str, target: str, transition_id: str) -> PortableModel:
    return PortableModel(
        model_id=model_id,
        states=(PortableState(source), PortableState(target)),
        transitions=(PortableTransition(transition_id, source, transition_id, transition_id, target),),
        initial_state_ids=(source,),
        terminal_state_ids=(target,),
    )


def system(models, *, atomic: bool = False, temporal: bool = False) -> PortableSystemDefinition:
    left, right = models
    steps = (
        (SystemStep("commit-and-consume", (SystemTransitionRef("order", "commit"), SystemTransitionRef("index", "consume"))),)
        if atomic
        else (
            SystemStep("commit", (SystemTransitionRef("order", "commit"),)),
            SystemStep("consume", (SystemTransitionRef("index", "consume"),)),
        )
    )
    patterns = (
        SystemStatePattern("initial", (("order", "ready"), ("index", "pending"))),
        SystemStatePattern("unsafe", (("order", "done"), ("index", "pending"))),
        SystemStatePattern("complete", (("order", "done"), ("index", "done"))),
    )
    properties = (
        SystemProperty("eventual-index", "owner:index", "eventually", ("initial",), ("complete",))
        if temporal
        else SystemProperty("no-unindexed-commit", "owner:order", "safety", target_pattern_ids=("unsafe",))
    ,)
    return PortableSystemDefinition(
        system_id="order-index",
        components=(
            SystemComponentRef("order", left.model_id, left.fingerprint),
            SystemComponentRef("index", right.model_id, right.fingerprint),
        ),
        dependencies=(SystemDependency("order-index-event", "order", "index", "event"),),
        ports=(), bindings=(), resources=(), steps=steps, state_patterns=patterns, properties=properties,
        discovery_evidence_id="fixture:order-index",
    )


class PortableSystemTests(unittest.TestCase):
    def setUp(self):
        self.models = (
            component("order-model", "ready", "done", "commit"),
            component("index-model", "pending", "done", "consume"),
        )

    def request(self, definition, max_states=20):
        return SystemCompositionRequest("request-1", definition.system_id, definition.fingerprint, ("order",), max_states=max_states)

    def test_definition_identity_is_order_independent(self):
        first = system(self.models)
        payload = first.to_dict()
        payload["components"].reverse()
        payload["steps"].reverse()
        second = PortableSystemDefinition.from_dict(payload)
        self.assertEqual(first.fingerprint, second.fingerprint)

    def test_strict_shape_rejects_unknown_field(self):
        payload = system(self.models).to_dict()
        payload["legacy_alias"] = True
        with self.assertRaises(PortableModelError):
            PortableSystemDefinition.from_dict(payload)

    def test_declared_graph_slice_closes_dependency(self):
        definition = system(self.models)
        slice_ = derive_system_slice(definition, self.request(definition))
        self.assertTrue(slice_.complete)
        self.assertEqual(("index", "order"), slice_.included_component_ids)
        self.assertNotEqual(definition.fingerprint, slice_.fingerprint)

    def test_local_and_token_green_can_be_system_red(self):
        definition = system(self.models)
        report = check_system_composition(definition, self.request(definition), self.models)
        self.assertEqual("fail", report.status)
        self.assertEqual("pass", report.stages["component_local"])
        self.assertEqual("pass", report.stages["contract_composition"])
        self.assertEqual("fail", report.stages["system_composition"])
        self.assertTrue(report.counterexamples)
        self.assertEqual("commit", report.counterexamples[0].steps[0].system_step_id)

    def test_atomic_repair_passes(self):
        definition = system(self.models, atomic=True)
        report = check_system_composition(definition, self.request(definition), self.models)
        self.assertEqual("pass", report.status)
        self.assertEqual(2, report.explored_state_count)

    def test_final_system_graph_uses_one_canonical_checker_invocation(self):
        import flowguard.system_composition as composition_module

        definition = system(self.models, atomic=True)
        original = composition_module.check_portable_model
        system_calls = []

        def recording_check(model, **kwargs):
            if model.model_id.startswith("system:"):
                system_calls.append(model.model_id)
            return original(model, **kwargs)

        with mock.patch.object(composition_module, "check_portable_model", side_effect=recording_check):
            report = composition_module.check_system_composition(definition, self.request(definition), self.models)
        self.assertEqual("pass", report.status)
        self.assertEqual(1, len(system_calls))

    def test_clean_truncation_is_blocked(self):
        definition = system(self.models)
        report = check_system_composition(definition, self.request(definition, max_states=1), self.models)
        self.assertEqual("blocked", report.status)
        self.assertEqual("blocked", report.stages["system_composition"])
        self.assertTrue(report.frontier_ids)

    def test_confirmed_safety_witness_survives_truncation(self):
        definition = system(self.models)
        report = check_system_composition(definition, self.request(definition, max_states=2), self.models)
        self.assertEqual("fail", report.status)
        self.assertTrue(report.frontier_ids)
        self.assertIn("residual", " ".join(report.residual_risk))

    def test_temporal_prefix_does_not_become_failure(self):
        definition = system(self.models, temporal=True)
        report = check_system_composition(definition, self.request(definition, max_states=2), self.models)
        self.assertEqual("blocked", report.status)
        self.assertIsNone(report.system_report)

    def test_stale_component_fingerprint_is_blocked(self):
        definition = system(self.models)
        payload = definition.to_dict()
        payload["components"][0]["model_fingerprint"] = "sha256:stale"
        stale = PortableSystemDefinition.from_dict(payload)
        report = check_system_composition(stale, self.request(stale), self.models)
        self.assertEqual("blocked", report.status)

    def test_missing_component_is_invalid(self):
        definition = system(self.models)
        report = check_system_composition(definition, self.request(definition), self.models[:1])
        self.assertEqual("invalid", report.status)

    def test_request_subset_cannot_omit_closure_member(self):
        definition = system(self.models)
        request = SystemCompositionRequest("request-1", definition.system_id, definition.fingerprint, ("order",), requested_component_ids=("order",))
        report = check_system_composition(definition, request, self.models)
        self.assertEqual("blocked", report.status)
        self.assertIn("omits closure", " ".join(report.blockers))

    def test_public_api_registry_exposes_one_system_cohort(self):
        import flowguard

        self.assertIn("check_system_composition", flowguard.PORTABLE_VERIFICATION_API)
        self.assertIn("PortableSystemDefinition", flowguard.PORTABLE_VERIFICATION_API)
        self.assertNotIn("_compile", flowguard.PORTABLE_VERIFICATION_API)

    def test_cli_and_api_have_status_and_identity_parity(self):
        definition = system(self.models, atomic=True)
        request = self.request(definition)
        expected = check_system_composition(definition, request, self.models)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            system_path = write_portable_system(definition, root / "system.json")
            request_path = write_system_composition_request(request, root / "request.json")
            component_paths = []
            for model in self.models:
                path = root / f"{model.model_id}.json"
                path.write_text(json.dumps(model.to_dict()), encoding="utf-8")
                component_paths.append(path)
            command = [sys.executable, "-m", "flowguard", "portable-system-check", "--system", str(system_path), "--request", str(request_path), "--json"]
            for path in component_paths:
                command.extend(("--component", str(path)))
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(0, completed.returncode, completed.stderr)
        actual = json.loads(completed.stdout)
        self.assertEqual(expected.status, actual["status"])
        self.assertEqual(expected.slice_fingerprint, actual["slice_fingerprint"])
        self.assertEqual(expected.compiled_model_fingerprint, actual["compiled_model_fingerprint"])


if __name__ == "__main__":
    unittest.main()
