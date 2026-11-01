"""A plain code change needs no map upkeep, no target and no generated commit text."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from test_requests import _call, _git, _plan_target, _project

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/flowguard"


def _seed(root: Path, capsys) -> Path:
    (root / "shop").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "shop/__init__.py").write_text("")
    (root / "shop/prices.py").write_text('def price(item):\n    return {"a": 1, "b": 2}.get(item, 0)\n')
    (root / "shop/cart.py").write_text("from shop.prices import price\n\n\ndef total(items):\n    return sum(price(i) for i in items)\n")
    (root / "tests/test_cart.py").write_text('from shop.cart import total\n\n\ndef test_total():\n    assert total(["a", "b"]) == 3\n')
    component = dict(layer="", state=[], side_effects=[], entrypoints=[], models=[], status="draft", fingerprint="")
    data = {"schema": "flowguard.map.v1", "project": "seed", "fingerprint_format": 2, "model_digests": {},
            "layers": [], "ignore": [], "test_command": "python -m pytest -q", "flows": [], "accepted_debts": [],
            "components": [
                dict(component, id="cart", summary="Cart totals", responsibilities=["sum item prices"],
                     files=["shop/cart.py", "shop/__init__.py"], depends_on=["prices"], tests=["tests/test_cart.py"]),
                dict(component, id="prices", summary="Price table", responsibilities=["look up item price"],
                     files=["shop/prices.py"], depends_on=[], tests=[]),
            ]}
    (root / ".flowguard").mkdir()
    (root / ".flowguard/map.json").write_text(json.dumps(data, indent=2) + "\n")
    assert _call(root, capsys, "map", "confirm", "all")[0] == 0
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    assert _call(root, capsys, "map", "check", "--strict")[0] == 0
    return root


MUTATIONS = {
    "new_file": lambda root: (root / "shop/discount.py").write_text("def discount(x):\n    return x\n"),
    "edit_owned_file": lambda root: (root / "shop/cart.py").write_text(
        (root / "shop/cart.py").read_text() + "\n\ndef cheapest():\n    return min(price(i) for i in 'ab')\n"),
    "drop_import": lambda root: (root / "shop/cart.py").write_text("def total(items):\n    return len(items)\n"),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_plain_code_change_passes_map_check_strict_and_release(tmp_path, capsys, name):
    root = _seed(tmp_path / "seed", capsys)
    MUTATIONS[name](root)
    for arguments in (("map", "check"), ("map", "check", "--strict"), ("release",)):
        code, output, errors = _call(root, capsys, *arguments)
        assert code == 0, (arguments, output, errors)
    if name == "new_file":
        _, output, _ = _call(root, capsys, "map", "check")
        assert "INFO  file_unmapped" in output and "import checks between components do not see this file" in output


def test_change_run_still_runs_tests_with_a_new_file(tmp_path, capsys):
    root = _seed(tmp_path / "seed", capsys)
    MUTATIONS["new_file"](root)
    cart = root / "shop/cart.py"
    cart.write_text(cart.read_text().replace("price(i) for i in items", "price(item) for item in items"))
    _, output, _ = _call(root, capsys, "change", "--run")
    assert "RAN: skipped" not in output and "RAN PASS" in output, output
    assert "next[confirm]" not in output


def test_real_architecture_errors_still_gate(tmp_path, capsys):
    """Control: an import cycle made by code stays an error."""
    root = _seed(tmp_path / "seed", capsys)
    (root / "shop/prices.py").write_text(
        'from shop.cart import total\n\n\ndef price(item):\n    return {"a": 1, "b": 2}.get(item, 0)\n')
    code, output, _ = _call(root, capsys, "map", "check", "--strict")
    assert code == 1 and "dependency_cycle" in output


def test_req_add_does_not_send_the_ai_into_a_target(tmp_path, capsys):
    root = _seed(tmp_path / "seed", capsys)
    (tmp_path / "R1.md").write_text("Carts get a discount over 3 items.\n")
    code, output, _ = _call(root, capsys, "req", "add", str(tmp_path / "R1.md"), "--id", "R1")
    assert code == 0
    assert "target" not in output, output
    assert output.splitlines()[-1].startswith("next[status]: python -m flowguard status --root "), output


def test_plan_comments_written_by_the_ai_are_kept_in_the_record(tmp_path, capsys):
    from flowguard.map.records import change_records
    _plan_target(tmp_path)
    plan = tmp_path / ".flowguard/target/PLAN.txt"
    lines = ["# Keep the old ceiling; the owner asked only for the limit.",
             'changes: renew_limit.renew_within_limit by RQuote "Renewals keep the limit 3."']
    model = tmp_path / ".flowguard/target/models/one.py"
    model.write_text(model.read_text().replace("if state in (0, availability_ceiling)",
                                               "if state in (0, availability_ceiling) and state >= 0"))
    plan.write_text(plan.read_text() + "\n".join(lines) + "\n")
    code, output, errors = _call(tmp_path, capsys, "target", "promote", "--json")
    assert code == 0, (output, errors)
    _, record = change_records(tmp_path)[0]
    assert [item["line"] for item in record["plan"]] == lines


def test_promote_writes_no_generated_commit_message(tmp_path, capsys):
    _plan_target(tmp_path)
    model = tmp_path / ".flowguard/target/models/one.py"
    model.write_text(model.read_text().replace("if state in (0, availability_ceiling)",
                                               "if state in (0, availability_ceiling) and state >= 0"))
    (tmp_path / ".flowguard/target/PLAN.txt").write_text(
        'changes: renew_limit.renew_within_limit by RQuote "Renewals keep the limit 3."\n')
    code, output, errors = _call(tmp_path, capsys, "target", "promote")
    assert code == 0, (output, errors)
    assert not list((tmp_path / ".flowguard/changes").glob("*.msg"))
    assert "commit -F" not in output and "next[confirm]" not in output


def test_a_deleted_legacy_commit_message_is_still_reported(tmp_path, capsys):
    from flowguard.map.records import CHANGE_DIR, change_records, record_findings, write_once
    _plan_target(tmp_path)
    model = tmp_path / ".flowguard/target/models/one.py"
    model.write_text(model.read_text().replace("if state in (0, availability_ceiling)",
                                               "if state in (0, availability_ceiling) and state >= 0"))
    (tmp_path / ".flowguard/target/PLAN.txt").write_text(
        'changes: renew_limit.renew_within_limit by RQuote "Renewals keep the limit 3."\n')
    assert _call(tmp_path, capsys, "target", "promote")[0] == 0
    identifier, _ = change_records(tmp_path)[0]
    legacy = CHANGE_DIR / (identifier + ".msg")
    write_once(tmp_path, legacy, b"a message written by an older FlowGuard\n")
    assert record_findings(tmp_path) == [] and change_records(tmp_path)
    (tmp_path / legacy).unlink()
    assert [item.code for item in record_findings(tmp_path)] == ["record_edited"]


def test_skill_and_agents_template_teach_the_plain_flow():
    from flowguard.templates import adoption_template_files
    rules = next(f.content for f in adoption_template_files() if f.path == "AGENTS.md")
    texts = {"SKILL.md": (SKILL / "SKILL.md").read_text(), "openai.yaml": (SKILL / "agents/openai.yaml").read_text(),
             "AGENTS template": rules, "AGENTS.md": (ROOT / "AGENTS.md").read_text()}
    for name, text in texts.items():
        for ceremony in ("target start", "target add", "target check", "target promote", "map confirm",
                         "owner block", "commit -F", "PLAN.txt", "change --run"):
            assert ceremony not in text, (name, ceremony)
    for name in ("SKILL.md", "AGENTS template", "openai.yaml"):
        for taught in ("python -m flowguard status", "python -m flowguard req add", "python -m flowguard where",
                       "your own words", "Request: R"):
            assert taught in texts[name], (name, taught)
    for path in sorted((SKILL / "references").glob("*.md")):
        text = path.read_text()
        assert not re.search(r"target first|Write no current model file in place", text), path.name


def test_editing_a_legacy_model_in_place_is_not_a_release_error(tmp_path, capsys):
    from flowguard.map.common import content_digest
    root = _project(tmp_path, capsys)
    data = json.loads((root / ".flowguard/map.json").read_text())
    data["model_digests"] = {path.relative_to(root).as_posix(): content_digest(path)
                             for path in sorted((root / ".flowguard/models").glob("*.py"))
                             if not path.name.startswith("_")}
    (root / ".flowguard/map.json").write_text(json.dumps(data, indent=2) + "\n")
    assert "model_edited_outside_target" not in _call(root, capsys, "map", "check", "--strict")[1]
    model = next(path for path in sorted((root / ".flowguard/models").glob("*.py")) if not path.name.startswith("_"))
    model.write_text(model.read_text() + "\n# the AI fixed this legacy model in place\n")
    code, output, _ = _call(root, capsys, "map", "check", "--strict")
    assert "INFO  model_edited_outside_target" in output and "ERROR model_edited_outside_target" not in output, output
