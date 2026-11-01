"""Real promotions preserve immutable evidence and nongit release boundaries."""
from __future__ import annotations

import hashlib
import json
import shutil

import pytest

from test_requests import _call, _git, _plan_target, _project, _request_target


def _seed_git(root):
    _git(root, "init", "-q")
    paths = [".flowguard/map.json", ".flowguard/models"]
    paths += [path for path in ("native.py", "shelf", "tests", ".flowguard/requests") if (root / path).exists()]
    _git(root, "add", "--", *paths)
    _git(root, "commit", "-qm", "real project baseline")


def _promoted_project(root, capsys, *, git=False):
    from flowguard.map.requests import store_request

    _project(root, capsys)
    if git:
        _seed_git(root)
    store_request(root, b"extend shelf\n", identifier="R1")
    _request_target(root, capsys, "R1")
    code, output, errors = _call(root, capsys, "target", "promote", "--json")
    assert code == 0 and not errors, (output, errors)
    assert json.loads(output)["verdict"] == "PASS"
    assert _call(root, capsys, "map", "confirm", "all")[0] == 0
    return next((root / ".flowguard/changes").glob("*.json"))


def _record_refused(root, capsys):
    from flowguard.map.records import change_records, record_findings

    assert change_records(root) == []
    assert any(item.code == "record_edited" for item in record_findings(root))
    code, output, _ = _call(root, capsys, "map", "check", "--strict")
    assert code == 1 and "record_edited" in output
    code, output, _ = _call(root, capsys, "release", "--json")
    assert code != 0 and len(output.splitlines()) == 1
    verdict = json.loads(output)
    assert verdict["verdict"] == "FAIL"
    assert any(row["code"] == "record_edited" for row in verdict["codes"])


def test_real_promotion_records_checked_plan_rules_and_function_diff(tmp_path, capsys):
    from flowguard.map import target as native
    from flowguard.map.plan import rule_info
    from flowguard.map.mapfile import load_map
    from flowguard.map.targetfile import load_target, build_target_view
    from flowguard.map.records import change_records

    _plan_target(tmp_path)
    assert native.drop_target(tmp_path, yes=True) == 0
    _seed_git(tmp_path)
    assert native.start_target(tmp_path, "explain the changed rule") == 0
    assert native.add_to_target(tmp_path, "renew_limit") == 0
    target = load_target(tmp_path)
    view = build_target_view(tmp_path, load_map(tmp_path), target)
    fingerprint = lambda definition: "fp:" + hashlib.sha256(definition.encode()).hexdigest()
    old = fingerprint(rule_info(tmp_path, target, view)["renew_limit.renew_within_limit"]["definition"])
    model = tmp_path / ".flowguard/target/models/one.py"
    source = model.read_text().replace("if state in (0, availability_ceiling)",
                                      "if state in (0, availability_ceiling) and state >= 0")
    source = source.replace("invariants=INVARIANTS,", "invariants=INVARIANTS + (SECOND,),")
    model.write_text(source + '\nSECOND = Invariant("visible_limit", "record a nonnegative limit", lambda s,t: s >= 0)\n')
    implementation = tmp_path / "native.py"
    implementation.write_text(implementation.read_text().replace("def value(): return 1", "def value(optional=None): return 1"))
    lines = ['touch: native.py:value because "Keep the source edit visible."',
             'changes: renew_limit.renew_within_limit by RQuote "Renewals keep the limit 3."',
             'changes: renew_limit.visible_limit because "The nonnegative limit remains visible."']
    (tmp_path / ".flowguard/target/PLAN.txt").write_text("\n".join(lines) + "\n")
    definitions = rule_info(tmp_path, target, view)
    capsys.readouterr()
    code, output, errors = _call(tmp_path, capsys, "target", "promote", "--json")
    assert code == 0 and not errors, (output, errors)
    verdict = json.loads(output)
    assert verdict["verdict"] == "PASS"
    identifier, record = change_records(tmp_path)[0]
    assert [item["line"] for item in record["plan"]] == lines
    assert all(item["added_after_code"] is None and item["cleared"] == [] for item in record["plan"])
    rules = {item["id"]: item for item in record["rules"]}
    for name, previous, provenance in (
        ("renew_limit.renew_within_limit", old, "owner RQuote"),
        ("renew_limit.visible_limit", None, "because The nonnegative limit remains visible."),
    ):
        assert rules[name]["old"] == previous
        assert rules[name]["new"] == fingerprint(definitions[name]["definition"])
        assert rules[name]["provenance"] == provenance
    assert record["implemented_by"] == ["native.py:value"]
    block = verdict["owner_block"]
    assert block.index(lines[0]) < block.index(lines[1]) < block.index(lines[2])
    assert block.count("old rule:") == block.count("new rule:") == 2
    assert not (tmp_path / f".flowguard/changes/{identifier}.msg").exists()


