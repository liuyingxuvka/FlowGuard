import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard import (
    behavior_commitment_ledger_from_mapping,
    behavior_commitment_ledger_to_mapping,
)
from flowguard.__main__ import main as flowguard_cli_main
from flowguard.templates import (
    architecture_reduction_template_files,
    behavior_commitment_ledger_template_files,
    code_structure_template_files,
    contract_exhaustion_template_files,
    field_lifecycle_template_files,
    model_mesh_template_files,
    model_test_alignment_full_template_files,
    model_test_alignment_template_files,
    primary_path_authority_template_files,
    topology_hazard_template_files,
    ui_flow_structure_full_template_files,
    ui_flow_structure_template_files,
    write_template_files,
)
from flowguard.risk_templates import (
    TemplateHarvestReview,
    harvest_risk_template_candidate,
    review_template_harvest_closure,
    search_risk_templates,
)


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_TEMPLATE_FACTORIES = (
    architecture_reduction_template_files,
    behavior_commitment_ledger_template_files,
    primary_path_authority_template_files,
    model_test_alignment_template_files,
    code_structure_template_files,
    field_lifecycle_template_files,
    ui_flow_structure_template_files,
    model_mesh_template_files,
    contract_exhaustion_template_files,
    topology_hazard_template_files,
)

TEMPLATE_CLI_COMMANDS = {
    "architecture-reduction-template": "architecture_reduction",
    "behavior-commitment-ledger-template": "behavior_commitment_ledger",
    "primary-path-authority-template": "primary_path_authority",
    "model-test-alignment-template": "model_test_alignment",
    "model-test-alignment-full-template": "model_test_alignment_full",
    "code-structure-template": "code_structure",
    "field-lifecycle-template": "field_lifecycle",
    "ui-flow-structure-template": "ui_flow_structure",
    "ui-flow-structure-full-template": "ui_flow_structure_full",
    "model-mesh-template": "model_mesh",
    "contract-exhaustion-template": "contract_exhaustion",
    "topology-hazard-template": "model_topology_hazard_review",
}


def _template_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


