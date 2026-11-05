"""Printed advice names current commands that replay from another working directory."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

from _pure_helpers import call as _call


def _next(output, root):
    from flowguard.__main__ import _verb_parser
    from flowguard.map.common import ADVICE_IDS
    items=[]
    for line in output.splitlines():
        if not line.startswith('next['):
            continue
        match=re.fullmatch(r'next\[([a-z_]+)\]: (.+)',line)
        assert match,line
        identifier,command=match.groups()
        assert identifier in ADVICE_IDS
        argv=shlex.split(command)
        assert argv[:3]==['python','-m','flowguard']
        assert not any('<' in arg or '>' in arg or arg in {'then','&&',';'} for arg in argv)
        parsed=_verb_parser(argv[3]).parse_args(argv[4:])
        assert Path(parsed.root)==root.resolve()
        items.append(dict(id=identifier,command=command))
    assert items,output
    return items


def _replay(item, elsewhere):
    argv=shlex.split(item['command'])
    assert argv[3] in {'where','status'}
    elsewhere.mkdir(exist_ok=True)
    environment=dict(os.environ)
    environment['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
    return subprocess.run(argv,cwd=elsewhere,env=environment,capture_output=True,text=True,timeout=30)


def test_request_without_map_advises_status_that_runs(tmp_path, capsys):
    root = tmp_path / "中文 plain folder"
    root.mkdir()
    source = root / "owner request.txt"
    original = "续借保持为三次。\r\nPreserve owner bytes.\n".encode()
    source.write_bytes(original)
    (root / "app.py").write_text("def run(): return 1\n", encoding="utf-8")
    code, output, errors = _call(root, capsys, "req", "add", str(source), "--id", "R1")
    assert code == 0 and not errors
    item, = _next(output, root)
    argv = shlex.split(item["command"])
    assert item["id"] == "status" and argv[3] == "status"
    requests = root / ".flowguard/requests"
    snapshot = {path.name: path.read_bytes() for path in requests.iterdir() if path.is_file()}
    assert original in snapshot.values()
    status = _replay(item, tmp_path / "other cwd")
    assert status.returncode == 0, (status.stdout, status.stderr)
    assert not (root / ".flowguard/map.json").exists()
    assert source.read_bytes() == original
    assert snapshot == {path.name: path.read_bytes() for path in requests.iterdir() if path.is_file()}



def test_where_truncation_advice_replays_the_complete_source_view(tmp_path,capsys):
    root=tmp_path/'中文 lookup';root.mkdir()
    for index in range(40):
        (root/f'part{index}.py').write_text('def run(): return 1\n')
    code,output,errors=_call(root,capsys,'where')
    assert code==0 and not errors
    items=_next(output,root)
    assert any('--all' in shlex.split(item['command']) for item in items)
    for item in items:
        replay=_replay(item,tmp_path/'other cwd')
        assert replay.returncode==0,replay.stdout+replay.stderr
        if '--all' in shlex.split(item['command']):
            assert 'part39.py' in replay.stdout


def test_text_json_and_human_advice_share_replayable_commands(tmp_path,capsys):
    root=tmp_path/'text lookup';root.mkdir()
    (root/'README.md').write_text('# Shipping\n\nOrders must be ready before shipping.\n')
    (root/'app.py').write_text('STATE = "ready"\n')
    code,human,errors=_call(root,capsys,'where','--text')
    assert code==0 and not errors
    items=_next(human,root)
    code,structured,errors=_call(root,capsys,'where','--text','--json')
    assert code==0 and not errors
    payload=json.loads(structured)
    assert [item['id'] for item in payload['next']]==[item['id'] for item in items]
    for item in payload['next']:
        replay=_replay(item,tmp_path/'elsewhere')
        assert replay.returncode==0,replay.stdout+replay.stderr
        assert len(replay.stdout.splitlines())==1
        json.loads(replay.stdout)


def test_no_next_line_is_built_outside_the_shared_advice_renderer():
    """The round-11 check: no source line in flowguard/ builds a `next: ...` text of its own."""
    pattern = re.compile(r'"next: |next: "|\("next: ')
    package = Path(__file__).resolve().parents[1] / "flowguard"
    found = [f"{path.relative_to(package.parent).as_posix()}:{number}"
             for path in sorted(package.rglob("*.py"))
             for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if pattern.search(line)]
    assert found == [], found
