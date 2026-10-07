"""Current author request orchestration with a fake native CLI boundary."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import check_flowguard_author_skill_assurance as author_command
from scripts import check_flowguard_skill_suite as suite


class FakeAuthorCli:
    def __init__(self):
        self.calls = []
        self.current = None
        self.fail_operation = None
        self.invalid_id = False
        self.read_mismatch = False

    def __call__(self, command, cwd):
        operation = command[2]
        request_path = Path(cwd) / command[command.index("--request") + 1]
        request = json.loads(request_path.read_text(encoding="utf-8"))
        self.calls.append(request)
        required = {"operation", "target_id", "scope", "contract_path", "author_state_root"}
        if operation != "read":
            required |= {"expected_current", "facts"}
            assert request["facts"] == {"operation": operation}
            assert request["expected_current"] == self.current
        assert set(request) == required
        assert request["operation"] == operation
        assert request["target_id"] == "flowguard"
        assert request["contract_path"] == ".skillguard/contract-source.json"
        assert request["scope"] in (["route:change"], ["route:release"])
        assert request_path.parent == Path(cwd) / ".skillguard/runtime-requests/full-author-assurance"
        if operation == self.fail_operation:
            payload = {"status": "blocked", "decision": "block"}
            code = 1
        else:
            if operation != "read":
                self.current = "sha256:" + hashlib.sha256(f"{operation}:{len(self.calls)}".encode()).hexdigest()
            current = self.current
            if self.invalid_id:
                current = "not-an-accepted-id"
            if operation == "read" and self.read_mismatch:
                current = "sha256:" + "f" * 64
            payload = {"status": "pass", "decision": "pass", "accepted_id": current,
                       "producer_count": 0 if operation == "read" else 1}
            code = 0
        return {"command": command, "exit_code": code, "stdout": json.dumps(payload),
                "stderr": "", "payload": payload}


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    root = tmp_path / "source"
    member = root / ".agents/skills/flowguard"
    (member / ".skillguard").mkdir(parents=True)
    declared_paths = ("SKILL.md", "agents/openai.yaml", "references/route_index.md",
                      "references/route_execution_common.md", "references/domains/model-mesh/protocol.md")
    for relative in declared_paths:
        path = member / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"declared author source: {relative}\n", encoding="utf-8")
    (member / ".skillguard/contract-source.json").write_text(json.dumps({
        "schema_version": "skillguard.skill_contract.v3", "skill_id": "flowguard",
        "maintenance_unit_id": "unit:flowguard-suite",
        "inputs": [{"id": f"input:{index}", "path": relative, "required": True,
                    "role": "instructions" if index <= 2 else "runtime_source"}
                   for index, relative in enumerate(declared_paths, 1)],
    }), encoding="utf-8")
    state = tmp_path / "author-state"
    state.mkdir()
    cli = tmp_path / "tools/skillguard.py"
    cli.parent.mkdir()
    cli.write_text("# fake author CLI boundary\n", encoding="utf-8")
    inventory = SimpleNamespace(ok=True, declared_member_ids=("flowguard",),
                                inventory_hash="inventory", semantic_hash="source-one", to_dict=lambda: {})
    compiler = SimpleNamespace(ok=True, compiler_version="current", route_registry_hash="routes", to_dict=lambda: {})
    fake = FakeAuthorCli()
    monkeypatch.setattr(suite, "validate_skill_suite", lambda root: inventory)
    monkeypatch.setattr(suite, "compile_skill_suite", lambda root, write: compiler)
    monkeypatch.setattr(suite, "_run_json_command", fake)
    def run(**kwargs):
        return suite.run_author_skill_assurance(root, author_state_root=kwargs.pop("state", state), skillguard=str(cli), **kwargs)
    return SimpleNamespace(root=root, member=member, state=state, cli=cli, fake=fake,
                           inventory=inventory, compiler=compiler, run=run)


def test_fresh_state_uses_current_schema_and_accepted_chain(fixture):
    result = fixture.run()
    assert result["ok"] is True
    assert [item["operation"] for item in fixture.fake.calls] == ["change", "release", "read"]
    assert fixture.fake.calls[0]["expected_current"] is None
    changed_id = result["members"][0]["results"]["change"]["payload"]["accepted_id"]
    assert fixture.fake.calls[1]["expected_current"] == changed_id
    assert fixture.fake.calls[2]["scope"] == ["route:release"]
    assert "facts" not in fixture.fake.calls[2]
    assert result["native_producer_count"] == 0
    assert result["author_subprocess_count"] == 3
    checkpoint = Path(result["members"][0]["checkpoint_path"])
    assert checkpoint.is_file()
    assert json.loads(checkpoint.read_text())["phase"] == "complete"
    retained = list(checkpoint.parent.glob("invocations/*/*.json"))
    assert len(retained) == 3
    assert all("request_fingerprint" in json.loads(path.read_text()) for path in retained)


def test_exact_terminal_reuses_only_read(fixture):
    assert fixture.run()["ok"]
    fixture.fake.calls.clear()
    result = fixture.run()
    assert result["ok"] and result["members"][0]["reused_current"]
    assert [item["operation"] for item in fixture.fake.calls] == ["read"]
    assert result["author_subprocess_count"] == 1


@pytest.mark.parametrize(("operation", "expected_calls"), [("change", ["change"]), ("release", ["change", "release"])])
def test_failure_stops_dependent_operations(fixture, operation, expected_calls):
    fixture.fake.fail_operation = operation
    result = fixture.run()
    assert not result["ok"]
    assert [item["operation"] for item in fixture.fake.calls] == expected_calls
    assert fixture.state.is_dir()


def test_release_failure_resumes_from_real_change_receipt(fixture):
    fixture.fake.fail_operation = "release"
    assert not fixture.run()["ok"]
    accepted = fixture.fake.current
    fixture.fake.fail_operation = None
    fixture.fake.calls.clear()
    result = fixture.run()
    assert result["ok"]
    assert [item["operation"] for item in fixture.fake.calls] == ["read", "release", "read"]
    assert fixture.fake.calls[0]["scope"] == ["route:change"]
    assert fixture.fake.calls[1]["expected_current"] == accepted


def test_changed_inputs_use_observed_cas_token_instead_of_null(fixture):
    assert fixture.run()["ok"]
    accepted = fixture.fake.current
    (fixture.member / "SKILL.md").write_text("changed source bytes\n", encoding="utf-8")
    fixture.fake.calls.clear()
    assert fixture.run()["ok"]
    assert [item["operation"] for item in fixture.fake.calls] == ["read", "change", "release", "read"]
    assert fixture.fake.calls[1]["expected_current"] == accepted


def test_changed_toolchain_does_not_reuse_old_terminal(fixture):
    assert fixture.run()["ok"]
    fixture.cli.write_text("# changed author engine\n", encoding="utf-8")
    fixture.fake.calls.clear()
    assert fixture.run()["ok"]
    assert [item["operation"] for item in fixture.fake.calls] == ["read", "change", "release", "read"]


def test_mismatched_current_read_never_restarts_producer(fixture):
    assert fixture.run()["ok"]
    fixture.fake.read_mismatch = True
    fixture.fake.calls.clear()
    assert not fixture.run()["ok"]
    assert [item["operation"] for item in fixture.fake.calls] == ["read"]


def test_invalid_accepted_id_blocks_release(fixture):
    fixture.fake.invalid_id = True
    assert not fixture.run()["ok"]
    assert len(fixture.fake.calls) == 1


@pytest.mark.parametrize("kind", ["missing", "inside", "ancestor", "foreign", "wrong-checkpoint"])
def test_invalid_state_blocks_before_producer(fixture, kind):
    state = fixture.state
    if kind == "missing":
        state = state / "missing"
    elif kind == "inside":
        state = fixture.member
    elif kind == "ancestor":
        state = fixture.root.parent
    elif kind == "foreign":
        (state / "foreign-state.json").write_text("{}", encoding="utf-8")
    else:
        assert fixture.run()["ok"]
        path = state / "flowguard-author-assurance/flowguard/checkpoint.json"
        payload = json.loads(path.read_text())
        payload["binding"]["root"] = "foreign-root"
        path.write_text(json.dumps(payload), encoding="utf-8")
        fixture.fake.calls.clear()
    result = fixture.run(state=state)
    assert not result["ok"]
    assert fixture.fake.calls == []


def test_inventory_failure_does_not_launch_author(fixture):
    fixture.inventory.ok = False
    assert not fixture.run()["ok"]
    assert fixture.fake.calls == []


def test_author_cli_requires_state_and_forwards_it(monkeypatch, tmp_path, capsys):
    seen = []
    monkeypatch.setattr(author_command, "run_author_skill_assurance", lambda root, **kwargs: seen.append((root, kwargs)) or {"ok": True})
    monkeypatch.setattr(author_command, "_print_light", lambda *args, **kwargs: None)
    state = tmp_path / "state"
    assert author_command.main(["--root", str(tmp_path), "--author-state-root", str(state), "--skillguard", "chosen-cli"]) == 0
    assert seen[0][1] == {"skillguard": "chosen-cli", "author_state_root": state.resolve()}
    with pytest.raises(SystemExit):
        author_command.build_parser().parse_args([])


def test_missing_release_state_rejected_before_full(monkeypatch, capsys):
    monkeypatch.setattr(suite, "run_full_validation", lambda *args: pytest.fail("full must not start"))
    assert suite.main(["--scope", "full", "--json"]) == 3
    assert "--author-state-root" in capsys.readouterr().out


@pytest.mark.parametrize("relative", ["SKILL.md", "references/route_index.md"])
def test_real_declared_bytes_invalidate_with_unchanged_inventory_and_contract(fixture, relative):
    first = fixture.run()
    assert first["ok"]
    accepted = fixture.fake.current
    contract = fixture.member / ".skillguard/contract-source.json"
    contract_bytes = contract.read_bytes()
    semantic_hash = fixture.inventory.semantic_hash
    (fixture.member / relative).write_bytes(b"current changed author source\r\n")
    fixture.fake.calls.clear()
    second = fixture.run()
    assert second["ok"] and not second["members"][0]["reused_current"]
    assert first["members"][0]["input_identity"] != second["members"][0]["input_identity"]
    assert contract.read_bytes() == contract_bytes
    assert fixture.inventory.semantic_hash == semantic_hash
    assert [request["operation"] for request in fixture.fake.calls] == ["read", "change", "release", "read"]
    assert fixture.fake.calls[1]["expected_current"] == accepted


def test_only_declared_source_inputs_affect_author_identity(fixture):
    first = fixture.run()
    assert first["ok"]
    for relative in (".skillguard/runtime-requests/full-author-assurance/extra.json",
                     "references/not-a-declared-input.md"):
        (fixture.member / relative).write_text("unrelated output or undeclared source", encoding="utf-8")
    fixture.inventory.semantic_hash = "inventory-description-only"
    fixture.fake.calls.clear()
    second = fixture.run()
    assert second["ok"] and second["members"][0]["reused_current"]
    assert first["members"][0]["input_identity"] == second["members"][0]["input_identity"]
    assert [request["operation"] for request in fixture.fake.calls] == ["read"]


@pytest.mark.parametrize("kind", ["missing", "duplicate-id", "duplicate-path", "escape", "glob", "output", "directory"])
def test_invalid_declared_inputs_block_before_author_call(fixture, kind):
    contract_path = fixture.member / ".skillguard/contract-source.json"
    contract = json.loads(contract_path.read_text())
    if kind == "missing":
        (fixture.member / "SKILL.md").unlink()
    elif kind.startswith("duplicate"):
        item = dict(contract["inputs"][0])
        item["path" if kind == "duplicate-id" else "id"] = "other"
        contract["inputs"].append(item)
    elif kind == "escape":
        contract["inputs"][0]["path"] = "../outside.md"
    elif kind == "glob":
        contract["inputs"][0]["path"] = "references/*.md"
    elif kind == "output":
        contract["inputs"][0]["path"] = ".skillguard/runtime-requests/full-author-assurance/change.json"
    else:
        contract["inputs"][0]["path"] = "references"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    result = fixture.run()
    assert not result["ok"] and fixture.fake.calls == []
    assert "author_" in ";".join(result["blockers"])
    if kind == "missing":
        assert "author_required_input_missing" in ";".join(result["blockers"])


def test_optional_declared_presence_changes_identity(fixture):
    contract_path = fixture.member / ".skillguard/contract-source.json"
    contract = json.loads(contract_path.read_text())
    contract["inputs"].append({"id": "optional", "path": "optional.md", "role": "instructions", "required": False})
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    first = fixture.run()
    assert first["ok"]
    (fixture.member / "optional.md").write_text("now present", encoding="utf-8")
    fixture.fake.calls.clear()
    second = fixture.run()
    assert second["ok"]
    assert first["members"][0]["input_identity"] != second["members"][0]["input_identity"]
    assert [request["operation"] for request in fixture.fake.calls] == ["read", "change", "release", "read"]


@pytest.mark.parametrize("field", ["path", "role", "required", "id"])
def test_source_identity_binds_declared_metadata_even_with_identical_bytes(fixture, field):
    _, before = suite._author_source_identity(fixture.member, "flowguard")
    contract_path = fixture.member / ".skillguard/contract-source.json"
    contract = json.loads(contract_path.read_text())
    if field == "path":
        (fixture.member / "equivalent.md").write_bytes((fixture.member / "SKILL.md").read_bytes())
        contract["inputs"][0][field] = "equivalent.md"
    else:
        contract["inputs"][0][field] = {"role": "runtime_source", "required": False, "id": "renamed-input"}[field]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    assert suite._author_source_identity(fixture.member, "flowguard")[1] != before
    assert fixture.fake.calls == []


def test_declared_symlink_rejected_before_resolve(fixture, monkeypatch):
    # Exercise the rejection on hosts without link-creation privilege too.
    original = Path.is_symlink
    target = fixture.member / "SKILL.md"
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == target or original(path))
    result = fixture.run()
    assert not result["ok"] and fixture.fake.calls == []
    assert "author_input_symlink" in ";".join(result["blockers"])


@pytest.mark.parametrize("plan_only", [False, True])
@pytest.mark.parametrize("kind", ["missing", "inside", "ancestor"])
def test_full_state_preflight_blocks_before_any_child(fixture, monkeypatch, capsys, plan_only, kind):
    state = {"missing": fixture.state / "not-created", "inside": fixture.member,
             "ancestor": fixture.root.parent}[kind]
    starts = []
    monkeypatch.setattr(suite, "run_full_validation", lambda *args: starts.append("full"))
    monkeypatch.setattr(suite, "run_local_functional_validation", lambda *args: starts.append("local"))
    command = ["--root", str(fixture.root), "--scope", "full", "--author-state-root", str(state), "--json"]
    if plan_only:
        command.append("--plan-only")
    assert suite.main(command) == 3
    assert "author_state_root_invalid" in capsys.readouterr().out
    assert starts == [] and fixture.fake.calls == []


@pytest.mark.parametrize("kind", ["missing", "inside", "ancestor"])
def test_direct_full_state_preflight_precedes_specs_or_local_child(fixture, monkeypatch, kind):
    state = {"missing": fixture.state / "not-created", "inside": fixture.member,
             "ancestor": fixture.root.parent}[kind]
    monkeypatch.setattr(suite, "_full_child_specs", lambda *args: pytest.fail("owner plan must not start"))
    monkeypatch.setattr(suite, "run_local_functional_validation", lambda *args: pytest.fail("child must not start"))
    args = suite.build_parser().parse_args(["--root", str(fixture.root), "--scope", "full", "--plan-only",
                                            "--author-state-root", str(state)])
    result = suite.run_full_validation(args)
    assert result.exit_code == 3
    assert "author_state_root_invalid" in result.terminal_json_text()


def _interrupt_after_accepted(fixture, monkeypatch, operation, *, omit_result=False):
    original = suite.write_json_atomic
    failed = False

    def interrupt(path, payload):
        nonlocal failed
        hit = ((Path(path).name == "checkpoint.json" and payload.get("phase") == operation
                and not payload.get("pending_operation")) if not omit_result
               else ("invocations" in Path(path).parts and Path(path).name.endswith(f"-{operation}.json")))
        if hit and not failed:
            failed = True
            raise OSError("injected write failure after native accepted")
        return original(path, payload)

    with monkeypatch.context() as context:
        context.setattr(suite, "write_json_atomic", interrupt)
        result = fixture.run()
    assert failed and not result["ok"]
    checkpoint_path = fixture.state / "flowguard-author-assurance/flowguard/checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    assert checkpoint["pending_operation"] == operation
    assert Path(checkpoint["last_invocation"]).is_dir()
    return checkpoint_path, checkpoint


@pytest.mark.parametrize("operation", ["change", "release"])
def test_recorded_accepted_checkpoint_window_recovers_without_repeating_mutation(fixture, monkeypatch, operation):
    _interrupt_after_accepted(fixture, monkeypatch, operation)
    accepted = fixture.fake.current
    fixture.fake.calls.clear()
    result = fixture.run()
    assert result["ok"]
    assert result["members"][0]["results"]["recovered_invocation"]["accepted_id"] == accepted
    expected = ["read", "release", "read"] if operation == "change" else ["read"]
    assert [request["operation"] for request in fixture.fake.calls] == expected
    if operation == "change":
        assert fixture.fake.calls[1]["expected_current"] == accepted
    checkpoint = json.loads(Path(result["members"][0]["checkpoint_path"]).read_text())
    assert checkpoint["phase"] == "complete" and "pending_operation" not in checkpoint


@pytest.mark.parametrize("operation", ["change", "release"])
def test_accepted_without_durable_result_has_typed_block_and_preserves_state(fixture, monkeypatch, operation):
    path, _ = _interrupt_after_accepted(fixture, monkeypatch, operation, omit_result=True)
    before = path.read_bytes()
    accepted = fixture.fake.current
    fixture.fake.calls.clear()
    result = fixture.run()
    assert not result["ok"] and result["members"][0]["blocker"] == "author_recovery_result_missing"
    assert fixture.fake.calls == [] and fixture.fake.current == accepted
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["source", "toolchain", "request", "current", "ambiguous"])
def test_recovery_requires_exact_record_source_and_current(fixture, monkeypatch, kind):
    path, checkpoint = _interrupt_after_accepted(fixture, monkeypatch, "release")
    before = path.read_bytes()
    record_path = next(Path(checkpoint["last_invocation"]).glob("*-release.json"))
    if kind == "source":
        (fixture.member / "SKILL.md").write_text("source after interruption", encoding="utf-8")
    elif kind == "toolchain":
        fixture.cli.write_text("changed author runtime", encoding="utf-8")
    elif kind == "request":
        record = json.loads(record_path.read_text())
        record["request"]["expected_current"] = "sha256:" + "0" * 64
        record["request_fingerprint"] = suite.fingerprint_payload(record["request"])
        record_path.write_text(json.dumps(record), encoding="utf-8")
    elif kind == "ambiguous":
        (record_path.parent / "99-release.json").write_bytes(record_path.read_bytes())
    else:
        fixture.fake.read_mismatch = True
    fixture.fake.calls.clear()
    result = fixture.run()
    assert not result["ok"]
    assert result["members"][0]["blocker"].startswith("author_recovery_")
    assert [request["operation"] for request in fixture.fake.calls] == (["read"] if kind == "current" else [])
    assert path.read_bytes() == before


def test_source_drift_during_read_cannot_reuse_or_start_change(fixture, monkeypatch):
    assert fixture.run()["ok"]
    fixture.fake.calls.clear()
    def drifting_read(command, cwd):
        result = fixture.fake(command, cwd)
        (fixture.member / "SKILL.md").write_text("changed during current read", encoding="utf-8")
        return result
    monkeypatch.setattr(suite, "_run_json_command", drifting_read)
    result = fixture.run()
    assert not result["ok"] and [request["operation"] for request in fixture.fake.calls] == ["read"]
    assert "author_inputs_changed" in ";".join(result["blockers"])
    assert result["author_subprocess_count"] == 1
    member = result["members"][0]
    assert member["author_subprocess_count"] == 1
    assert member["blocker"] == "author_inputs_changed"
    assert member["results"]["current_read"]["payload"]["accepted_id"] == fixture.fake.current
    assert "change" not in member["results"]


def test_toolchain_drift_after_change_preserves_attempt_and_pending_cas(fixture, monkeypatch):
    def drifting_change(command, cwd):
        result = fixture.fake(command, cwd)
        fixture.cli.write_text("author runtime changed after change accepted", encoding="utf-8")
        return result
    monkeypatch.setattr(suite, "_run_json_command", drifting_change)
    result = fixture.run()
    assert not result["ok"] and result["author_subprocess_count"] == 1
    assert [request["operation"] for request in fixture.fake.calls] == ["change"]
    member = result["members"][0]
    assert member["author_subprocess_count"] == 1 and member["blocker"] == "author_toolchain_changed"
    assert member["results"]["change"]["payload"]["accepted_id"] == fixture.fake.current
    assert "release" not in member["results"]
    checkpoint = json.loads(Path(member["checkpoint_path"]).read_text())
    assert checkpoint["phase"] == "planned" and checkpoint["accepted_id"] is None
    assert checkpoint["pending_operation"] == "change"
    recorded = list(Path(checkpoint["last_invocation"]).glob("*-change.json"))
    assert len(recorded) == 1
    assert json.loads(recorded[0].read_text())["result"] == member["results"]["change"]
