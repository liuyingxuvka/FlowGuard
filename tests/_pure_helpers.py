"""Pure source/Git fixtures and declared historical inputs; no legacy CLI import."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


def write(root, relative, text):
    path=Path(root)/relative
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')


def git(root,*arguments):
    return subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0',
                           '-c','user.name=probe','-c','user.email=probe@example.invalid',
                           '-C',str(root),*arguments],check=True,capture_output=True).stdout


def project(root,capsys=None):
    root=Path(root)
    (root/'.flowguard').mkdir(parents=True,exist_ok=True)
    write(root,'app.py','def value():\n    return 1\n')
    return root


def call(root,capsys,*arguments):
    from flowguard.__main__ import main
    code=main([*arguments,'--root',str(root)])
    output=capsys.readouterr()
    return code,output.out,output.err


def integrity(root):
    """Inspect the retained independent readers directly, without map-check plumbing."""
    from flowguard.map.records import record_findings
    from flowguard.map.requests import request_findings
    findings=[*request_findings(root),*record_findings(root)]
    return findings


def integrity_result(root):
    findings=integrity(root)
    text='\n'.join(f'{finding.level} {finding.code}: {finding.message}' for finding in findings)
    return int(any(finding.level=='error' for finding in findings)),text,''


def historical_change(root,*,identifier='20261101-0000-abcdef',links=(),goal='Historical fixture input',fields=None):
    """A declared old record tests immutable readers, never a new verified promotion."""
    from flowguard.map.records import CHANGE_DIR,prepare_directory,write_once
    item=dict(kind='change',goal=goal,base=None,tree=hashlib.sha256(goal.encode()).hexdigest(),
              promoted=datetime(2026,11,1,tzinfo=timezone.utc).isoformat(),checked='Historical fixture input.',
              requests=list(links),plan=[],rules=[],acceptances=[],existing_cleared=[],implemented_by=[],
              new_actions=[],corrections=[])
    if fields:
        item.update(fields)
    prepare_directory(root,CHANGE_DIR,('.json','.msg'))
    relative=CHANGE_DIR/(identifier+'.json')
    write_once(root,relative,json.dumps(item,ensure_ascii=False).encode())
    return Path(root)/relative


def injected_project(root,*,service=None,cli=None):
    root=Path(root)
    files={'notes/__init__.py':'','notes/store.py':_INJECTED_STORE,
           'notes/service.py':_INJECTED_SERVICE if service is None else service}
    if cli is not None:
        files['notes/cli.py']=cli
    for relative,text in files.items():
        write(root,relative,text)
    return root


def resolution_case(root,files,caller,callee,*,import_roots=(),private=True):
    from flowguard.map.discover import discover_inventory
    from flowguard.map.inventory import build_inventory
    for relative,text in files.items():
        write(root,relative,text)
    inv=build_inventory(root,[],write_cache=False,import_roots=import_roots)
    raw=discover_inventory(root,inv,write_cache=False)
    assert callee in raw['edges'].get(caller,[]),raw['edges']
    if caller.partition('#')[0]!=callee.partition('#')[0]:
        assert callee.partition('#')[0] in inv.file_deps[caller.partition('#')[0]]
    return inv,raw


def write_discovery_project(root):
    for relative,text in {'notes/__init__.py':'','notes/app.py':APP,'notes/store.py':STORE,'notes/cli.py':CLI}.items():
        write(root,relative,text)

APP = '\nimport requests\nfrom notes.store import NoteStore\n\nclass App:\n    def __init__(self):\n        self.routes = {}\n    def route(self, path, methods=None):\n        def wrap(fn):\n            self.routes[path] = fn\n            return fn\n        return wrap\n\napp = App()\nstore = NoteStore("notes.db")\n\n@app.route("/notes", methods=["POST"])\ndef create_note(body):\n    store.add(body)\n    requests.post("https://hooks.example/notes", json=body)\n\n@app.route("/notes")\ndef list_notes():\n    return store.all()\n\ndef tally(items):\n    requests = []\n    requests.append(len(items))\n    return requests\n'

STORE = '\nimport sqlite3\n\nclass NoteStore:\n    def __init__(self, path):\n        self.conn = sqlite3.connect(path)\n        self.count = 0\n    def add(self, body):\n        cur = self.conn.cursor()\n        cur.execute("insert into notes values (?)", (body,))\n        self.count += 1\n    def all(self):\n        return self.conn.cursor().execute("select * from notes").fetchall()\n'

CLI = '\nimport argparse\nimport shutil\n\ndef main(argv=None):\n    p = argparse.ArgumentParser()\n    sub = p.add_subparsers(dest="cmd")\n    sub.add_parser("backup")\n    if p.parse_args(argv).cmd == "backup":\n        shutil.copy("notes.db", "notes.bak")\n\n\n\nif __name__ == "__main__":\n    main()\n'

_INJECTED_STORE = 'import json\n\n\nclass NoteStore:\n    def __init__(self, path):\n        self.path = path\n        self.notes = {}\n\n    def save(self, note_id, text):\n        self.notes[note_id] = text\n        with open(self.path, "w") as handle:\n            json.dump(self.notes, handle)\n\n    def delete(self, note_id):\n        self.notes.pop(note_id, None)\n        with open(self.path, "w") as handle:\n            json.dump(self.notes, handle)\n'

_INJECTED_SERVICE = 'class NoteService:\n    def __init__(self, store):\n        self.store = store\n\n    def add(self, note_id, text):\n        self.store.save(note_id, text)\n\n    def delete(self, note_id):\n        self.store.delete(note_id)\n'

_INJECTED_CLI = 'from notes.service import NoteService\nfrom notes.store import NoteStore\n\n\ndef main():\n    service = NoteService(NoteStore("notes.json"))\n    service.add("a", "first note")\n'
