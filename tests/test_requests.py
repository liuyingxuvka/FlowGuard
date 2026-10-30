"""Owner requests remain raw and visible, including before their first commit."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess

import pytest

from _fg_helpers import (
    target__target_life_cycle_fixture_helpers as fixture_helpers,
    target__fg403_helpers as gap_helpers,
)


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


def _plan_target(root):
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map
    from flowguard.map.requests import store_request
    from flowguard.map.targetfile import load_target, build_target_view

    source = gap_helpers()["regular_source"]().replace('MODEL_ID = \'one\'', 'MODEL_ID = \'renew_limit\'')
    source = source.replace('"answer"', '"renew_within_limit"')
    source = source.replace('INVARIANTS = (', 'availability_ceiling = EXPECTED["renew_within_limit"]\nINVARIANTS = (')
    source = source.replace('s in (0, EXPECTED["renew_within_limit"])', 's in (0, availability_ceiling)')
    source = source.replace('lambda s,t:', 'lambda state,trace:').replace(
        'if s in (0, availability_ceiling)', 'if state in (0, availability_ceiling)')
    gap_helpers()["make_project"](root, source)
    owner = 'Renewals keep the limit 3.\nThe ceiling remains 1.\nThe desk opens at nine.\n续借的 limit 仍然是 3\n续借次数保持为3。\nThe state is visible.\n'
    store_request(root, owner.encode(), identifier="RQuote")
    native.start_target(root, "explain the changed rule")
    native.add_to_target(root, "renew_limit")
    target = load_target(root)
    return target, build_target_view(root, load_map(root), target)


def test_quote_check_verbatim_and_elision():
    from flowguard.map.plan import quote_matches
    text = 'Renewals keep\n the limit 3.\n续借的 limit 仍然是 3'
    assert quote_matches(text, 'Renewals keep the limit 3.')
    assert quote_matches(text, 'Renewals ... limit 3.')
    assert not quote_matches(text, 'Renewals keep the limit 4.')
    assert quote_matches(text, '续借的 limit 仍然是 3')
    assert not quote_matches(text, '续借的 limit 仍然是 4')


def test_changes_line_syntax(tmp_path):
    from flowguard.map.plan import check_plan
    target, view = _plan_target(tmp_path)
    path = tmp_path / ".flowguard/target/PLAN.txt"
    for line, expected in (
        ('changes: renew_limit.renew_within_limit by RQuote "Renewals keep the limit 3."', None),
        ('changes: renew_limit.renew_within_limit because "The lower bound is intentional."', None),
        ('changes: renew_limit.renew_within_limit because missing_quotes', 'line_syntax'),
        ('changes: renew_limit.renew_within_limit RQuote "Renewals keep the limit 3."', 'line_syntax'),
        ('changes: missing.renew_within_limit because "intentional"', 'line_syntax'),
        ('changes: renew_limit.renew_within_limit by R9 "Renewals keep the limit 3."', 'request_unknown'),
        ('changes: renew_limit.renew_within_limit by RQuote "Renewals keep the limit 4."', 'quote_not_in_request'),
    ):
        path.write_text(line + "\n", encoding="utf-8")
        items, findings = check_plan(tmp_path, target, view)
        assert [item.code for item in findings] == ([] if expected is None else [expected]), (line, findings)
        if expected is None:
            assert len(items) == 1


def test_changes_quote_needs_shared_term(tmp_path):
    from flowguard.map.plan import check_plan
    from flowguard.map.requests import store_request
    target, view = _plan_target(tmp_path)
    path = tmp_path / ".flowguard/target/PLAN.txt"
    for quote, accepted in (('Renewals keep the limit 3.', True), ('The ceiling remains 1.', True),
                            ('The desk opens at nine.', False),
                            ('续借的 limit 仍然是 3', True), ('The state is visible.', False)):
        path.write_text(f'changes: renew_limit.renew_within_limit by RQuote "{quote}"\n', encoding="utf-8")
        _, findings = check_plan(tmp_path, target, view)
        assert [item.code for item in findings] == ([] if accepted else ['link_without_shared_term'])
    path.write_text('changes: renew_limit.renew_within_limit by RQuote "续借次数保持为3。"\n', encoding="utf-8")
    assert any(item.code == 'link_without_shared_term' for item in check_plan(tmp_path, target, view)[1])
    store_request(tmp_path, '续借次数 = limit\n'.encode(), identifier="RGloss", kind="glossary")
    items, findings = check_plan(tmp_path, target, view)
    assert not findings and items[0]['glossary_used']


@pytest.mark.parametrize("as_json", [False, True])
def test_promote_prints_owner_block(tmp_path, capsys, as_json):
    from flowguard.map import target as native

    _plan_target(tmp_path)
    model = tmp_path / '.flowguard/target/models/one.py'
    source = model.read_text().replace('if state in (0, availability_ceiling)',
                                      'if state in (0, availability_ceiling) and state >= 0')
    source = source.replace('invariants=INVARIANTS,', 'invariants=INVARIANTS + (SECOND,),')
    source += '\nSECOND = Invariant("visible_limit", "record a nonnegative limit", lambda s,t: s >= 0)\n'
    model.write_text(source)
    first = 'changes: renew_limit.renew_within_limit by RQuote "Renewals keep the limit 3."'
    second = 'changes: renew_limit.visible_limit because "The nonnegative limit remains visible."'
    (tmp_path / '.flowguard/target/PLAN.txt').write_text(first + '\n' + second + '\n', encoding='utf-8')
    capsys.readouterr()
    assert native.promote_target(tmp_path, as_json=as_json) == 0
    output = capsys.readouterr().out
    if as_json:
        assert len(output.splitlines()) == 1
        verdict = json.loads(output)
        assert verdict['verdict'] == 'PASS'
        output = verdict['owner_block']
    header = 'owner block (paste it unchanged into your final message):'
    assert header in output
    assert output.index(first) < output.index(second)
    assert output.count('old rule:') == 2 and output.count('new rule:') == 2
    assert 'availability_ceiling' in output and 'and state >= 0' in output
    assert '(absent: this rule did not exist)' in output
    message = next((tmp_path / '.flowguard/changes').glob('*.msg')).read_text()
    block = message[message.index(header):].rstrip()
    assert block in output


def test_owner_block_marks_stored_requests_and_glossary(tmp_path):
    from flowguard.map.mapfile import load_map
    from flowguard.map.plan import check_plan, render_owner_block, rule_info
    from flowguard.map.requests import store_request
    from flowguard.map.records import CHANGE_DIR, prepare_directory, write_once

    target, view = _plan_target(tmp_path)
    raw = '续借次数保持为1。\nOwner original second line.\n'
    request = store_request(tmp_path, raw.encode(), identifier='RDuring')
    glossary = store_request(tmp_path, '续借次数 = availability_ceiling\n'.encode(), identifier='GDuring', kind='glossary')
    source = tmp_path / 'native.py'
    source.write_text(source.read_text().replace('def value(): return 1', 'def value(optional=None): return 1'))
    touch = 'touch: native.py:value because "Keep the source edit visible."'
    change = 'changes: renew_limit.renew_within_limit by RDuring "续借次数保持为1。"'
    (tmp_path / '.flowguard/target/PLAN.txt').write_text(touch + '\n' + change + '\n', encoding='utf-8')
    items, findings = check_plan(tmp_path, target, view)
    assert not findings
    block = render_owner_block(tmp_path, load_map(tmp_path), target, view, items)
    assert block.index(touch) < block.index(change)
    assert 'RDuring: stored during this change at ' + request['received'] in block
    assert 'GDuring: stored during this change at ' + glossary['received'] in block
    assert 'glossary GDuring: 续借次数 = availability_ceiling' in block
    assert 'Owner original second line.' not in block
    # A declared historical record supplies existing owner provenance. It is not
    # a newly manufactured promotion verdict or a provenance claim for this edit.
    received = json.loads((tmp_path / '.flowguard/requests/RQuote.json').read_bytes())['received']
    prior = dict(kind='change', goal='record the earlier owner rule', requests=[dict(id='RQuote', part=False)],
                 base=None, tree='a' * 64, promoted=received,
                 plan=[dict(line='changes: renew_limit.renew_within_limit by RQuote "Renewals keep the limit 3."',
                            added_after_code=False, cleared=[])],
                 rules=[dict(id='renew_limit.renew_within_limit', old=None,
                             new='fp:' + hashlib.sha256(rule_info(tmp_path, target, view)['renew_limit.renew_within_limit']['definition'].encode()).hexdigest(),
                             provenance='owner RQuote')],
                 acceptances=[], existing_cleared=[], implemented_by=[], new_actions=[], corrections=[], checked='Historical fixture input.')
    prepare_directory(tmp_path, CHANGE_DIR, ('.json', '.msg'))
    identifier = datetime.fromisoformat(received).strftime('%Y%m%d-%H%M-') + 'aaaaaa'
    write_once(tmp_path, CHANGE_DIR / (identifier + '.msg'), (prior['goal'] + '\n\n' + prior['checked'] + '\n').encode())
    write_once(tmp_path, CHANGE_DIR / (identifier + '.json'), json.dumps(prior).encode())
    block = render_owner_block(tmp_path, load_map(tmp_path), target, view, items)
    assert 'full request RDuring:' in block and 'Owner original second line.' in block
    assert 'full request GDuring:' in block
    from flowguard.map import target as native
    from flowguard.map.targetfile import load_target, build_target_view
    assert native.drop_target(tmp_path, yes=True) == 0
    assert native.start_target(tmp_path, 'a later change') == 0
    assert native.add_to_target(tmp_path, 'renew_limit') == 0
    target = load_target(tmp_path)
    view = build_target_view(tmp_path, load_map(tmp_path), target)
    (tmp_path / '.flowguard/target/PLAN.txt').write_text(change + '\n', encoding='utf-8')
    items, findings = check_plan(tmp_path, target, view)
    assert not findings
    reused = render_owner_block(tmp_path, load_map(tmp_path), target, view, items)
    assert request['stored_during']['goal'] in reused and request['stored_during']['started'] in reused
    assert 'stored during this change at ' + request['received'] not in reused


@pytest.mark.parametrize("git_backed", [False, True])
def test_touch_uses_actual_function_change(tmp_path, git_backed):
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map
    from flowguard.map.plan import check_plan
    from flowguard.map.targetfile import load_target, build_target_view

    gap_helpers()["make_project"](tmp_path, gap_helpers()["regular_source"]())
    if git_backed:
        _git(tmp_path, 'init', '-q')
        _git(tmp_path, 'add', '.')
        _git(tmp_path, 'commit', '-qm', 'function baseline')
    native.start_target(tmp_path, 'change the function')
    native.add_to_target(tmp_path, 'one')
    target = load_target(tmp_path)
    view = build_target_view(tmp_path, load_map(tmp_path), target)
    (tmp_path / '.flowguard/target/PLAN.txt').write_text('touch: native.py:value because "Change the declared function."\n', encoding='utf-8')
    assert any(item.code == 'plan_item_not_done' for item in check_plan(tmp_path, target, view)[1])
    source = tmp_path / 'native.py'
    original = source.read_text()
    source.write_text(original.replace('def value(): return 1', 'def value():\n    """New words only."""\n    # no behavior change\n    return 1'))
    assert any(item.code == 'plan_item_not_done' for item in check_plan(tmp_path, target, view)[1])
    source.write_text(original.replace('def value(): return 1', 'def value(optional=None): return 1'))
    items, findings = check_plan(tmp_path, target, view)
    assert not findings and items[0]['reason'] == 'Change the declared function.'
    source.write_text('def value(): return 1\ndef value(): return 2\n')
    assert any('ambiguous' in item.message for item in check_plan(tmp_path, target, view)[1])
    source.write_text(original.replace('def value(): return 1', 'def value(optional=None): return 1'))
    if not git_backed:
        base_path = tmp_path / '.flowguard/target/base.json'
        base = json.loads(base_path.read_text())
        for entry in base['files'].values():
            entry.pop('functions', None)
        base_path.write_text(json.dumps(base))
        assert any(item.code == 'plan_item_not_done' for item in check_plan(tmp_path, target, view)[1])


def _request_target(root, capsys, link):
    code, output, errors = _call(root, capsys, "target", "start", "extend shelf", "--request", link)
    assert code == 0 and not errors, (output, errors)
    assert _call(root, capsys, "target", "add", "loans")[0] == 0
    assert _call(root, capsys, "target", "add", "shelf_rule")[0] == 0
    model = root / ".flowguard/target/models/shelf_rule.py"
    model.write_text(model.read_text() + "\nTARGET_REVISION = 2\n", encoding="utf-8")


def test_promote_marks_linked_request_done(tmp_path, capsys):
    from flowguard.map.requests import store_request, request_rows

    for partial in (False, True):
        root = _project(tmp_path / str(partial), capsys)
        store_request(root, b"extend shelf\r\n", identifier="R1")
        store_request(root, b"leave this request visible\n", identifier="R2")
        originals = {p.name: p.read_bytes() for p in (root / ".flowguard/requests").glob("R*.*")}
        _request_target(root, capsys, "R1:part" if partial else "R1")
        data = json.loads((root / ".flowguard/target/map.json").read_bytes())
        assert data["requests"] == [{"id": "R1", "part": partial}]
        assert any("R1 in this change" in row for row in request_rows(root))
        code, output, errors = _call(root, capsys, "target", "promote")
        assert code == 0 and not errors, (output, errors)
        records = list((root / ".flowguard/changes").glob("*.json"))
        assert len(records) == 1
        item = json.loads(records[0].read_bytes())
        assert item["kind"] == "change" and item["requests"] == data["requests"]
        assert records[0].with_suffix(".msg").is_file()
        rows = request_rows(root)
        assert any(("R1 open since" if partial else "R1 done (change ") in row for row in rows)
        assert any("R2 open since" in row for row in rows)
        assert {p.name: p.read_bytes() for p in (root / ".flowguard/requests").glob("R*.*")} == originals
        if not partial:
            from flowguard.map.records import change_records, record_findings
            records[0].write_bytes(records[0].read_bytes() + b" ")
            assert change_records(root) == []
            assert any(item.code == "record_edited" for item in record_findings(root))
            assert any("R1 open since" in row for row in request_rows(root))


def test_request_link_refusal_and_failed_record_do_not_complete(tmp_path, capsys, monkeypatch):
    from flowguard.map import records
    from flowguard.map.requests import store_request, request_rows

    root = _project(tmp_path / "project", capsys)
    code, output, errors = _call(root, capsys, "target", "start", "unknown", "--request", "R9")
    assert code == 2 and "R9 is not stored" in errors and "--id R9" in errors
    assert not (root / ".flowguard/target").exists()
    store_request(root, b"complete this request\n", identifier="R1")
    code, _, errors = _call(root, capsys, "target", "start", "duplicate", "--request", "R1", "--request", "R1:part")
    assert code == 2 and "duplicate request R1" in errors
    _request_target(root, capsys, "R1")
    path = root / ".flowguard/target/map.json"
    target = json.loads(path.read_bytes())
    target["requests"][0]["id"] = "R9"
    path.write_text(json.dumps(target), encoding="utf-8")
    code, output, errors = _call(root, capsys, "target", "promote")
    assert code == 1 and "request_unknown" in output
    assert not list((root / ".flowguard/changes").glob("*.json"))
    target["requests"][0]["id"] = "R1"
    path.write_text(json.dumps(target), encoding="utf-8")
    (root / '.flowguard/target/PLAN.txt').write_text(
        'changes: shelf_rule.one_loan_step because "Complete the recorded request."\n', encoding='utf-8')
    original = records.write_once
    def fail_json(root, path, raw, **kwargs):
        if Path(path).parent == records.CHANGE_DIR and Path(path).suffix == ".json":
            raise OSError("record writer unavailable")
        return original(root, path, raw, **kwargs)
    monkeypatch.setattr(records, "write_once", fail_json)
    code, output, errors = _call(root, capsys, "target", "promote", "--json")
    verdict = json.loads(output)
    assert code == 2 and verdict["verdict"] == "FAIL"
    assert any(item["code"] == "operation_failed" for item in verdict["codes"])
    assert 'owner_block' not in verdict
    assert "tree was applied" in errors and "no complete change record" in errors
    assert not (root / ".flowguard/target").exists()
    assert records.change_records(root) == [] and records.record_findings(root) == []
    assert not list((root / records.CHANGE_DIR).glob("*.msg"))
    assert any("R1 open since" in row for row in request_rows(root))


def test_request_state_prefers_this_target_then_other_worktree(tmp_path, capsys):
    from flowguard.map.requests import store_request, request_rows

    root = _project(tmp_path / "repository/project", capsys)
    _git(root.parent, "init", "-q")
    store_request(root, b"a shared request\n", identifier="R1")
    _git(root, "add", "--", ".flowguard/map.json", ".flowguard/models", ".flowguard/requests", "shelf", "tests")
    _git(root, "commit", "-qm", "shared request")
    peer_root = tmp_path / "peer"
    _git(root, "worktree", "add", "-qb", "peer", str(peer_root))
    peer = peer_root / "project"
    assert _call(peer, capsys, "target", "start", "peer change", "--request", "R1:part")[0] == 0
    assert any(f"R1 in another change ({peer})" in row for row in request_rows(root))
    assert _call(root, capsys, "target", "start", "this change", "--request", "R1")[0] == 0
    assert any("R1 in this change" in row for row in request_rows(root))


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


def test_request_receipts_survive_git_init(tmp_path, capsys):
    root = _project(tmp_path / 'project', capsys)
    source = tmp_path / 'owner.md'
    source.write_bytes(b'Keep the original request across git init.\r\n')
    assert _call(root, capsys, 'req', 'add', str(source), '--id', 'RTransition')[0] == 0
    body = root / '.flowguard/requests/RTransition.md'
    meta = body.with_suffix('.json')
    original = body.read_bytes(), meta.read_bytes()
    assert _call(root, capsys, 'map', 'check', '--strict')[0] == 0
    _git(root, 'init', '-q')
    assert _call(root, capsys, 'map', 'check', '--strict')[0] == 0
    from flowguard.map.records import _written_path
    common = Path(_git(root, 'rev-parse', '--git-common-dir').decode().strip())
    if not common.is_absolute():
        common = root / common
    competing = _written_path(root, body, common)
    competing.parent.mkdir(parents=True, exist_ok=True)
    competing.write_text(json.dumps(dict(path=body.as_posix(), sha256='0' * 64)), encoding='ascii')
    code, output, _ = _call(root, capsys, 'map', 'check', '--strict')
    assert code == 1 and 'conflicting first-write receipts' in output
    competing.unlink()
    body.write_bytes(original[0] + b'edited')
    item = json.loads(original[1])
    item.update(sha256=hashlib.sha256(body.read_bytes()).hexdigest(), bytes=len(body.read_bytes()))
    meta.write_bytes(json.dumps(item).encode())
    code, output, _ = _call(root, capsys, 'map', 'check', '--strict')
    assert code == 1 and 'owner_text_edited' in output and 'request_meta_edited' in output
    body.unlink()
    meta.unlink()
    code, output, _ = _call(root, capsys, 'map', 'check', '--strict')
    assert code == 1 and 'owner_text_edited' in output and 'request_meta_edited' in output
    code, _, errors = _call(root, capsys, 'req', 'add', str(source), '--id', 'RTransition')
    assert code == 2 and 'request_exists' in errors
    assert not body.exists() and not meta.exists()


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
