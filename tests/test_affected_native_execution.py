from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from flowguard.validation_ownership import ValidationOwnerContract, build_affected_impact_plan


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_flowguard_skill_suite.py"
SPEC = importlib.util.spec_from_file_location("flowguard_skill_suite_affected_native", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
suite = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = suite
SPEC.loader.exec_module(suite)


def _root(tmp_path: Path, *, with_runner: bool = True) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("value = 1\n", encoding="utf-8")
    if with_runner:
        runner = tmp_path / ".flowguard" / "verification" / "owners" / "owner_a" / "run_checks.py"
        runner.parent.mkdir(parents=True)
        runner.write_text(
            "from pathlib import Path\n"
            "import hashlib, json, os\n"
            "out = Path(os.environ['FLOWGUARD_OUTPUT_DIR'])\n"
            "(out / 'result.json').write_text(json.dumps({'status':'pass','ok':True}), encoding='utf-8')\n"
            "fp = lambda value: 'sha256:' + hashlib.sha256(value.encode('utf-8')).hexdigest()\n"
            "dims = ('input','state','output','effect','order','completion')\n"
            "raw = out / 'raw.json'\n"
            "raw.write_text(json.dumps({'owner':'owner_a','case':'owner_a:case:good'}, sort_keys=True), encoding='utf-8')\n"
            "row = {'schema_version':'flowguard.native_model_case_result.v1','owner_id':'owner_a','source_case_id':'case:good','outcome':'pass','observed_status':'pass','observed_finding_codes':[],'executed_dimensions':list(dims),'oracle_results':[{'dimension':item,'oracle_member_id':'oracle:' + item,'status':'pass','ok':True} for item in dims],'result_artifact_fingerprint':'sha256:' + hashlib.sha256(raw.read_bytes()).hexdigest(),'input_fingerprint':fp('input'),'model_fingerprint':fp('model'),'code_fingerprint':fp('code'),'test_fingerprint':fp('test'),'oracle_fingerprint':fp('oracle'),'toolchain_fingerprint':fp('toolchain'),'environment_fingerprint':fp('environment'),'raw_artifact_path':'raw.json','child_case_ids':[]}\n"
            "(out / 'native-case-results.json').write_text(json.dumps({'schema_version':'flowguard.native_model_case_result.v1','results':[row]}, sort_keys=True), encoding='utf-8')\n"
            "print('native owner ran')\n",
            encoding="utf-8",
        )
    return tmp_path


def _plan(root: Path):
    contract = ValidationOwnerContract(
        owner_id="owner_a",
        command=("python", "-c", "pass"),
        input_patterns=("src/a.py",),
        obligation_ids=("model:a",),
    )
    return build_affected_impact_plan(
        root,
        (contract,),
        changed_paths=("src/a.py",),
        component_bindings={
            "component:a": {
                "paths": ["src/a.py"],
                "owner_id": "owner_a",
            }
        },
    )


def test_affected_execute_runs_native_owner_and_never_light_suite(tmp_path, monkeypatch):
    root = _root(tmp_path)
    plan = _plan(root)
    assert plan.ok
    monkeypatch.setattr(suite, "_canonical_flowguard_member_ids", lambda: ("owner_a",))

    def fail_light(*_args, **_kwargs):
        raise AssertionError("affected execution must not call run_light_suite")

    monkeypatch.setattr(suite, "run_light_suite", fail_light)
    payload = suite.run_affected_suite(root, impact_plan=plan, members=("owner_a",))

    assert payload["ok"]
    assert payload["status"] == "pass"
    assert payload["native_execution"]["executed_owner_ids"] == ["owner_a"]
    row = payload["members"][0]
    assert row["execution_disposition"] == "execute"
    assert row["native_ok"] is True
    work = Path(row["native_work_dir"])
    assert work.is_dir()
    assert json.loads((work / "result.json").read_text(encoding="utf-8"))["status"] == "pass"


def test_missing_native_owner_blocks_without_light_fallback(tmp_path, monkeypatch):
    root = _root(tmp_path, with_runner=False)
    plan = _plan(root)
    assert plan.ok
    monkeypatch.setattr(suite, "_canonical_flowguard_member_ids", lambda: ("owner_a",))
    monkeypatch.setattr(
        suite,
        "run_light_suite",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("affected execution must not fall back to light")
        ),
    )

    payload = suite.run_affected_suite(root, impact_plan=plan, members=("owner_a",))

    assert not payload["ok"]
    assert payload["status"] == "blocked"
    assert any("native owner runner is missing" in item for item in payload["blockers"])
    assert payload["members"][0]["execution_disposition"] == "blocked"
    assert payload["members"][0]["native_ok"] is False