class PublicTemplateTests(unittest.TestCase):
    def run_written_template(self, files, run_dir_parts, expected_returncode=0, fill=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_template_files(root, files)
            if fill:        # name real code where the template ships REPLACE_ME placeholder anchors
                for path in root.rglob("*"):
                    if path.is_file() and "REPLACE_ME" in path.read_text(encoding="utf-8"):
                        path.write_text(path.read_text(encoding="utf-8").replace("REPLACE_ME", "app"), encoding="utf-8")
                (root / "app").mkdir()
                (root / "app/module.py").write_text("class Owner:\n    pass\n", encoding="utf-8")
                (root / "app/request.py").write_text("def parse_request(data):\n    return data\n", encoding="utf-8")
                (root / "app/workflow.py").write_text("def run_primary_workflow():\n    return 'done'\n", encoding="utf-8")
                (root / "app/test_workflow.py").write_text("def test_primary_workflow():\n    assert True\n",
                                                           encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "run_checks.py"],
                cwd=root.joinpath(*run_dir_parts),
                env=_template_env(),
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(expected_returncode, result.returncode, result.stdout + result.stderr)
        return result.stdout

    def run_kit_template(self, files, model_id, code, *, fill="", expected_returncode=None, components=None):
        """Write a model-kit template into a tiny git project, list it in the map and run it.

        ``components`` ({id: files}) replaces the scanned components; the model is listed in the first one.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel, text in code.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(text, encoding="utf-8")
            subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
            write_template_files(root, files)
            model = root / files[0].path
            if fill:
                model.write_text(model.read_text(encoding="utf-8").replace("REPLACE_ME", fill), encoding="utf-8")

            def flowguard_map(*args):
                return subprocess.run([sys.executable, "-m", "flowguard", "map", *args], cwd=root, env=_template_env(),
                                      text=True, capture_output=True, check=False)

            flowguard_map("scan")
            data = json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))
            if components:
                data["components"] = [dict(data["components"][0], id=cid, files=paths, tests=[], models=[])
                                      for cid, paths in components.items()]
            data["components"][0]["models"] = [files[0].path]
            (root / ".flowguard/map.json").write_text(json.dumps(data), encoding="utf-8")
            result = flowguard_map("models", model_id)
        if expected_returncode is not None:
            self.assertEqual(expected_returncode, result.returncode, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                return_code = flowguard_cli_main(list(argv))
        except SystemExit as exc:
            return_code = int(exc.code or 0)
        return return_code, stdout.getvalue(), stderr.getvalue()

    def test_template_text_is_route_scoped_behind_public_facade(self):
        template_text_root = ROOT / "flowguard" / "template_text"
        route_modules = {path.stem for path in template_text_root.glob("*.py") if path.name != "__init__.py"}

        self.assertIn("ui_flow_structure", route_modules)
        self.assertNotIn("model_similarity_consolidation", route_modules)
        self.assertNotIn("risk_evidence_ledger", route_modules)
        self.assertIn("UIInteractionModel", (template_text_root / "ui_flow_structure.py").read_text(encoding="utf-8"))

    def test_active_ui_guidance_does_not_hardcode_specific_source_technology(self):
        forbidden_terms = (
            "MATLAB",
            "matlab",
            "uigetfile",
            "uigetdir",
            "winopen",
            "MATLABBaselineCallbackGate",
            "MATLABCallbackSemantics",
            "review_matlab_baseline_callback_gate",
            "matlab_callback",
            "baseline_callback",
            "covered_callback_ids",
            "UI_EVIDENCE_ROLE_BASELINE_SEMANTICS",
            "ui_baseline_semantics",
        )
        roots = (ROOT / "flowguard", ROOT / "docs", ROOT / ".agents" / "skills", ROOT / "openspec" / "changes")
        suffixes = {".py", ".md", ".txt", ".toml", ".yaml", ".yml", ".json"}
        ignored_parts = {
            ".git",
            "__pycache__",
            "archive",
        }
        ignored_names = {
            "CHANGELOG.md",
            "flowguard_adoption_log.md",
        }
        offenders = []
        for root in roots:
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in suffixes:
                    continue
                if ignored_parts.intersection(path.parts) or path.name in ignored_names:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                hits = [term for term in forbidden_terms if term in text]
                if hits:
                    offenders.append(f"{path.relative_to(ROOT)}: {', '.join(hits)}")

        self.assertEqual([], offenders)

    def test_runner_templates_fail_until_their_anchors_name_real_code(self):
        runners = {"behavior_commitment_ledger": behavior_commitment_ledger_template_files,
                   "primary_path_authority": primary_path_authority_template_files,
                   "model_test_alignment": model_test_alignment_template_files,
                   "model_mesh": model_mesh_template_files,
                   "ui_flow_structure": ui_flow_structure_full_template_files,
                   "model_topology_hazard_review": topology_hazard_template_files}
        for directory, factory in runners.items():
            with self.subTest(template=directory):
                output = self.run_written_template(factory(), (".flowguard", "verification", "owners", directory),
                                                   expected_returncode=1, fill=False)
                self.assertIn("placeholder anchor 'REPLACE_ME/module.py:Owner'", output)

    def test_behavior_commitment_ledger_template_executes(self):
        output = self.run_written_template(
            behavior_commitment_ledger_template_files(),
            (".flowguard", "verification", "owners", "behavior_commitment_ledger"),
        )
        self.assertIn("flowguard behavior commitment ledger", output)
        self.assertIn("full_inventory_registered: yes", output)
        self.assertIn("behavior_commitment_coverage_green", output)

    def test_behavior_commitment_template_has_one_canonical_ledger_authority(self):
        files = behavior_commitment_ledger_template_files()
        by_path = {file.path: file.content for file in files}

        self.assertIn(".flowguard/behavior/inventory/ledger.json", by_path)
        payload = json.loads(by_path[".flowguard/behavior/inventory/ledger.json"])
        canonical = behavior_commitment_ledger_from_mapping(payload)
        self.assertEqual(payload, behavior_commitment_ledger_to_mapping(canonical))
        commitment = payload["ledger"]["commitments"][0]
        self.assertEqual("product_runtime", commitment["behavior_plane"])
        self.assertEqual("end_user", commitment["actor_kind"])
        self.assertEqual("intent:run-primary-workflow", commitment["business_intent_id"])
        model_text = by_path[".flowguard/models/owners/behavior_commitment_ledger/model.py"]
        self.assertIn("load_behavior_commitment_ledger", model_text)
        self.assertNotIn("BehaviorCommitment(", model_text)

    def test_primary_path_authority_template_executes(self):
        output = self.run_written_template(
            primary_path_authority_template_files(),
            (".flowguard", "verification", "owners", "primary_path_authority"),
        )
        self.assertIn("Primary Path Authority checks passed", output)
        self.assertIn("primary_path_authority_green", output)

    def test_model_test_alignment_template_executes(self):
        output = self.run_written_template(model_test_alignment_template_files(),
            (".flowguard", "verification", "owners", "model_test_alignment"))
        self.assertIn("flowguard model-test alignment", output)
        self.assertIn("design-ready scaffold; target execution: not_run", output)
        self.assertIn("test_evidence_not_passing", output)


    def test_model_test_alignment_template_fails_when_its_plan_names_missing_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_template_files(root, model_test_alignment_template_files())
            for path in root.rglob("*.py"):
                path.write_text(path.read_text(encoding="utf-8").replace("REPLACE_ME", "app"), encoding="utf-8")
            (root / "app").mkdir()
            (root / "app/module.py").write_text("class Owner:\n    pass\n", encoding="utf-8")   # no app/request.py
            result = subprocess.run([sys.executable, "run_checks.py"], env=_template_env(), text=True,
                                    cwd=root / ".flowguard" / "verification" / "owners" / "model_test_alignment",
                                    capture_output=True, check=False)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("anchor app/request.py:parse_request exists: anchor file missing: app/request.py", result.stdout)

    def test_model_test_alignment_full_template_executes_all_six_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_template_files(root, model_test_alignment_full_template_files())
            result = subprocess.run(
                [sys.executable, "-c", "import json, run_checks; "
                 "print(json.dumps([report.ok for report in run_checks.run_checks()]))"],
                cwd=root / ".flowguard" / "verification" / "owners" / "model_test_alignment",
                env=_template_env(),
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        # Alignment, boundary conformance and source audit each reject their bad example.
        self.assertEqual([True, False, True, False, True, False], json.loads(result.stdout))

    def test_model_mesh_template_executes_and_exposes_negative_fixture(self):
        output = self.run_written_template(
            model_mesh_template_files(),
            (".flowguard", "verification", "owners", "model_mesh"),
        )
        self.assertIn("flowguard hierarchical mesh", output)
        self.assertIn("decision:", output)
        self.assertIn("missing", output.lower())
        self.assertNotIn("negative-case matrix: PASS", output)

    def test_contract_exhaustion_template_runs_the_bad_cases_against_the_real_function(self):
        files = contract_exhaustion_template_files()
        strict = {"shop/orders.py": "def place(order_id, amount):\n"
                  "    if not isinstance(order_id, str) or not order_id or not isinstance(amount, int):\n"
                  "        raise ValueError('bad input')\n    return 'placed'\n"}
        lax = {"shop/orders.py": "def place(order_id, amount):\n    return 'placed'\n"}
        self.assertIn("placeholder anchor", self.run_kit_template(files, "contract_exhaustion", strict,
                                                                  expected_returncode=1))
        self.assertIn("PASS  contract_exhaustion", self.run_kit_template(files, "contract_exhaustion", strict,
                                                                         fill="shop", expected_returncode=0))
        output = self.run_kit_template(files, "contract_exhaustion", lax, fill="shop", expected_returncode=1)
        self.assertIn("executed against code: 22 of 22 feature combinations; declared only: 0; errors: 0; "
                      "counterexamples: 21", output)
        self.assertIn("- each_defect_rejected: contract:order_id:missing_required_field: expected rejected, "
                      "observed accepted", output)

    def test_code_structure_template_compares_the_split_with_the_code_and_the_map(self):
        files = code_structure_template_files()
        code = {"shop/orders.py": "from shop.pricing import price_order\n\n\ndef place_order(order):\n"
                                  "    return {'total': price_order(order)}\n",
                "shop/pricing.py": "def price_order(order):\n    return order['amount']\n"}
        split = {"orders": ["shop/orders.py"], "pricing": ["shop/pricing.py"]}
        self.assertIn("placeholder anchor", self.run_kit_template(files, "code_structure", code, components=split,
                                                                  expected_returncode=1))
        self.assertIn("PASS  code_structure", self.run_kit_template(files, "code_structure", code, fill="shop",
                                                                    components=split, expected_returncode=0))
        other_owner = {"orders": ["shop/orders.py"], "billing": ["shop/pricing.py"]}
        self.assertIn("- PriceOrder: owner file shop/pricing.py belongs to map component orders: "
                      "shop/pricing.py belongs to billing",
                      self.run_kit_template(files, "code_structure", code, fill="shop", components=other_owner,
                                            expected_returncode=1))
        renamed = {"shop/orders.py": code["shop/orders.py"], "shop/prices.py": code["shop/pricing.py"]}
        self.assertIn("IMPLEMENTED_BY PriceOrder -> anchor file missing: shop/pricing.py",
                      self.run_kit_template(files, "code_structure", renamed, fill="shop", components=split,
                                            expected_returncode=1))

    def test_architecture_reduction_template_fails_when_removed_code_is_still_referenced(self):
        files = architecture_reduction_template_files()
        code = {"shop/orders.py": "def validate(order):\n    return bool(order)\n\n\ndef validate_v2(order):\n"
                                  "    return bool(order)\n\n\ndef place_order(order):\n    return validate(order)\n",
                "shop/api.py": "from shop.orders import validate\n\n\ndef create(order):\n    return validate(order)\n"}
        self.assertIn("placeholder anchor", self.run_kit_template(files, "architecture_reduction", code,
                                                                  expected_returncode=1))
        self.assertIn("PASS  architecture_reduction", self.run_kit_template(files, "architecture_reduction", code,
                                                                            fill="shop", expected_returncode=0))
        caller = dict(code, **{"shop/api.py": code["shop/api.py"] + "\n\nLEGACY = validate_v2\n"})
        caller["shop/api.py"] = caller["shop/api.py"].replace("import validate\n", "import validate, validate_v2\n")
        output = self.run_kit_template(files, "architecture_reduction", caller, fill="shop", expected_returncode=1)
        self.assertIn("invariant: removed_code_unreferenced", output)
        self.assertIn("shop/orders.py:validate_v2 is still referenced at shop/api.py:1, shop/api.py:8", output)
        unused = dict(code, **{"shop/api.py": "def create(order):\n    return bool(order)\n"})
        self.assertIn("known-bad variant 'remove_validate_still_called' passed",
                      self.run_kit_template(files, "architecture_reduction", unused, fill="shop", expected_returncode=1))

    def test_ui_flow_structure_template_compares_controls_with_the_ui_source(self):
        files = ui_flow_structure_template_files()
        ui = {"web/index.html": '<button id="show">Show</button><button id="hide">Hide</button>\n',
              "web/app.js": "function showDetails() {}\nfunction hideDetails() {}\n"}
        self.assertIn("placeholder anchor", self.run_kit_template(files, "ui_flow_structure", ui, expected_returncode=1))
        self.assertIn("PASS  ui_flow_structure", self.run_kit_template(files, "ui_flow_structure", ui, fill="web",
                                                                       expected_returncode=0))
        missing = dict(ui, **{"web/index.html": '<button id="show">Show</button>\n'})
        self.assertIn("control hide is in the UI source",
                      self.run_kit_template(files, "ui_flow_structure", missing, fill="web", expected_returncode=1))


    def test_ui_flow_structure_full_template_executes_content_visibility_cases(self):
        output = self.run_written_template(
            ui_flow_structure_full_template_files(),
            (".flowguard", "verification", "owners", "ui_flow_structure"),
        )

        self.assertIn("flowguard UI content visibility review", output)
        self.assertIn("internal_content_mapped_to_ui", output)
        self.assertIn("unknown_content_visibility_class", output)
        self.assertIn("on_demand_content_visible_in_default_state", output)
        self.assertIn("flowguard UI product consistency review", output)
        self.assertIn("product_semantic_drift", output)

    def test_topology_hazard_template_executes(self):
        output = self.run_written_template(
            topology_hazard_template_files(),
            (".flowguard", "verification", "owners", "model_topology_hazard_review"),
            expected_returncode=1,
        )
        self.assertIn("flowguard topology hazard review", output)
        self.assertIn("topology_hazard_blocked", output)
        self.assertIn("unresolved_hazard_ids", output)

    def test_topology_hazard_template_good_review_exits_zero(self):
        from dataclasses import replace

        files = topology_hazard_template_files()
        good_review = """
def build_review():
    from flowguard import TOPOLOGY_USAGE_LOCAL
    plan = infer_topology_hazard_plan(
        workflow=Workflow((SaveRecord(),), name="save-record"),
        initial_states=(State(),), external_inputs=(),
        usage_intent=UsageIntent(usage_modes=(TOPOLOGY_USAGE_LOCAL,), final_claim="local"),
    )
    return review_topology_hazards(plan)
"""
        files = tuple(replace(file, content=file.content + good_review)
                      if file.path.endswith("model.py") else file for file in files)
        output = self.run_written_template(
            files, (".flowguard", "verification", "owners", "model_topology_hazard_review"),
        )
        self.assertIn("topology_hazard_pass", output)

    def test_field_lifecycle_template_fails_until_bound_to_real_code(self):
        files = field_lifecycle_template_files()
        code = {"shop/orders.py": "class Order:\n    mode = 'fast'\n"}
        self.assertIn("placeholder anchor", self.run_kit_template(files, "field_lifecycle", code, expected_returncode=1))
        self.assertIn("PASS  field_lifecycle", self.run_kit_template(files, "field_lifecycle", code, fill="shop",
                                                                     expected_returncode=0))
        stale = {"shop/orders.py": code["shop/orders.py"] + "    old_mode = None\n"}
        self.assertIn("field:old_mode: deleted field has no reference left",
                      self.run_kit_template(files, "field_lifecycle", stale, fill="shop", expected_returncode=1))

    def test_template_cli_prints_and_writes_new_templates(self):
        factories = {
            factory.__name__.removesuffix("_template_files"): factory
            for factory in PUBLIC_TEMPLATE_FACTORIES
        }
        factories["model_test_alignment_full"] = model_test_alignment_full_template_files
        factories["ui_flow_structure_full"] = ui_flow_structure_full_template_files
        factories["model_topology_hazard_review"] = topology_hazard_template_files
        for command, template_name in TEMPLATE_CLI_COMMANDS.items():
            self.assertIn(template_name, factories, command)
            files = factories[template_name]()
            self.assertTrue(files, command)

            with tempfile.TemporaryDirectory() as directory:
                write_template_files(directory, files)
                written_paths = tuple(Path(directory).rglob("*"))
                self.assertTrue(written_paths, command)

        # Every starter template is reachable through one CLI verb.
        code, stdout, _stderr = self.run_cli(["template", "--list"])
        self.assertEqual(0, code)
        listed = stdout.split()
        self.assertNotIn("project", listed)
        self.assertIn("ui-flow-structure-full", listed)
        for name in listed:
            code, stdout, stderr = self.run_cli(["template", name])
            self.assertEqual(0, code, name + stderr)
            self.assertIn("===== ", stdout, name)
        with tempfile.TemporaryDirectory() as directory:
            code, stdout, _stderr = self.run_cli(["template", "model-mesh", "--write", directory])
            self.assertEqual(0, code)
            self.assertTrue(any(Path(directory).rglob("run_checks.py")))
            code, _stdout, stderr = self.run_cli(["template", "model-mesh", "--write", directory])
            self.assertEqual(1, code)
            self.assertIn("--force", stderr)
        code, _stdout, _stderr = self.run_cli(["template", "no-such-template"])
        self.assertEqual(2, code)

    def test_risk_template_cli_searches_and_harvests(self):
        search_report = search_risk_templates(
            "completion evidence",
            include_local=False,
        )
        self.assertEqual(("public",), search_report.searched_layers)
        self.assertEqual(
            "completion_requires_evidence",
            search_report.matches[0].template.template_id,
        )

        harvest_report = harvest_risk_template_candidate(
            template_id="cli_sample",
            title="CLI sample",
            summary="CLI sample.",
            protected_error_classes=("premature_completion",),
            required_state=("completed",),
            required_evidence=("completion_receipt",),
            known_bad_cases=("ack_only",),
            known_bad_proofs=(
                {
                    "case_id": "ack_only",
                    "protected_error_class": "premature_completion",
                    "method": "broken_workflow_variant",
                    "observed_status": "failed",
                    "observed_failure": "ack-only completion was rejected",
                    "evidence_id": "cli:known-bad",
                },
            ),
            write=False,
        )
        self.assertTrue(harvest_report.ok)
        self.assertEqual("candidate_ready", harvest_report.status)
        self.assertEqual("", harvest_report.path)

        closure = review_template_harvest_closure(
            TemplateHarvestReview(
                disposition="duplicate_linked",
                linked_template_ids=("completion_requires_evidence",),
            )
        )
        self.assertTrue(closure.ok)

    def test_public_templates_do_not_contain_local_project_markers(self):
        home_path = Path.home()
        private_markers = [
            "C:" + "\\Users",
            "FlowGuardProjectAutopilot",
            "FlowPilot",
            "Cockpit",
            "heartbeat",
        ]
        if home_path.name.lower() not in {"runner", "root"}:
            private_markers.append(str(home_path))
        for factory in PUBLIC_TEMPLATE_FACTORIES:
            with self.subTest(factory=factory.__name__):
                for file in factory():
                    for marker in private_markers:
                        self.assertNotIn(marker, file.content)


if __name__ == "__main__":
    unittest.main()
