"""Legacy console encoding changes display only, never a rendered report or data."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.intent import differences as D
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


def run_public_entry(root, mode):
    """One real top-level session, including the complete public check path."""
    bootstrap = '''import io,sys
from contextlib import redirect_stdout
sdk,root,mode=sys.argv[1:]
sys.path.insert(0,sdk)
from flowguard.intent import cli
buffer=io.BytesIO()
stream=io.TextIOWrapper(buffer,encoding='cp1252',newline='')
with redirect_stdout(stream):
    if mode=='pytest':
        import pytest
        status=int(pytest.main(['-q','-p','flowguard.intent.plugin','tests']))
    else:
        status=cli.main(['--root',root,'check','--all'])
    print('AFTER_GRACE_DISPLAY')
stream.flush()
assert stream.encoding=='cp1252' and stream.errors=='strict'
sys.stdout.buffer.write(buffer.getvalue())
stream.detach()
raise SystemExit(status)
'''
    return subprocess.run([sys.executable,'-c',bootstrap,str(Path(__file__).resolve().parents[2]),str(root),mode],
                          cwd=root,capture_output=True,timeout=60)


def test_real_comparison_displays_survive_cp1252_and_keep_unicode_data(tmp_path):
    root=tmp_path/'project'
    other=SOURCE.replace('def accept(', 'def other(').replace('<= 3','<= 7')
    project(root,SOURCE+'\n'+other,'',
            'from app import accept, other\ndef test_actual():\n    assert accept(0) is other(0) is True\n')
    for name in ('pytest','check'):
        result=run_public_entry(root,name)
        shown=result.stdout.decode('cp1252')
        (tmp_path/(name+'.stdout.txt')).write_text(shown,encoding='utf-8')
        assert result.returncode==1,(name,result.returncode,shown,result.stderr)
        assert 'GRACE'in shown and 'AFTER_GRACE_DISPLAY'in shown,(name,shown)
        # The 4.3 block of pytest and check reports the actual same-name contradiction: what each copy answered on
        # the input; check's red is pytest's own.
        assert 'red: same GRACE: on ' in shown and ' returns ' in shown,(name,shown)
        assert [line for line in shown.splitlines() if line.startswith('red: ')] == [
            'red: same GRACE: on days=7: app.py:accept returns False, app.py:other returns True '
            '-> decide which copy is right, then make the other agree'],(name,shown)
        assert 'UnicodeEncodeError'not in shown,(name,shown)
    # Retain literals and a final LF, including a backslash that looks like an
    # escape and non-LF separators. The fallback must be reversible display.
    rendered='same GRACE: on days=7 \u2192 the copies differ (\u6700\u591a\u4e09\u5929)'
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
    class BrokenWrite:
        encoding='cp1252'
        def write(self,text):raise OSError('existing write failure')
    with pytest.raises(OSError,match='existing write failure'):
        D.display(rendered,file=BrokenWrite())
