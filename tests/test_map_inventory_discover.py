"""Tests grouped by their model or native component."""
from __future__ import annotations
import sys
from flowguard.map.discover import discover_inventory
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory

def test_attribute_calls_resolve_to_the_assigned_class(tmp_path):
    import sys
    from flowguard.map.discover import discover_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    marker = tmp_path / 'fg232-user-code-imported.txt'
    sources = {'fg232_shelf/__init__.py': '', 'fg232_shelf/members.py': 'class Members:\n    def may_borrow(self): return True\n    def shared(self): return True\n', 'fg232_shelf/catalog.py': 'class Catalog:\n    def take(self): return True\n    def flush(self): return True\n    def shared(self): return True\n', 'fg232_shelf/decoy.py': 'class Decoy:\n    def may_borrow(self): return False\n    def take(self): return False\n    def shared(self): return False\n', 'fg232_shelf/outside.py': 'class Outside:\n    def flush(self): return False\n', 'fg232_shelf/loans.py': f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\nfrom fg232_shelf.members import Members\nimport fg232_shelf.catalog as stock\nclass LoanService:\n    def __init__(self, catalog=None, dependency=None):\n        self.members = Members()\n        self.catalog = catalog or stock.Catalog()\n        self.unknown = dependency\n    def borrow(self):\n        self.members.may_borrow()\n        return self.catalog.take()\n    def flush(self): return self.unknown.flush()\n    def ambiguous(self): return self.unknown.shared()\n"}
    for relative, source in sources.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    raw = discover_inventory(tmp_path, inv)
    assert set(raw['edges']['fg232_shelf/loans.py#LoanService.borrow']) == {'fg232_shelf/members.py#Members.may_borrow', 'fg232_shelf/catalog.py#Catalog.take'}
    assert not raw['edges'].get('fg232_shelf/loans.py#LoanService.flush')
    assert not raw['edges'].get('fg232_shelf/loans.py#LoanService.ambiguous')
    assert not marker.exists()
    assert not any((name == 'fg232_shelf' or name.startswith('fg232_shelf.') for name in sys.modules))

def test_static_entrypoints_preserve_names_and_lines(tmp_path):
    source = tmp_path / 'commands.py'
    source.write_text('import click\n' + '\n'.join((f'@click.command()\ndef command_{i}(): pass\n' for i in range(5))))
    raw = discover_inventory(tmp_path, build_inventory(tmp_path, DEFAULT_IGNORE), write_cache=False)
    entries = raw['files']['commands.py']['entrypoints']
    assert {entry['symbol'] for entry in entries} == {f'command_{i}' for i in range(5)}
    assert all((entry['kind'] == 'cli_command' and isinstance(entry['line'], int) for entry in entries))
