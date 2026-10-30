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
    assert block in (tmp_path / f".flowguard/changes/{identifier}.msg").read_text()


def test_real_record_pair_is_write_once_before_commit_and_after_clone(tmp_path, capsys):
    from flowguard.map import records
    from flowguard.map.mapfile import MapError

    root = tmp_path / "project"
    record = _promoted_project(root, capsys, git=True)
    originals = {path.name: path.read_bytes() for path in (record, record.with_suffix(".msg"))}
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
    _git(root, "commit", "-qm", "original promoted pair")
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
    from flowguard.map.requests import request_details, store_request

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
    assert {row["id"] for row in request_details(root) if row["state"].startswith("done ")} == set(identifiers)
    assert _git(root, "ls-files", "-u") == b""
    assert not (root / ".flowguard/requests/index.json").exists()
    assert not (root / ".flowguard/changes/index.json").exists()


def test_nongit_release_snapshot_survives_cache_loss_and_rejects_edited_record(tmp_path, capsys):
    from flowguard.map import records
    from flowguard.map.impact_history import read_git_paths
    from flowguard.map.requests import request_findings, store_request

    record = _promoted_project(tmp_path, capsys)
    store_request(tmp_path, b"Keep this pending request visible.\n", identifier="RWaiting")
    code, output, errors = _call(tmp_path, capsys, "release", "--json")
    assert code == 0 and not errors and json.loads(output)["verdict"] == "PASS", (output, errors)
    snapshots = [tmp_path / ".flowguard/release-base" / name for name in ("records.json", "covered.json")]
    original = {path: path.read_bytes() for path in snapshots}
    shutil.rmtree(tmp_path / ".flowguard/cache")
    assert records.record_findings(tmp_path) == request_findings(tmp_path) == []
    history = records.since_release(tmp_path, records.change_records(tmp_path), read_git_paths)
    assert history["changes"] == [] and "snapshot" in history["known_from"].lower()
    store_request(tmp_path, b"A later request.\n", identifier="RLater")
    code, output, _ = _call(tmp_path, capsys, "status", "--json")
    assert code == 0
    requests = {row["id"]: row for row in json.loads(output)["requests"]}
    assert requests["RWaiting"]["since_release"] is False
    assert requests["RLater"]["since_release"] is True
    original_record = record.read_bytes()
    record.write_bytes(original_record + b"\n")  # valid JSON; byte protection must catch it
    _record_refused(tmp_path, capsys)
    assert {path: path.read_bytes() for path in snapshots} == original
    # A later first Git commit cannot supersede the earlier independent digest.
    _seed_git(tmp_path)
    _git(tmp_path, 'add', '--', '.flowguard/changes', '.flowguard/release-base')
    _git(tmp_path, 'commit', '-qm', 'first committed record bytes still disagree with the original release')
    _record_refused(tmp_path, capsys)
    assert {path: path.read_bytes() for path in snapshots} == original
    record.write_bytes(original_record)
    _git(tmp_path, 'add', '--', record.relative_to(tmp_path).as_posix())
    assert records.record_findings(tmp_path) == []
    assert _call(tmp_path, capsys, 'map', 'check', '--strict')[0] == 0


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
