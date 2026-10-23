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
from flowguard.__main__ import main as flowguard_cli_main, template_factories
from flowguard.templates import (
    behavior_commitment_template_files,
    code_structure_template_files,
    contract_exhaustion_template_files,
    field_lifecycle_template_files,
    model_mesh_template_files,
    model_test_alignment_template_files,
    topology_hazard_template_files,
    ui_flow_structure_template_files,
    write_template_files,
)


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_TEMPLATE_FACTORIES = (
    behavior_commitment_template_files,
    model_test_alignment_template_files,
    code_structure_template_files,
    field_lifecycle_template_files,
    ui_flow_structure_template_files,
    model_mesh_template_files,
    contract_exhaustion_template_files,
    topology_hazard_template_files,
)

TEMPLATE_CLI_COMMANDS = {
    "behavior-commitment-template": "behavior_commitment",
    "model-test-alignment-template": "model_test_alignment",
    "code-structure-template": "code_structure",
    "field-lifecycle-template": "field_lifecycle",
    "ui-flow-structure-template": "ui_flow_structure",
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
            for written in (root / file.path for file in files) if fill else ():
                written.write_text(written.read_text(encoding="utf-8").replace("REPLACE_ME", fill), encoding="utf-8")

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

    def test_behavior_commitment_template_has_one_canonical_ledger_authority(self):
        files = behavior_commitment_template_files()
        by_path = {file.path: file.content for file in files}

        self.assertIn(".flowguard/behavior/inventory/ledger.json", by_path)
        payload = json.loads(by_path[".flowguard/behavior/inventory/ledger.json"])
        canonical = behavior_commitment_ledger_from_mapping(payload)
        self.assertEqual(payload, behavior_commitment_ledger_to_mapping(canonical))
        commitment = payload["ledger"]["commitments"][0]
        self.assertEqual("product_runtime", commitment["behavior_plane"])
        self.assertEqual("intent:submit-order", commitment["business_intent_id"])
        model_text = by_path[".flowguard/models/behavior_commitment.py"]
        self.assertIn("load_behavior_commitment_ledger", model_text)
        self.assertNotIn("BehaviorCommitment(", model_text)

    def test_behavior_commitment_template_binds_promises_paths_and_tests_to_the_code(self):
        files = behavior_commitment_template_files()
        code = {"shop/orders.py": "def submit_order(order):\n    return order\n",
                "shop/orders_v1.py": "from shop.orders import submit_order\n\n\ndef submit(order):\n"
                                     "    return submit_order(order)\n",
                "shop/test_orders.py": "from shop.orders import submit_order\n\n\ndef test_submit_order():\n"
                                       "    assert submit_order({'id': 1})\n"}
        self.assertIn("placeholder anchor", self.run_kit_template(files, "behavior_commitment", code,
                                                                  expected_returncode=1))
        self.assertIn("PASS  behavior_commitment", self.run_kit_template(files, "behavior_commitment", code,
                                                                         fill="shop", expected_returncode=0))
        untouched = dict(code, **{"shop/test_orders.py": "def test_submit_order():\n    assert {'id': 1}\n"})
        output = self.run_kit_template(files, "behavior_commitment", untouched, fill="shop", expected_returncode=1)
        self.assertIn("invariant: commitment_tests_touch_entrypoints", output)
        self.assertIn("shop/test_orders.py never imports or calls shop/orders.py:submit_order", output)
        own_logic = dict(code, **{"shop/orders_v1.py": "def submit(order):\n    return dict(order, via='v1')\n"})
        self.assertIn("shop/orders_v1.py never imports or calls shop/orders.py:submit_order",
                      self.run_kit_template(files, "behavior_commitment", own_logic, fill="shop",
                                            expected_returncode=1))

    def alignment_code(self):
        return {"shop/module.py": "class Owner:\n    def __init__(self): self.ready = True\n",
                "shop/test_module.py": "from shop.module import Owner\ndef test_owner():\n    assert isinstance(Owner(), Owner)\n",
                ".flowguard/models/shop.py": 'MODEL_ID="shop"\nPARENT="system"\nIMPLEMENTED_BY={"Owner":"shop/module.py:Owner"}\nTESTED_BY={"owner":["shop/test_module.py:test_owner"]}\ndef build_explorer(): pass\n'}

    def test_model_test_alignment_template_executes(self):
        files = model_test_alignment_template_files()
        self.assertEqual([".flowguard/models/model_test_alignment.py"], [f.path for f in files])
        code = self.alignment_code()
        output = self.run_kit_template(files, "model_test_alignment", code, fill="shop", expected_returncode=0)
        self.assertIn("PASS  model_test_alignment", output)
        code["shop/test_module.py"] = "from shop.module import Owner\ndef test_owner():\n    Owner()\n    assert False, 'real failing bound test'\n"
        output = self.run_kit_template(files, "model_test_alignment", code, fill="shop", expected_returncode=1)
        self.assertIn("tested_by_failed", output)
        self.assertIn("real failing bound test", output)
        code["shop/test_module.py"] = "def test_owner():\n    assert True\n"
        output = self.run_kit_template(files, "model_test_alignment", code, fill="shop", expected_returncode=1)
        self.assertIn("tested_by_misses_anchor", output)

    def test_model_test_alignment_template_fails_when_its_plan_names_missing_code(self):
        code = self.alignment_code()
        code[".flowguard/models/shop.py"] = code[".flowguard/models/shop.py"].replace("shop/module.py:Owner", "shop/request.py:parse_request")
        output = self.run_kit_template(model_test_alignment_template_files(), "model_test_alignment", code,
                                       fill="shop", expected_returncode=1)
        self.assertIn("anchor file missing: shop/request.py", output)

    def test_model_mesh_template_executes_and_exposes_negative_fixture(self):
        files = model_mesh_template_files()
        self.assertEqual([".flowguard/models/model_mesh.py"], [f.path for f in files])
        code = {"shop/module.py": "class Owner: pass\nclass Other: pass\n"}
        for file, mid, anchors, parent in (("parent", "shop", '{"A":"shop/module.py:Owner","B":"shop/module.py:Other"}', "system"),
                                           ("shop", "first", '{"A":"shop/module.py:Owner"}', "shop"),
                                           ("shop_other", "second", '{"B":"shop/module.py:Other"}', "shop")):
            code[f".flowguard/models/{file}.py"] = (f'MODEL_ID={mid!r}\nPARENT={parent!r}\nIMPLEMENTED_BY={anchors}\n'
                'DESIGN_ONLY="fixture declarations"\ndef build_explorer(): pass\n')
        components = {"domain": ["shop/module.py"]}
        output = self.run_kit_template(files, "model_mesh", code, components=components, expected_returncode=1)
        self.assertIn("placeholder anchor", output)
        output = self.run_kit_template(files, "model_mesh", code, fill="shop", components=components, expected_returncode=0)
        self.assertIn("PASS  model_mesh", output)
        from dataclasses import replace
        wrong = tuple(replace(f, content=f.content.replace(
            'coverage = tuple(', 'children = (replace(children[0], model_id=children[0].model_id + "x"),) + children[1:]\n    coverage = tuple(')) for f in files)
        output = self.run_kit_template(wrong, "model_mesh", code, fill="shop", components=components, expected_returncode=1)
        self.assertIn("unknown_child_model", output)

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


    def test_every_kit_template_names_its_code_and_its_tests(self):
        from flowguard.map.mapfile import read_model_contract

        for name, factory in template_factories().items():
            model = factory()[0]
            if not model.path.startswith(".flowguard/models/") or model.path.count("/") != 2:
                continue                      # adoption rules and the meta-capability runners
            with self.subTest(template=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "model.py"
                path.write_text(model.content, encoding="utf-8")
                contract = read_model_contract(path)
                anchors = [*contract["IMPLEMENTED_BY"].values(), *(a for v in contract["TESTED_BY"].values() for a in v)]
                self.assertTrue(contract["IMPLEMENTED_BY"] and contract["TESTED_BY"])
                self.assertTrue(all(anchor.startswith("REPLACE_ME/") for anchor in anchors), anchors)

    def test_no_template_writes_a_runner(self):
        for name, factory in template_factories().items():
            paths = [file.path for file in factory()]
            self.assertFalse(any(path.endswith("/run_checks.py") for path in paths), name)
            if name == "adoption":
                self.assertEqual(["docs/flowguard_agents_rules.md"], paths)
            else:
                models = [p for p in paths if p.startswith(".flowguard/models/") and p.count("/") == 2]
                self.assertEqual(1, len(models), name)
                self.assertEqual([".flowguard/behavior/inventory/ledger.json"] if name == "behavior-commitment" else [],
                                 [p for p in paths if p not in models], name)
        self.assertNotIn("model-test-alignment-full", template_factories())
        self.assertEqual(9, len(template_factories()))

    def test_every_template_fails_cleanly_before_it_is_filled(self):
        from flowguard.map.mapfile import read_model_contract
        for name, factory in template_factories().items():
            if name == "adoption":
                continue
            with self.subTest(template=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "model.py"
                path.write_text(factory()[0].content)
                model_id = read_model_contract(path)["MODEL_ID"]
                output = self.run_kit_template(factory(), model_id, {"shop/module.py": "class Owner: pass\n"}, expected_returncode=1)
                self.assertIn("placeholder anchor", output)
                self.assertNotIn("Traceback", output)

    def test_topology_hazard_template_executes(self):
        files = topology_hazard_template_files()
        self.assertEqual([".flowguard/models/topology_hazard.py"], [f.path for f in files])
        output = self.run_kit_template(files, "topology_hazard", {"shop/module.py": "class Owner: pass\n"}, expected_returncode=1)
        self.assertIn("placeholder anchor", output)

    def test_topology_hazard_template_good_review_exits_zero(self):
        output = self.run_kit_template(topology_hazard_template_files(), "topology_hazard",
                                      {"shop/module.py": "class Owner: pass\n"}, fill="shop", expected_returncode=0)
        self.assertIn("PASS  topology_hazard", output)

    def test_field_lifecycle_template_fails_until_bound_to_real_code(self):
        files = field_lifecycle_template_files()
        code = {"shop/orders.py": "class Order:\n    mode = 'fast'\n"}
        self.assertIn("placeholder anchor", self.run_kit_template(files, "field_lifecycle", code, expected_returncode=1))
        self.assertIn("PASS  field_lifecycle", self.run_kit_template(files, "field_lifecycle", code, fill="shop",
                                                                     expected_returncode=0))
        stale = {"shop/orders.py": code["shop/orders.py"] + "    old_mode = None\n"}
        self.assertIn("field:old_mode: deleted field has no reference left",
                      self.run_kit_template(files, "field_lifecycle", stale, fill="shop", expected_returncode=1))

    def test_code_structure_template_runs_as_a_plan_before_the_split(self):
        from dataclasses import replace
        files = code_structure_template_files()
        current = {"shop/orders.py": "def place_order(order):\n    return price_order(order)\n\ndef price_order(order):\n    return order['amount']\n"}
        unsplit = tuple(replace(f, content=f.content.replace("REPLACE_ME/pricing.py:price_order", "REPLACE_ME/orders.py:price_order")) for f in files)
        planned = tuple(replace(f, content=f.content + '\nDESIGN_ONLY = "split pricing into its own module"\n') if f is unsplit[0] else f for f in unsplit)
        components = {"orders": ["shop/orders.py"], "pricing": ["shop/pricing.py"]}
        output = self.run_kit_template(planned, "code_structure", current, fill="shop", components=components, expected_returncode=0)
        self.assertIn("PASS  code_structure", output)
        self.assertIn("planned fact(s) still to make true", output)
        output = self.run_kit_template(unsplit, "code_structure", current, fill="shop", components=components, expected_returncode=1)
        self.assertIn("does not exist", output)
        forced = tuple(replace(f, content=f.content.replace('planned="DESIGN_ONLY" in globals()', 'planned=True')) for f in unsplit)
        output = self.run_kit_template(forced, "code_structure", current, fill="shop", components=components, expected_returncode=1)
        self.assertIn("planned facts without DESIGN_ONLY:", output)
        completed = {"shop/orders.py": "from shop.pricing import price_order\ndef place_order(order):\n    return price_order(order)\n",
                     "shop/pricing.py": "def price_order(order):\n    return order['amount']\n"}
        output = self.run_kit_template(files, "code_structure", completed, fill="shop", components=components, expected_returncode=0)
        self.assertNotIn("planned fact(s)", output)


    def test_field_lifecycle_template_can_plan_a_replacement_not_yet_written(self):
        from dataclasses import replace
        files = field_lifecycle_template_files()
        planned = tuple(replace(f, content=f.content + '\nDESIGN_ONLY = "replace old_mode with mode"\n') if f is files[0] else f for f in files)
        code = {"shop/orders.py": "class Order:\n    old_mode = 'fast'\n"}
        output = self.run_kit_template(planned, "field_lifecycle", code, fill="shop", expected_returncode=0)
        self.assertIn("PASS  field_lifecycle", output)
        self.assertIn("planned fact(s) still to make true", output)
        output = self.run_kit_template(files, "field_lifecycle", code, fill="shop", expected_returncode=1)
        self.assertIn("replacement field:mode exists", output)

    def test_template_cli_prints_and_writes_new_templates(self):
        factories = {
            factory.__name__.removesuffix("_template_files"): factory
            for factory in PUBLIC_TEMPLATE_FACTORIES
        }
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
        for name in listed:
            code, stdout, stderr = self.run_cli(["template", name])
            self.assertEqual(0, code, name + stderr)
            self.assertIn("===== ", stdout, name)
        with tempfile.TemporaryDirectory() as directory:
            code, stdout, _stderr = self.run_cli(["template", "model-mesh", "--write", directory])
            self.assertEqual(0, code)
            self.assertEqual([".flowguard/models/model_mesh.py"],
                             sorted(p.relative_to(directory).as_posix() for p in Path(directory).rglob("*") if p.is_file()))
            code, _stdout, stderr = self.run_cli(["template", "model-mesh", "--write", directory])
            self.assertEqual(1, code)
            self.assertIn("--force", stderr)
        code, _stdout, _stderr = self.run_cli(["template", "no-such-template"])
        self.assertEqual(2, code)


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
