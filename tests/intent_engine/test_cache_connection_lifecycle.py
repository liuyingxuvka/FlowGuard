"""Cache readers release their actual SQLite connections before returning."""
from contextlib import closing
import json
import sqlite3
from types import SimpleNamespace

import pytest

from flowguard.intent import cache, plugin
from flowguard.intent.config import load_config


def capture_connections(monkeypatch):
    connect, opened = sqlite3.connect, []

    def retain(*args, **kwargs):
        connection = connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, 'connect', retain)
    return opened


def assert_closed(opened):
    assert len(opened) == 1
    try:
        with pytest.raises(sqlite3.ProgrammingError, match='closed'):
            opened[0].execute('SELECT 1')
    finally:
        opened[0].close()


@pytest.mark.parametrize('malformed', [False, True])
def test_cache_read_closes_real_connection_on_return_and_decode_error(tmp_path, monkeypatch, malformed):
    cfg = load_config(tmp_path)
    cfg.cache.mkdir(parents=True)
    with closing(sqlite3.connect(cfg.cache / 'map.sqlite')) as connection, connection:
        connection.execute('CREATE TABLE meta(k TEXT, v TEXT)')
        connection.execute('INSERT INTO meta VALUES (?, ?)',
                           ('intent_attempt', '{' if malformed else json.dumps({'sentinel': 'ok'})))
    opened = capture_connections(monkeypatch)
    if malformed:
        with pytest.raises(json.JSONDecodeError):
            cache.read(cfg)
    else:
        assert cache.read(cfg)['attempt'] == {'sentinel': 'ok'}
    assert_closed(opened)


@pytest.mark.parametrize('malformed', [False, True])
def test_deferred_read_closes_real_connection_on_return_and_query_error(tmp_path, monkeypatch, malformed):
    cfg = load_config(tmp_path)
    cfg.cache.mkdir(parents=True)
    with closing(sqlite3.connect(cfg.cache / 'map.sqlite')) as connection, connection:
        connection.execute('CREATE TABLE result(other TEXT)' if malformed else 'CREATE TABLE result(item TEXT)')
        connection.execute('INSERT INTO result VALUES (?)', ('kept',))
    opened = capture_connections(monkeypatch)
    state = SimpleNamespace(cfg=cfg, collected={'kept', 'missing'}, selected=set(), deferred={'kept', 'missing'})
    if malformed:
        with pytest.raises(sqlite3.OperationalError, match='no such column: item'):
            plugin._missing(state, {'kept', 'missing'})
    else:
        assert plugin._missing(state, {'kept', 'missing'}) == ['missing']
    assert_closed(opened)