def test_real_record_is_write_once_before_commit_and_after_clone(tmp_path, capsys):
    from flowguard.map import records
    from flowguard.map.mapfile import MapError

    root = tmp_path / "project"
    record = _promoted_project(root, capsys, git=True)
    assert not record.with_suffix(".msg").exists()
    originals = {record.name: record.read_bytes()}
    for name, raw in originals.items():
        path = record.parent / name
        relative = path.relative_to(root)
        with pytest.raises(MapError, match="immutable file"):
            records.write_once(root, relative, raw)
        path.unlink()
        with pytest.raises(MapError, match="immutable file"):
            records.write_once(root, relative, raw)
        path.write_bytes(raw + b"edited before first commit")
        _record_refused(root, capsys)
        path.write_bytes(raw)
    _git(root, "add", "--", ".flowguard/map.json", ".flowguard/models", ".flowguard/requests", ".flowguard/changes")
    _git(root, "commit", "-qm", "original promoted record")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(root), str(clone))
    assert not (clone / ".git/flowguard/written").exists()
    assert records.record_findings(clone) == []
    for name, raw in originals.items():
        path = clone / ".flowguard/changes" / name
        assert path.read_bytes() == raw
        path.write_bytes(raw + b"edited after fresh clone")
        _record_refused(clone, capsys)
        path.write_bytes(raw)


def test_independent_branches_merge_automatic_requests_and_real_records(tmp_path, capsys):
    from flowguard.map import records
    from flowguard.map.requests import owner_words, store_request

    root = _project(tmp_path / "project", capsys)
    _seed_git(root)
    seed = _git(root, "rev-parse", "HEAD").strip().decode()
    identifiers, changes = [], []
    for branch in ("left", "right"):
        _git(root, "checkout", "-qb", branch, seed)
        request = store_request(root, f"extend shelf for {branch}\n".encode())
        identifiers.append(request["id"])
        _request_target(root, capsys, request["id"])
        code, output, errors = _call(root, capsys, "target", "promote", "--json")
        assert code == 0 and not errors, (output, errors)
        assert json.loads(output)["verdict"] == "PASS"
        changes.append(records.change_records(root)[0][0])
        _git(root, "add", "--", ".flowguard/map.json", ".flowguard/models", ".flowguard/requests", ".flowguard/changes")
        _git(root, "commit", "-qm", branch + " actual promotion")
    assert len(set(identifiers)) == len(set(changes)) == 2
    _git(root, "merge", "--no-edit", "left")
    assert {identifier for identifier, _ in records.change_records(root)} == set(changes)
    assert records.record_findings(root) == []
    assert {row["id"] for row in owner_words(root)["rows"]
            if any(cited.startswith("change ") for cited in row["cited_by"])} == set(identifiers)
    assert _git(root, "ls-files", "-u") == b""
    assert not (root / ".flowguard/requests/index.json").exists()
    assert not (root / ".flowguard/changes/index.json").exists()


