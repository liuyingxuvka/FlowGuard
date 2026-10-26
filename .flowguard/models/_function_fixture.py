"""Small git projects for native function/test selection; no cached verdicts."""
from pathlib import Path
import json
import shutil
import subprocess
from flowguard.map.inventory import build_inventory
from flowguard.map.impact import compute_impact
from flowguard.map.common import DEFAULT_IGNORE

def write(root,path,text):
    destination=root/path; destination.parent.mkdir(parents=True,exist_ok=True); destination.write_text(text)

def fixture(root):
    write(root,'core.py','VALUE=1\ndef helper(): return 1\ndef own(): return helper()+VALUE\ndef other(): return 2\ndef compose(): return own()\n')
    write(root,'api.py','from core import VALUE as LIMIT\ndef call(): return LIMIT\n')
    write(root,'tests/test_core.py','from core import own,other\ndef test_bound(): assert own()\ndef test_call(): assert own()\ndef helper(): return own()\ndef test_help(): assert helper()\ndef test_indirect(): assert other()\ndef test_other(): assert other()\ndef test_noop(): pass\ndef test_last(): pass\n')
    for mid,anchor,parent in (('child','own','parent'),('parent','compose','logic'),('other','other','logic'),('importer','call','api')):
        write(root,'.flowguard/models/'+mid+'.py',f'MODEL_ID={mid!r}\nPARENT={parent!r}\nIMPLEMENTED_BY={{"Run":{("api.py:" if mid=="importer" else "core.py:")+anchor!r}}}\nTESTED_BY='+ ('{"safe":["tests/test_core.py:test_bound"]}' if mid=='child' else '{}')+'\ndef build_explorer(): pass\n')
    components=[dict(id=cid,layer='code',summary=cid,responsibilities=[cid],files=files,tests=['tests/test_core.py'] if cid=='logic' else [],depends_on=['logic'] if cid=='api' else [],models=[],status='draft') for cid,files in (('logic',['core.py']),('api',['api.py']))]
    data=dict(schema='flowguard.map.v1',project='function-selection',layers=['code'],components=components)
    write(root,'.flowguard/map.json',json.dumps(data))
    for args in (('init','-q'),('add','.'),('-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','baseline')):
        subprocess.run(['git',*args],cwd=root,check=True,capture_output=True)
    return data

def native_case(root,case):
    data=fixture(root)
    text=(root/'core.py').read_text()
    replacement={'body':('return helper()+VALUE','return helper()+VALUE+1'),'binding':('VALUE=1','VALUE=2'),'removed':('def other(): return 2\n',''),'helper':('def helper(): return 1','def helper(): return 3')}
    if case=='no_git':
        from flowguard.map.cli import main
        from contextlib import redirect_stdout
        from io import StringIO
        with redirect_stdout(StringIO()): assert main(['confirm','all','--root',str(root)])==0
        data=json.loads((root/'.flowguard/map.json').read_text())
        shutil.rmtree(root/'.git')
        text=text.replace('return helper()+VALUE','return helper()+VALUE+1')
        (root/'core.py').write_text(text)
        from flowguard.map.impact import changed_files
        changed=changed_files(root,'HEAD')
    else:
        before,after=replacement[case]
        (root/'core.py').write_text(text.replace(before,after))
        changed=['core.py']
    inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False)
    return compute_impact(root,data,inv,changed,base='HEAD')
