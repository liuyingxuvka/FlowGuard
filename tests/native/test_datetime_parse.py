"""Parsing explicit values is pure; clock reads keep their explicit world boundary."""
import pytest
from flowguard.native import session


def program(tmp_path, body):
    (tmp_path/'program.py').write_text(f'''from datetime import datetime,date,time
class Program:
    def __init__(self): self.seconds=0
    def run(self):
        {body}
''')
    return {'root':str(tmp_path),'system':'program:Program','classes':['program:Program']}


def test_actual_iso_datetime_metadata_parsing_and_offset_arithmetic(tmp_path):
    spec=program(tmp_path,"moment=datetime.fromisoformat('2026-11-04T12:00:00+02:00')\n        self.seconds=int(moment.utcoffset().total_seconds())\n        return self.seconds")
    result=session.replay(spec,[{'name':'run'}])
    assert result['steps'][0]['outcome']=='success'
    assert result['steps'][0]['value']['root']==7200


@pytest.mark.parametrize('kind,value,expected', [('date','2026-11-04','2026-11-04'),('time','12:03:04','12:03:04')])
def test_explicit_date_and_time_parsing(tmp_path,kind,value,expected):
    result=session.replay(program(tmp_path,f"return {kind}.fromisoformat({value!r}).isoformat()"),[{'name':'run'}])
    assert result['steps'][0]['value']['root']==expected


def test_invalid_parse_is_an_actual_sut_value_error(tmp_path):
    result=session.replay(program(tmp_path,"return datetime.fromisoformat('invalid')"),[{'name':'run'}])
    assert result['steps'][0]['outcome']=='crash'
    assert result['steps'][0]['exception']['type']=='builtins:ValueError'


@pytest.mark.parametrize('body', ['return datetime.now()', 'return date.today()', "__import__('time').sleep(0)"])
def test_actual_clocks_and_waits_remain_unsupported(tmp_path,body):
    with pytest.raises(session.UnsupportedWorld,match='nondeterministic resource'):
        session.replay(program(tmp_path,body),[{'name':'run'}])
