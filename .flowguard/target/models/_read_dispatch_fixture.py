"""Fresh read CLI fixtures and observable answers; never import project models."""
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
import json,sys
from pathlib import Path
from _target_fixture import make_port_project,write_json

def fixture(root):
    data=make_port_project(root)
    (root/'tests').mkdir(exist_ok=True)
    (root/'tests/test_loan.py').write_text('from shelf.loans import borrow\ndef test_borrow(): assert borrow("lend_request")=="lent"\n')
    data['components'][1]['tests']=['tests/test_loan.py']
    data['flows']=[dict(id='borrow',summary='request a loan',steps=['cli:main','loans:borrow'])]
    write_json(root/'.flowguard/map.json',data)
    for path in (root/'.flowguard/models').glob('*.py'):
        path.write_text(path.read_text()+"\nfrom pathlib import Path as _MarkerPath\n_MarkerPath(__file__).parents[2].joinpath('read_import.marker').write_text('imported')\n")
    return data

def call(root,*args):
    from flowguard.__main__ import main
    output=StringIO()
    with redirect_stdout(output),redirect_stderr(output):
        try: code=main(['read','--root',str(root),*args])
        except SystemExit as exc:code=exc.code
    return code,output.getvalue()

def imported(root):
    models=(root/'.flowguard/models').resolve()
    return (root/'read_import.marker').exists() or any(isinstance((file:=vars(module).get('__file__')),str) and Path(file).resolve().is_relative_to(models) for module in tuple(sys.modules.values()) if module is not None)

def answers(root,mode):
    if mode=='show':
        for args,value in (((), 'complete'),(('--budget','200'),'truncated')):
            code,text=call(root,*args)
            yield value,code==0 and ('truncated' in text if value=='truncated' else text.startswith('# ') and 'truncated' not in text),text
    elif mode=='component':
        for name,value,expected in (('loans','shown',0),('missing','unknown',1)):
            code,text=call(root,'--component',name)
            yield value,code==expected and ("no component" in text if value=='unknown' else '## loans' in text),text
    elif mode=='find':
        for word,value,expected in (('loans','owners',0),('zzzzzzzzzz','no_owner',1),('shelf/loans.py:borrow','location',0),('shelf/loans.py:missing','no_symbol',1),('tests/test_loan.py:test_borrow','test',0)):
            code,text=call(root,'--find',word)
            yield value,code==expected and bool(text),text
    elif mode=='review':
        code,text=call(root,'--review')
        yield 'ranked',code==0 and 'optimise next:' in text and 'optimise next: nothing to rank' not in text,text
        empty=root/'clean';(empty/'.flowguard').mkdir(parents=True)
        write_json(empty/'.flowguard/map.json',dict(schema='flowguard.map.v1',project='clean',layers=[],components=[],flows=[],accepted_debts=[]))
        code,text=call(empty,'--review')
        yield 'nothing_to_rank',code==0 and 'optimise next: nothing to rank' in text,text
    elif mode=='field':
        for word,value,expected in (('answer','listed',0),('missing_field','unknown',1)):
            code,text=call(root,'--field',word)
            yield value,code==expected and bool(text),text
    elif mode=='mermaid':
        for args,value,expected in (((),'drawn',0),(('--component','missing'),'unknown',1)):
            code,text=call(root,'--mermaid',*args)
            yield value,code==expected and (text.startswith('flowchart TD') if value=='drawn' else text.startswith('no component')),text
