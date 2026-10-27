"""Real model-file target-guard probes, retained when the temporary model rejoins the pointer."""
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
import json
from flowguard.map.facts import CodeFactsReport,Fact

def model_edit_cases():
    from flowguard.map.check import model_edit_findings
    from flowguard.map.cli import main as map_main
    from flowguard.map.target import main as target_main
    from flowguard.map.common import content_digest
    with TemporaryDirectory(prefix='fg-model-edit-') as directory:
        root=Path(directory);(root/'.flowguard/models').mkdir(parents=True)
        (root/'native.py').write_text('def run(): return True\n')
        logical='.flowguard/models/one.py';path=root/logical
        path.write_text('MODEL_ID="one"\nPARENT="app"\nIMPLEMENTED_BY={"Run":"native.py:run"}\nTESTED_BY={}\ndef build_explorer():pass\ndef conformance():pass\n')
        data=dict(schema='flowguard.map.v1',fingerprint_format=2,model_digests={logical:content_digest(path)},components=[dict(id='app',summary='Compute one value',responsibilities=['Compute value'],files=['native.py'],tests=[],models=[],status='draft')])
        (root/'.flowguard/map.json').write_text(json.dumps(data))
        facts=[]
        facts.append(Fact('unchanged',not model_edit_findings(root,data,'error')))
        path.write_text(path.read_text()+'# changed model\n')
        facts.append(Fact('changed',bool(model_edit_findings(root,data,'error'))))
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()):
            confirmed=map_main(['--root',str(root),'confirm','app'])
        data=json.loads((root/'.flowguard/map.json').read_text())
        facts.append(Fact('confirm_keeps_guard',confirmed==0 and bool(model_edit_findings(root,data,'error'))))
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()):
            started=target_main(['--root',str(root),'start','Plan model edit'])
            added=target_main(['--root',str(root),'add','one'])
        facts.append(Fact('target_owns_edit',started==added==0 and not model_edit_findings(root,data,'error')))
        return CodeFactsReport(tuple(facts))