def test_nongit_release_snapshot_survives_cache_loss_and_rejects_edited_record(tmp_path, capsys):
    from flowguard.map import records
    from flowguard.map.impact_history import read_git_paths
    from flowguard.map.requests import request_findings, retire_request, store_request

    record = _promoted_project(tmp_path, capsys)
    store_request(tmp_path, b"Keep this pending request visible.\n", identifier="RWaiting")
    store_request(tmp_path, b"1. a plan an AI stored\n", identifier="RPlan")
    retire_request(tmp_path, "RPlan")
    code, output, errors = _call(tmp_path, capsys, "release", "--json")
    assert code == 0 and not errors and json.loads(output)["verdict"] == "PASS", (output, errors)
    snapshots = [tmp_path / ".flowguard/release-base" / name for name in ("records.json", "covered.json")]
    original = {path: path.read_bytes() for path in snapshots}
    shutil.rmtree(tmp_path / ".flowguard/cache")
    assert records.record_findings(tmp_path) == request_findings(tmp_path) == []
    history = records.since_release(tmp_path, records.change_records(tmp_path), read_git_paths)
    assert history["changes"] == [] and "snapshot" in history["known_from"].lower()
    store_request(tmp_path, b"A later request.\n", identifier="RLater")
    retire_request(tmp_path, "RWaiting")
    code, output, _ = _call(tmp_path, capsys, "status", "--json")
    assert code == 0
    words = json.loads(output)["owner_words"]
    assert [row["id"] for row in words["rows"] if not row["retired"]] == ["RLater", "R1"]
    assert words["retired_since_release"] == ["RWaiting"]
    assert request_findings(tmp_path) == []
    original_record = record.read_bytes()
    record.write_bytes(original_record + b"\n")  # valid JSON; byte protection must catch it
    _record_refused(tmp_path, capsys)
    assert {path: path.read_bytes() for path in snapshots} == original
    record.write_bytes(original_record)
    assert records.record_findings(tmp_path) == []
    # With Git the first committed blob is the one source; the nongit snapshot no longer answers.
    _seed_git(tmp_path)
    code, output, _ = _call(tmp_path, capsys, 'map', 'check', '--strict')
    assert code == 0 and 'immutable_unverified' in output and 'record_edited' not in output, output
    assert records.change_records(tmp_path) == []
    _git(tmp_path, 'add', '--', '.flowguard/changes', '.flowguard/release-base')
    _git(tmp_path, 'commit', '-qm', 'first committed record bytes')
    assert records.record_findings(tmp_path) == []
    assert [identifier for identifier, _ in records.change_records(tmp_path)] == [record.stem]
    assert _call(tmp_path, capsys, 'map', 'check', '--strict')[0] == 0
    record.write_bytes(original_record + b"\n")
    _record_refused(tmp_path, capsys)
    assert {path: path.read_bytes() for path in snapshots} == original


def test_release_snapshot_writer_failure_has_one_failing_json_verdict(tmp_path, capsys, monkeypatch):
    from flowguard.map import records

    _project(tmp_path, capsys)
    code, output, errors = _call(tmp_path, capsys, "release", "--json")
    assert code == 0 and not errors and json.loads(output)["verdict"] == "PASS", (output, errors)
    directory = tmp_path / ".flowguard/release-base"
    original = {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}
    called = []
    def unavailable(root):
        called.append(root)
        raise OSError("release snapshot writer unavailable")
    monkeypatch.setattr(records, "save_release_snapshot", unavailable)
    code, output, errors = _call(tmp_path, capsys, "release", "--json")
    assert called and code != 0 and len(output.splitlines()) == 1
    assert json.loads(output)["verdict"] == "FAIL" and "PASS" not in output
    assert "release snapshot writer unavailable" in errors
    assert {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()} == original


def _immutable_codes(output):
    return {code for code in ("owner_text_edited", "request_meta_edited", "record_edited") if code in output}


