"""Legacy console encoding changes display only, never a rendered report or data."""
from contextlib import redirect_stdout
import io
import json
import sys

import pytest

from flowguard.intent import cli, differences as D
from flowguard.intent.config import load_config
from tests.intent_engine.test_anchor_integration import project, SOURCE


def capture_bytes(encoding, action):
    buffer=io.BytesIO()
    stream=io.TextIOWrapper(buffer,encoding=encoding,newline='')
    original=sys.stdout
    try:
        with redirect_stdout(stream):
            status=action()
            print('AFTER_GRACE_DISPLAY')
        stream.flush()
        assert stream.encoding==encoding and stream.errors=='strict'
        return status,buffer.getvalue()
    finally:
        assert sys.stdout is original
        stream.detach()


def test_real_comparison_displays_survive_cp1252_and_keep_unicode_data(tmp_path):
    root=tmp_path/'project'
    other=SOURCE.replace('def accept(', 'def other(').replace('<= 3','<= 7')
    project(root,SOURCE+'\n'+other,'')
    cfg=load_config(root)
    report=D.agreements(root)
    assert report['status']=='red'and report['changed']==1
    rendered=D.render(report)
    assert 'GRACE'in rendered and '↔'in rendered and '→'in rendered and '共 3 类'in rendered
    original_json=json.dumps(report,ensure_ascii=False,sort_keys=True).encode('utf-8')
    callers=[('pytest',lambda:int(pytest.main(['-q','-p','flowguard.intent.plugin',str(root/'tests')]))),
             ('check_sources',lambda:int(cli._check_sources(cfg))),
             ('compare',lambda:cli.main(['--root',str(root),'compare','app:accept','app:other']))]
    for name,call in callers:
        status,raw=capture_bytes('cp1252',call)
        shown=raw.decode('cp1252')
        (tmp_path/(name+'.stdout.txt')).write_text(shown,encoding='utf-8')
        assert status==1,(name,status,shown)
        assert 'GRACE'in shown and 'AFTER_GRACE_DISPLAY'in shown,(name,shown)
        assert r'\u2194'in shown and r'\u2192'in shown,(name,shown)
        assert r'\u5171 3 \u7c7b'in shown,(name,shown)
        assert 'UnicodeEncodeError'not in shown,(name,shown)
    # Retain literals and a final LF, including a backslash that looks like an
    # escape and non-LF separators. The fallback must be reversible display.
    text=rendered+'\nliteral '+r'\u5171'+'\v\f\u2028\n'
    for encoding in ('cp1252','utf-8'):
        buffer=io.BytesIO();stream=io.TextIOWrapper(buffer,encoding=encoding,newline='')
        try:
            D.display(text,file=stream)
            stream.flush();raw=buffer.getvalue()
        finally:stream.detach()
        if encoding=='utf-8':
            assert raw==(text+'\n').encode('utf-8')
        else:
            shown=raw.decode('ascii')
            assert shown.endswith('\n')
            restored='\n'.join(line.encode('ascii').decode('unicode_escape')for line in shown[:-1].split('\n'))
            assert restored==text
    assert D.render(report)==rendered
    assert json.dumps(report,ensure_ascii=False,sort_keys=True).encode('utf-8')==original_json
    class BrokenWrite:
        encoding='cp1252'
        def write(self,text):raise OSError('existing write failure')
    with pytest.raises(OSError,match='existing write failure'):
        D.display(rendered,file=BrokenWrite())
