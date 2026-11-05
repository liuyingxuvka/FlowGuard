"""Native directory metadata stays a typed footprint dependency, not a source file."""
from pathlib import Path
from flowguard.flow.parts import PartContext,PartSpec,core_part
from flowguard.flow.project import cache_dir
from flowguard.native.inputs import footprint_evidence
import pytest


@pytest.mark.parametrize('newline', [b'\n', b'\r\n'], ids=['lf', 'crlf'])
def test_unchanged_native_inputs_are_reusable_and_real_source_edits_are_not(project, newline):
    from flowguard.flow.jobs import Planned, lookup, store
    from flowguard.native.inputs import directory_stamp, file_stamp, module_lookup_stamp

    source = project.root / 'app.py'
    raw = b'class Program:\n    def __init__(self): self.value = 0\n    def run(self): self.value = 1\n'.replace(b'\n', newline)
    source.write_bytes(raw)
    path = project.flow('current_native', '''from flowguard.flow import Model
from flowguard.flow.adapter import fields
m = Model('current native', covers=['app.py:Program'])
m.field('value', (0, 1), 0)
@m.action()
def run(s): s['value'] = 1
m.terminal('value', (1,))
m.bind_adapter({'system': 'app:Program', 'classes': ['app:Program']},
               state=lambda snapshot: fields(snapshot, names=('value',)), operations={'run': 'run'})
MODEL = m
''')
    spec = PartSpec('core', 'current_native')
    part = core_part(PartContext(project.root, spec, path, cache_dir(project.root)))
    assert part.complete
    assert part.info['native']['footprints']
    for footprint in part.info['native']['footprints']:
        evidence = footprint_evidence(footprint)
        reason = evidence.reason
        detail = {'status': evidence.status, 'reason': reason}
        if reason in footprint['files']:
            detail.update(previous=footprint['files'][reason], current=file_stamp(reason))
        elif reason in footprint['directories']:
            usage = footprint.get('directory_uses', {}).get(reason, {})
            detail.update(previous=footprint['directories'][reason], current=directory_stamp(reason), usage=usage)
            if usage.get('kind') == 'module-lookup':
                detail['current_lookups'] = {name: module_lookup_stamp(reason, name) for name in usage['lookups']}
        assert evidence.status == 'current', detail
    assert part.info['native']['status'] == 'conformant'
    store(project.root, part)
    item = Planned(spec, path.relative_to(project.root).as_posix())
    assert lookup(project.root, item) is not None
    assert source.read_bytes() == raw
    source.write_bytes(raw.replace(b'self.value = 1', b'self.value = 0'))
    assert lookup(project.root, item) is None


def test_lazy_import_directory_metadata_is_not_a_source_manifest_file(project):
    project.file('dependency/__init__.py','')
    project.file('dependency/signal.py','VALUE=1\n')
    project.file('consumer/driver.py',f'''import sys
from importlib import import_module
sys.path.insert(0,{str(project.root)!r})
class Driver:
    def __init__(self): self.value=0
    def run(self): self.value=int(import_module('dependency.signal').VALUE)
''')
    path=project.flow('lazy_import',f'''from flowguard.flow import Model
from flowguard.flow.adapter import fields
m=Model('lazy import',covers=['consumer/driver.py:Driver'])
m.field('value',(0,1),0)
@m.action()
def run(s): s['value']=1
m.bind_adapter({{'root':{str(project.root/'consumer')!r},'system':'driver:Driver','classes':['driver:Driver']}},
               state=lambda snapshot:fields(snapshot,names=('value',)),operations={{'run':'run'}})
MODEL=m
''')
    part=core_part(PartContext(project.root,PartSpec('core','lazy_import'),path,cache_dir(project.root)))
    assert part.complete and part.info['native']['status']=='conformant'
    directories=[(name,stamp) for footprint in part.info['native']['footprints']
                 for name,stamp in footprint['files'].items() if stamp.get('directory') and Path(name).is_relative_to(project.root)]
    assert directories
    assert all((project.root/name).is_file() or (project.root/name).is_symlink() for name in part.reads)
    name,stamp=next((name,stamp) for name,stamp in directories if Path(name)==project.root/'dependency')
    evidence={'reusable':True,'files':{name:stamp},'directories':{}}
    assert footprint_evidence(evidence).status=='current'
    directory=Path(name)
    directory.rename(directory.with_name('moved-dependency'))
    directory.write_text('directory replaced by an actual file')
    assert footprint_evidence(evidence).status=='stale'
