"""Actual file reads are evidence; SQLite never opens a non-owned database."""
import base64
import sqlite3
import pytest
from flowguard.native import session


def spec(tmp_path):
    (tmp_path/'program.py').write_text('''import json,sqlite3
from pathlib import Path
class Program:
    def read_json(self,path): return json.loads(Path(path).read_text())
    def read_db(self,path):
        db=sqlite3.connect(path)
        try: return db.execute('select value from data').fetchone()[0]
        finally: db.close()
    def uri(self,path): return sqlite3.connect(path,uri=True)
''')
    return dict(root=str(tmp_path),system='program:Program',classes=['program:Program'])


def test_json_and_sqlite_actual_owned_reads_keep_source_provenance(tmp_path):
    selected=spec(tmp_path)
    database=tmp_path/'input.sqlite'
    with sqlite3.connect(database) as connection:
        connection.execute('create table data(value integer)')
        connection.execute('insert into data values(7)')
    start={'files':{name:base64.b64encode(raw).decode() for name,raw in
                    [('input.json',b'{"value":7}'),('input.sqlite',database.read_bytes())]}}
    result=session.replay(selected,[dict(name='read_json',args=[{'$file':'input.json'}]),
                                    dict(name='read_db',args=[{'$file':'input.sqlite'}])],start)
    assert all(step['outcome']=='success' for step in result['steps'])
    reads=result['footprint']['world_reads']
    assert any(row['path']=='input.json' and row['event']=='open' for row in reads)
    assert any(row['path']=='input.sqlite' and row['event']=='sqlite3.connect' for row in reads)
    assert all(row['source']['path']=='program.py' for row in reads)


def test_non_owned_sqlite_inputs_and_uri_aliases_remain_explicit_unknown(tmp_path):
    selected=spec(tmp_path)
    outside=tmp_path/'outside.sqlite'
    with sqlite3.connect(outside) as connection:
        connection.execute('create table data(value integer)')
    original=outside.read_bytes()
    with pytest.raises(session.UnsupportedWorld,match='outside the disposable world'):
        session.replay(selected,[dict(name='read_db',args=[str(outside)])])
    with pytest.raises(session.UnsupportedWorld,match='SQLite URI'):
        session.replay(selected,[dict(name='uri',args=['file:'+str(outside)])])
    assert outside.read_bytes()==original
