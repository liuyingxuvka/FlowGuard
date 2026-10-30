"""Owner requests remain raw and visible, including before their first commit."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess

import pytest

from _fg_helpers import target__target_life_cycle_fixture_helpers as fixture_helpers


def _call(root, capsys, *arguments):
    from flowguard.__main__ import main
    code = main([*arguments, "--root", str(root)])
    output = capsys.readouterr()
    return code, output.out, output.err


def _project(root, capsys):
    fixture_helpers()["make_project"](root)
    assert _call(root, capsys, "map", "confirm", "all")[0] == 0
    return root


def _git(root, *arguments):
    return subprocess.run(["git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid",
                           "-C", str(root), *arguments], check=True, capture_output=True).stdout


def test_req_add_stores_bytes_and_digest(tmp_path, capsys):
    root = _project(tmp_path / "project", capsys)
    _git(root, "init", "-q")
    (root / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    raw = "主人原话 request\r\nkeep exact bytes\n".encode()
    source = tmp_path / "owner.md"
    source.write_bytes(raw)
    code, output, errors = _call(root, capsys, "req", "add", str(source), "--id", "R9")
    assert code == 0 and not errors, (output, errors)
    body = root / ".flowguard/requests/R9.md"
    metadata = body.with_suffix(".json")
    assert body.read_bytes() == raw
    item = json.loads(metadata.read_bytes())
    assert item["id"] == "R9" and item["kind"] == "request"
    assert item["sha256"] == hashlib.sha256(raw).hexdigest() and item["bytes"] == len(raw)
    assert datetime.fromisoformat(item["received"]).utcoffset().total_seconds() == 0
    before = metadata.read_bytes()
    code, output, errors = _call(root, capsys, "req", "add", str(source), "--id", "R9")
    assert code == 2 and "request_exists" in errors
    assert metadata.read_bytes() == before and body.read_bytes() == raw
    _git(root, "add", ".flowguard/requests")
    assert _git(root, "show", ":.flowguard/requests/R9.md") == raw
    assert b"*.md -text" in (body.parent / ".gitattributes").read_bytes()
    # A changed index blob is a real loss even while the worktree stays original.
    blob = subprocess.run(["git", "-C", str(root), "hash-object", "-w", "--stdin"],
                          input=raw.replace(b"\r\n", b"\n"), check=True, capture_output=True).stdout.strip().decode()
    _git(root, "update-index", "--cacheinfo", "100644", blob, ".flowguard/requests/R9.md")
    code, output, _ = _call(root, capsys, "map", "check", "--strict")
    assert code == 1 and "owner_text_edited" in output and body.read_bytes() == raw
    _git(root, "add", ".flowguard/requests")


@pytest.mark.parametrize("has_git", [False, True])
def test_owner_text_edited_with_and_without_git(tmp_path, capsys, has_git):
    root = _project(tmp_path / "project", capsys)
    if has_git:
        _git(root, "init", "-q")
    source = tmp_path / "owner.md"
    source.write_bytes(b"the owner asks for an exact request\r\n")
    assert _call(root, capsys, "req", "add", str(source), "--id", "R1")[0] == 0
    body = root / ".flowguard/requests/R1.md"
    metadata = body.with_suffix(".json")
    original = body.read_bytes(), metadata.read_bytes()
    if not has_git:
        assert _call(root, capsys, "target", "start", "check stored owner bytes")[0] == 0
        assert _call(root, capsys, "target", "add", "component:loans")[0] == 0
        target_path = root / ".flowguard/target/map.json"
        target = json.loads(target_path.read_bytes())
        target["components"][0]["summary"] += " with protected owner context"
        target_path.write_text(json.dumps(target), encoding="utf-8")
        assert _call(root, capsys, "target", "check", "--json")[0] == 0
    body.write_bytes(original[0] + b"edited")
    code, output, _ = _call(root, capsys, "map", "check", "--strict")
    assert code == 1 and "owner_text_edited" in output
    if not has_git:
        for command in (("target", "check"), ("release",)):
            code, output, _ = _call(root, capsys, *command, "--json")
            assert code == 1 and len(output.splitlines()) == 1
            verdict = json.loads(output)
            assert verdict["verdict"] == "FAIL"
            assert any(row["code"] == "owner_text_edited" for row in verdict["codes"])
    item = json.loads(original[1])
    item["sha256"] = hashlib.sha256(body.read_bytes()).hexdigest()
    item["bytes"] = len(body.read_bytes())
    metadata.write_bytes(json.dumps(item).encode())
    code, output, _ = _call(root, capsys, "map", "check", "--strict")
    assert code == 1 and "owner_text_edited" in output and "request_meta_edited" in output
    body.write_bytes(original[0])
    metadata.write_bytes(original[1])
    assert _call(root, capsys, "map", "check", "--strict")[0] == 0
    body.unlink()
    metadata.unlink()
    code, output, _ = _call(root, capsys, "map", "check", "--strict")
    assert code == 1 and "owner_text_edited" in output and "request_meta_edited" in output
    body.write_bytes(original[0])
    metadata.write_bytes(original[1])
    if has_git:
        _git(root, "add", ".")
        _git(root, "commit", "-qm", "original request")
        clone = tmp_path / "clone"
        _git(tmp_path, "clone", "-q", str(root), str(clone))
        changed = clone / ".flowguard/requests/R1.md"
        assert changed.read_bytes() == original[0]
        changed.write_bytes(original[0] + b"changed after clone")
        assert "owner_text_edited" in _call(clone, capsys, "map", "check", "--strict")[1]


def test_open_request_without_target_is_listed(tmp_path, capsys):
    root = _project(tmp_path / "project", capsys)
    source = tmp_path / "owner.md"
    source.write_bytes(b"Keep an unclaimed request visible.\n")
    for identifier in ("R5", "R7"):
        assert _call(root, capsys, "req", "add", str(source), "--id", identifier)[0] == 0
    code, output, errors = _call(root, capsys, "read")
    assert code == 0 and not errors
    header = next(line for line in output.splitlines() if line.startswith("requests:"))
    today = datetime.now(timezone.utc).date().isoformat()
    assert f"R7 open since {today} (no target)" in header
    assert "R5 open since" in header
    assert not (root / ".flowguard/requests/index.json").exists()


def test_final_request_ids_stdin_kinds_and_open_target_time(tmp_path, capsys, monkeypatch):
    import io
    import sys

    root = _project(tmp_path / "project", capsys)
    source = tmp_path / "owner.md"
    identifiers = []
    for number, length in ((25, 4), (143, 6)):
        raw = f"owner note {number}\n".encode()
        source.write_bytes(raw)
        code, output, errors = _call(root, capsys, "req", "add", str(source))
        identifier = 'R' + datetime.now(timezone.utc).strftime('%Y%m%d') + '-' + hashlib.sha256(raw).hexdigest()[:length]
        assert code == 0 and not errors and identifier in output
        assert (root / f".flowguard/requests/{identifier}.md").read_bytes() == raw
        identifiers.append(identifier)
    assert identifiers[1].startswith(identifiers[0]) and identifiers[0] != identifiers[1]
    assert _call(root, capsys, "req", "add", str(source), "--id", "9bad")[0] == 2
    assert _call(root, capsys, "req", "add", str(source), "--kind", "glossary")[0] == 2
    glossary = "续借 = renew, renewal\r\n".encode()
    with monkeypatch.context() as scoped:
        scoped.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(glossary), encoding="utf-8"))
        assert _call(root, capsys, "req", "add", "-", "--id", "G1", "--kind", "glossary")[0] == 0
    assert (root / ".flowguard/requests/G1.md").read_bytes() == glossary
    assert _call(root, capsys, "target", "start", "an open owner request")[0] == 0
    started = json.loads((root / ".flowguard/target/base.json").read_bytes())["started"]
    assert _call(root, capsys, "req", "add", str(source), "--id", "R0", "--kind", "adoption")[0] == 0
    item = json.loads((root / ".flowguard/requests/R0.json").read_bytes())
    assert item["kind"] == "adoption"
    assert item["stored_during"] == {"goal": "an open owner request", "started": started}


def test_written_protection_distinguishes_linked_worktrees(tmp_path, capsys):
    root = _project(tmp_path / "main", capsys)
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed")
    seed = _git(root, "rev-parse", "HEAD").strip().decode()
    peer = tmp_path / "peer"
    _git(root, "worktree", "add", "-qb", "peer", str(peer))
    source = tmp_path / "owner.md"
    for project, raw in ((root, b"first original\r\n"), (peer, b"second original\r\n")):
        source.write_bytes(raw)
        assert _call(project, capsys, "req", "add", str(source), "--id", "R9")[0] == 0
        assert _call(project, capsys, "map", "check", "--strict")[0] == 0
    _git(peer, "add", ".flowguard/requests")
    _git(peer, "commit", "-qm", "peer request")
    body = root / ".flowguard/requests/R9.md"
    metadata = body.with_suffix('.json')
    original = body.read_bytes(), metadata.read_bytes()
    body.unlink()
    metadata.unlink()
    assert "owner_text_edited" in _call(root, capsys, "map", "check", "--strict")[1]
    body.write_bytes(original[0])
    metadata.write_bytes(original[1])
    body.write_bytes(body.read_bytes() + b"changed")
    assert "owner_text_edited" in _call(root, capsys, "map", "check", "--strict")[1]
    assert _call(peer, capsys, "map", "check", "--strict")[0] == 0
    _git(peer, "checkout", "-qb", "without-request", seed)
    assert not (peer / '.flowguard/requests/R9.md').exists()
    assert _call(peer, capsys, "map", "check", "--strict")[0] == 0


def test_sidecar_attribute_conflict_leaves_no_half_request(tmp_path, capsys):
    root = _project(tmp_path / "project", capsys)
    _git(root, "init", "-q")
    # This is a disposable fixture's override, never the user's Git settings.
    (root / ".git/info/attributes").write_text(".flowguard/requests/R9.json text\n", encoding="utf-8")
    source = tmp_path / "owner.md"
    source.write_bytes(b"one original\r\n")
    code, output, errors = _call(root, capsys, "req", "add", str(source), "--id", "R9")
    assert code == 2 and "Git attributes transform immutable bytes" in errors
    assert not (root / ".flowguard/requests/R9.md").exists()
    assert not (root / ".flowguard/requests/R9.json").exists()
