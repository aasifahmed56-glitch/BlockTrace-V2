"""Tests for the Neo4j session wrapper that retries once on a dead connection."""

import pytest
from neo4j.exceptions import ServiceUnavailable, SessionExpired

import api


class _FakeSession:
    def __init__(self, fail_with=None):
        self.fail_with = fail_with
        self.closed = False
        self.calls = 0

    def run(self, query, *args, **params):
        self.calls += 1
        if self.fail_with:
            raise self.fail_with("connection is dead")
        return "result"

    def close(self):
        self.closed = True


class _FakeDriver:
    def __init__(self, sessions):
        self.sessions = list(sessions)
        self.opened = []

    def session(self, **kwargs):
        s = self.sessions.pop(0)
        self.opened.append(s)
        return s


@pytest.mark.parametrize("error", [ServiceUnavailable, SessionExpired])
def test_retries_once_on_fresh_session(monkeypatch, error):
    dead, fresh = _FakeSession(fail_with=error), _FakeSession()
    monkeypatch.setattr(api, "driver", _FakeDriver([dead, fresh]))
    with api.neo4j_session() as session:
        assert session.run("RETURN 1") == "result"
    assert dead.closed and fresh.closed
    assert fresh.calls == 1


def test_gives_up_after_second_failure(monkeypatch):
    monkeypatch.setattr(api, "driver", _FakeDriver([
        _FakeSession(fail_with=ServiceUnavailable), _FakeSession(fail_with=ServiceUnavailable)]))
    with pytest.raises(ServiceUnavailable):
        with api.neo4j_session() as session:
            session.run("RETURN 1")


def test_other_errors_are_not_retried(monkeypatch):
    driver = _FakeDriver([_FakeSession(fail_with=ValueError), _FakeSession()])
    monkeypatch.setattr(api, "driver", driver)
    with pytest.raises(ValueError):
        with api.neo4j_session() as session:
            session.run("RETURN 1")
    assert len(driver.opened) == 1
