import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.__main__ import main as flowguard_cli_main, template_factories
from flowguard.templates import (
    behaviour_template_files,
    validator_template_files,
    ui_journey_template_files,
    write_template_files,
)


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_TEMPLATE_FACTORIES = (
    behaviour_template_files,
    ui_journey_template_files,
    validator_template_files,
)

TEMPLATE_CLI_COMMANDS = {
    "behaviour-template": "behaviour",
    "ui-journey-template": "ui_journey",
    "validator-template": "validator",
}


def _template_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


class PublicTemplateTests(unittest.TestCase):
    def run_kit_template(self, files, model_id, code, *, fill="", expected_returncode=None, components=None, known_bad=()):
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
            if known_bad:
                proof = subprocess.run([sys.executable, "-m", "flowguard.map.proof", str(root), str(root / files[0].path)],
                                       cwd=root, env=_template_env(), text=True, capture_output=True, check=True)
                payload = json.loads(proof.stdout)
                self.assertEqual(payload["status"], "pass", payload)
                self.assertEqual(payload["known_bad"], sorted(known_bad))
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

        self.assertIn("ui_journey", route_modules)
        self.assertNotIn("model_similarity_consolidation", route_modules)
        self.assertNotIn("risk_evidence_ledger", route_modules)
        self.assertIn("UIInteractionModel", (template_text_root / "ui_journey.py").read_text(encoding="utf-8"))

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







    def test_validator_template_runs_the_bad_cases_against_the_real_function(self):
        files = validator_template_files()
        strict = {"shop/orders.py": "def place(order_id, amount):\n"
                  "    if not isinstance(order_id, str) or not order_id or len(order_id) > 80 or not isinstance(amount, int):\n"
                  "        raise ValueError('bad input')\n    return 'placed'\n"}
        lax = {"shop/orders.py": "def place(order_id, amount):\n    return 'placed'\n"}
        self.assertIn("placeholder anchor", self.run_kit_template(files, "validator", strict,
                                                                  expected_returncode=1))
        self.assertIn("PASS  validator", self.run_kit_template(files, "validator", strict,
                                                                         fill="shop", expected_returncode=0))
        output = self.run_kit_template(files, "validator", lax, fill="shop", expected_returncode=1)
        self.assertIn("executed against code: 37 of 37 feature combinations; declared only: 0; errors: 0; "
                      "counterexamples: 36", output)
        self.assertIn("- each_defect_rejected: contract:order_id:missing_required_field: expected rejected, "
                      "observed accepted", output)



    def test_ui_journey_template_compares_controls_with_the_ui_source(self):
        files = ui_journey_template_files()
        ui = {"web/index.html": '<button id="show">Show</button><button id="hide">Hide</button>\n',
              "web/app.js": "function showDetails() {}\nfunction hideDetails() {}\n"}
        self.assertIn("placeholder anchor", self.run_kit_template(files, "ui_journey", ui, expected_returncode=1))
        filled = self.run_kit_template(files, "ui_journey", ui, fill="web", expected_returncode=0,
                                       known_bad=("show_opens_an_unknown_state", "details_dialog_cannot_close", "hide_has_no_transition"))
        self.assertIn("PASS  ui_journey", filled)
        for variant in ("show_opens_an_unknown_state", "details_dialog_cannot_close", "hide_has_no_transition"):
            self.assertNotIn(variant, filled)
        self.assertNotIn("violated by no known-bad variant", filled)
        missing = dict(ui, **{"web/index.html": '<button id="show">Show</button>\n'})
        self.assertIn("control hide is in the UI source",
                      self.run_kit_template(files, "ui_journey", missing, fill="web", expected_returncode=1))
        import ast
        from dataclasses import replace

        # Promote the template's genuine bad close variant to the design;
        # the real proof runner must reject it rather than merely print its name.
        model = files[0]
        build = next(node for node in ast.parse(model.content).body
                     if isinstance(node, ast.FunctionDef) and node.name == "build_explorer")
        lines = model.content.splitlines(keepends=True)
        lines[build.lineno - 1:build.end_lineno] = [
            "def build_explorer():\n    return broken_variants()['details_dialog_cannot_close']\n"]
        broken = (replace(model, content="".join(lines)), *files[1:])
        output = self.run_kit_template(broken, "ui_journey", ui, fill="web", expected_returncode=1)
        self.assertIn("FAIL  ui_journey", output)
        self.assertIn("dialog_cannot_close", output)



    def test_every_kit_template_names_its_code_and_its_tests(self):
        from flowguard.map.mapfile import read_model_contract

        for name, factory in template_factories().items():
            model = factory()[0]
            if not model.path.startswith(".flowguard/models/") or model.path.count("/") != 2:
                continue                      # adoption rules have no model
            with self.subTest(template=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "model.py"
                path.write_text(model.content, encoding="utf-8")
                contract = read_model_contract(path)
                anchors = [*contract["IMPLEMENTED_BY"].values(), *(a for v in contract.get("TESTED_BY", {}).values() for a in v)]
                if name == "behaviour":
                    self.assertEqual({"PlaceOrder": "shop/orders.py:OrderService.place"}, contract["IMPLEMENTED_BY"])
                    self.assertFalse(contract.get("TESTED_BY", {}))  # optional example is not a declared test binding
                    self.assertNotIn("REPLACE_ME", model.content)
                else:
                    self.assertTrue(contract["IMPLEMENTED_BY"] and contract["TESTED_BY"])
                    self.assertTrue(all(anchor.startswith("REPLACE_ME/") for anchor in anchors), anchors)

    def test_no_template_writes_a_runner(self):
        for name, factory in template_factories().items():
            paths = [file.path for file in factory()]
            self.assertFalse(any(path.endswith("/run_checks.py") for path in paths), name)
            if name == "adoption":
                self.assertEqual(["docs/flowguard_agents_rules.md", "CLAUDE.md"], paths)
            else:
                models = [p for p in paths if p.startswith(".flowguard/models/") and p.count("/") == 2]
                self.assertEqual(1, len(models), name)
                expected_tests = ["REPLACE_ME/tests/test_cases.py"] if name == "cases" else []
                self.assertEqual(expected_tests, [p for p in paths if p not in models], name)
        self.assertEqual(
            ["adoption", "behaviour", "cases", "ui-journey", "validator"], sorted(template_factories())
        )

    def test_every_template_fails_cleanly_before_it_is_filled(self):
        from flowguard.map.mapfile import read_model_contract
        for name, factory in template_factories().items():
            if name == "adoption":
                continue
            with self.subTest(template=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "model.py"
                path.write_text(factory()[0].content)
                model_id = read_model_contract(path)["MODEL_ID"]
                if name == "behaviour":
                    output = self.run_kit_template(factory(), model_id, {"shop/module.py": "class Owner: pass\n"},
                                                   components={"orders": ["shop/*.py"]}, expected_returncode=1)
                    self.assertIn("anchor file missing: shop/orders.py", output)
                else:
                    output = self.run_kit_template(factory(), model_id, {"shop/module.py": "class Owner: pass\n"}, expected_returncode=1)
                    self.assertIn("placeholder anchor", output)
                self.assertNotIn("Traceback", output)







    def test_template_cli_prints_and_writes_new_templates(self):
        factories = {
            factory.__name__.removesuffix("_template_files"): factory
            for factory in PUBLIC_TEMPLATE_FACTORIES
        }
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
        self.assertEqual(["adoption", "behaviour", "cases", "ui-journey", "validator"], listed)
        self.assertNotIn("project", listed)
        for name in listed:
            code, stdout, stderr = self.run_cli(["template", name])
            self.assertEqual(0, code, name + stderr)
            self.assertIn("===== ", stdout, name)
        with tempfile.TemporaryDirectory() as directory:
            code, stdout, _stderr = self.run_cli(["template", "validator", "--write", directory])
            self.assertEqual(0, code)
            self.assertEqual(
                [".flowguard/models/validator.py"],
                sorted(
                    p.relative_to(directory).as_posix()
                    for p in Path(directory).rglob("*")
                    if p.is_file()
                ),
            )
            code, _stdout, stderr = self.run_cli(["template", "validator", "--write", directory])
            self.assertEqual(1, code)
            self.assertIn("--force", stderr)
        code, _stdout, _stderr = self.run_cli(["template", "no-such-template"])
        self.assertEqual(2, code)
        code, _stdout, _stderr = self.run_cli(["template", "ui-flow-structure"])
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


    def test_template_writes_into_the_target_when_one_exists(self):
        from flowguard.map.targetfile import load_target

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".flowguard").mkdir()
            (root / ".flowguard/map.json").write_text(json.dumps({
                "schema": "flowguard.map.v1", "project": "template-target", "components": []}), encoding="utf-8")
            code, stdout, stderr = self.run_cli(["target", "start", "add an order behaviour model", "--root", directory])
            self.assertEqual(0, code, stdout + stderr)
            self.assertIsNotNone(load_target(root))
            code, stdout, stderr = self.run_cli(["template", "behaviour", "--write", directory])
            self.assertEqual(0, code, stdout + stderr)
            target = root / ".flowguard/target/models/order_placement.py"
            self.assertEqual(behaviour_template_files()[0].content, target.read_text(encoding="utf-8"))
            self.assertFalse((root / ".flowguard/models/order_placement.py").exists())
            self.assertIn("next[check]: python -m flowguard target check", stdout)
            self.assertNotIn("python -m flowguard map models order_placement", stdout)

            # Target relocation happens before the existing no-overwrite/force check.
            target.write_text("# locally edited target\n", encoding="utf-8")
            code, _stdout, stderr = self.run_cli(["template", "behaviour", "--write", directory])
            self.assertEqual(1, code)
            self.assertIn("--force", stderr)
            self.assertEqual("# locally edited target\n", target.read_text(encoding="utf-8"))
            code, stdout, stderr = self.run_cli(["template", "behaviour", "--write", directory, "--force"])
            self.assertEqual(0, code, stdout + stderr)
            self.assertEqual(behaviour_template_files()[0].content, target.read_text(encoding="utf-8"))
            self.assertFalse((root / ".flowguard/models/order_placement.py").exists())

            code, stdout, stderr = self.run_cli(["template", "adoption", "--write", directory])
            self.assertEqual(0, code, stdout + stderr)
            self.assertTrue((root / "docs/flowguard_agents_rules.md").is_file())
            self.assertFalse((root / ".flowguard/target/docs").exists())

if __name__ == "__main__":
    unittest.main()


def test_cases_template_passes_and_every_known_bad_fails(tmp_path):
    from flowguard.templates import cases_template_files

    package = tmp_path / "app"
    package.mkdir()
    (package / "api.py").write_text(
        "def convert(value):\n    result = value * 2\n    return result\n"
    )
    files = cases_template_files()
    for item in files:
        path = tmp_path / item.path.replace("REPLACE_ME", "app")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item.content.replace("REPLACE_ME", "app"))
    (tmp_path / ".flowguard/map.json").write_text(
        json.dumps(
            dict(
                schema="flowguard.map.v1",
                components=[
                    dict(
                        id="app",
                        files=["app/*.py"],
                        tests=["app/tests/*.py"],
                        models=[],
                        summary="Convert an input",
                        responsibilities=[],
                        status="draft",
                    )
                ],
            )
        )
    )
    env = _template_env()
    command = [
        sys.executable,
        "-m",
        "flowguard",
        "map",
        "models",
        "--root",
        str(tmp_path),
        "--tests",
    ]
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    model_path = tmp_path / files[0].path
    proof = subprocess.run(
        [sys.executable, "-m", "flowguard.map.proof", str(tmp_path), str(model_path)],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(proof.stdout)
    assert payload["status"] == "pass", payload
    assert payload["known_bad"] == ["wrong_output"], payload
    assert payload["rules"] == ["case_output_matches"], payload