def test_unedited_copy_without_git_is_unverifiable_not_edited(tmp_path, capsys):
    root = tmp_path / "project"
    _promoted_project(root, capsys, git=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "promoted change")
    copy = tmp_path / "copy"
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns(".git"))
    code, output, _ = _call(copy, capsys, "map", "check", "--strict")
    assert code == 0 and not _immutable_codes(output), output
    assert "immutable_unverified" in output
    code, output, _ = _call(copy, capsys, "release", "--json")
    assert not _immutable_codes(output), output
    body = copy / ".flowguard/requests/R1.md"
    body.write_bytes(body.read_bytes() + b"x")
    code, output, _ = _call(copy, capsys, "map", "check", "--strict")
    assert code == 1 and "owner_text_edited" in output, output


def test_moved_nongit_project_is_unverifiable_not_edited(tmp_path, capsys):
    root = _project(tmp_path / "project", capsys)
    source = tmp_path / "owner.md"
    source.write_bytes(b"Keep this request after the folder moves.\n")
    assert _call(root, capsys, "req", "add", str(source), "--id", "R1")[0] == 0
    assert _call(root, capsys, "map", "check", "--strict")[0] == 0
    moved = tmp_path / "moved"
    root.rename(moved)
    code, output, _ = _call(moved, capsys, "map", "check", "--strict")
    assert code == 0 and not _immutable_codes(output), output
    assert "immutable_unverified" in output
    body = moved / ".flowguard/requests/R1.md"
    body.write_bytes(body.read_bytes() + b"x")
    code, output, _ = _call(moved, capsys, "map", "check", "--strict")
    assert code == 1 and "owner_text_edited" in output, output


def test_committed_file_has_one_answer_in_every_checkout(tmp_path, capsys):
    root = _project(tmp_path / "project", capsys)
    _seed_git(root)
    source = tmp_path / "owner.md"
    source.write_bytes(b"Keep one answer for committed requests.\n")
    assert _call(root, capsys, "req", "add", str(source), "--id", "R1")[0] == 0
    body = root / ".flowguard/requests/R1.md"
    meta = body.with_suffix(".json")
    item = json.loads(meta.read_bytes())
    body.write_bytes(body.read_bytes() + b"edited before the first commit\n")
    item.update(sha256=hashlib.sha256(body.read_bytes()).hexdigest(), bytes=len(body.read_bytes()))
    meta.write_bytes(json.dumps(item).encode())
    code, output, _ = _call(root, capsys, "map", "check", "--strict")
    assert code == 1 and "owner_text_edited" in output, output  # uncommitted: this checkout's receipt answers
    _git(root, "add", "--", ".flowguard/requests")
    _git(root, "commit", "-qm", "committed request bytes")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(root), str(clone))
    answers = []
    for checkout in (root, clone):
        code, output, _ = _call(checkout, capsys, "map", "check", "--strict")
        answers.append((code, _immutable_codes(output)))
    assert answers == [(0, set()), (0, set())], answers  # committed: the first committed blob answers
    for checkout in (root, clone):
        changed = checkout / ".flowguard/requests/R1.md"
        changed.write_bytes(changed.read_bytes() + b"x")
        code, output, _ = _call(checkout, capsys, "map", "check", "--strict")
        assert code == 1 and "owner_text_edited" in output, output


def test_unreadable_receipt_is_reported_as_unreadable_not_as_an_edit(tmp_path, capsys):
    from flowguard.map.records import _written_path

    root = _project(tmp_path / "project", capsys)
    source = tmp_path / "owner.md"
    source.write_bytes(b"Keep the request when its receipt is damaged.\n")
    assert _call(root, capsys, "req", "add", str(source), "--id", "R1")[0] == 0
    receipt = _written_path(root, root / ".flowguard/requests/R1.md", None)
    receipt.write_text("not a receipt\n", encoding="ascii")
    code, output, errors = _call(root, capsys, "map", "check", "--strict")
    assert code == 2 and "receipt_unreadable" in errors and str(receipt) in errors, (output, errors)
    assert not _immutable_codes(output + errors)
