"""Pure source/Git fixtures and declared historical inputs; no legacy CLI import."""
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
    """Read each archive's actual byte problems, without the retired finding renderer."""
    from flowguard.map.requests import _identifiers, _request_problems
    root = Path(root)
    unverified = []
    problems = {identifier: _request_problems(root, identifier, unverified)[:2]
                for identifier in _identifiers(root)}
    return problems, unverified


def integrity_result(root):
    problems, unverified = integrity(root)
    errors = [f'.flowguard/requests/{identifier}.{suffix}: {problem}'
              for identifier, pair in problems.items()
              for suffix, problem in zip(('md', 'json'), pair) if problem]
    lines = errors + (['unverified: original bytes are unavailable'] if unverified else [])
    return int(bool(errors)), '\n'.join(lines), ''





_INJECTED_STORE = 'import json\n\n\nclass NoteStore:\n    def __init__(self, path):\n        self.path = path\n        self.notes = {}\n\n    def save(self, note_id, text):\n        self.notes[note_id] = text\n        with open(self.path, "w") as handle:\n            json.dump(self.notes, handle)\n\n    def delete(self, note_id):\n        self.notes.pop(note_id, None)\n        with open(self.path, "w") as handle:\n            json.dump(self.notes, handle)\n'

_INJECTED_SERVICE = 'class NoteService:\n    def __init__(self, store):\n        self.store = store\n\n    def add(self, note_id, text):\n        self.store.save(note_id, text)\n\n    def delete(self, note_id):\n        self.store.delete(note_id)\n'

_INJECTED_CLI = 'from notes.service import NoteService\nfrom notes.store import NoteStore\n\n\ndef main():\n    service = NoteService(NoteStore("notes.json"))\n    service.add("a", "first note")\n'
