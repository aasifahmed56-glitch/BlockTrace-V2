"""
Tests for per-visitor workspace isolation: header/query parsing, graph scoping in
Neo4j, saved cases on disk, and namespaced on-chain case keys.

Graph tests write only to throwaway workspaces and clear them afterwards, so the
"default" workspace (pre-existing data) is never touched.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

import api
import blockchain_service
import case_manager
import workspace


def _ws():
    return f"test-{uuid.uuid4()}"


def _addr(n):
    return "0x" + f"{n:040x}"


@pytest.fixture
def client():
    api.PUBLIC_MODE = False
    return TestClient(api.app)


@pytest.fixture
def two_workspaces():
    a, b = _ws(), _ws()
    yield a, b
    for ws in (a, b):
        token = workspace._current.set(ws)
        try:
            api.clear_graph()
        finally:
            workspace._current.reset(token)


# ============================================================
# 1. Workspace ID parsing
# ============================================================

class TestNormalize:
    def test_valid_id_is_lowercased(self):
        assert workspace.normalize("ABCDEF12-3456") == "abcdef12-3456"

    @pytest.mark.parametrize("raw", [None, "", "short", "../../etc/passwd", "a" * 65, "has space 1234"])
    def test_invalid_ids_fall_back_to_default(self, raw):
        assert workspace.normalize(raw) == workspace.DEFAULT_WORKSPACE

    def test_default_outside_requests(self):
        assert workspace.current() == workspace.DEFAULT_WORKSPACE


# ============================================================
# 2. Graph isolation (Neo4j)
# ============================================================

class TestGraphIsolation:
    def _load(self, client, ws, edges):
        # /cases/{name}/load needs a saved case, so load edges directly in the workspace
        token = workspace._current.set(ws)
        try:
            api.load_case_edges(edges)
        finally:
            workspace._current.reset(token)

    def test_workspaces_see_only_their_own_graph(self, client, two_workspaces):
        a, b = two_workspaces
        self._load(client, a, [{"from": _addr(1), "to": _addr(2), "value": 1.5}])
        self._load(client, b, [{"from": _addr(3), "to": _addr(4), "value": 2.0},
                               {"from": _addr(4), "to": _addr(5), "value": 0.5}])

        graph_a = client.get("/graph", headers={"X-Workspace-Id": a}).json()
        graph_b = client.get("/graph", headers={"X-Workspace-Id": b}).json()
        addrs_a = {e["from"] for e in graph_a["edges"]} | {e["to"] for e in graph_a["edges"]}
        addrs_b = {e["from"] for e in graph_b["edges"]} | {e["to"] for e in graph_b["edges"]}
        assert addrs_a == {_addr(1), _addr(2)}
        assert addrs_b == {_addr(3), _addr(4), _addr(5)}

        summary_b = client.get("/summary", headers={"X-Workspace-Id": b}).json()
        assert summary_b["wallets_traced"] == 3
        assert summary_b["transactions_mapped"] == 2

    def test_same_wallet_in_two_workspaces_stays_separate(self, client, two_workspaces):
        a, b = two_workspaces
        shared = _addr(9)
        self._load(client, a, [{"from": shared, "to": _addr(10), "value": 1.0}])
        self._load(client, b, [{"from": shared, "to": _addr(11), "value": 1.0}])
        edges_a = client.get("/graph", headers={"X-Workspace-Id": a}).json()["edges"]
        assert [e["to"] for e in edges_a] == [_addr(10)]

    def test_clear_only_affects_own_workspace(self, client, two_workspaces):
        a, b = two_workspaces
        self._load(client, a, [{"from": _addr(1), "to": _addr(2), "value": 1.0}])
        self._load(client, b, [{"from": _addr(3), "to": _addr(4), "value": 1.0}])

        assert client.post("/clear", headers={"X-Workspace-Id": a}).status_code == 200
        assert client.get("/graph", headers={"X-Workspace-Id": a}).json()["edges"] == []
        assert len(client.get("/graph", headers={"X-Workspace-Id": b}).json()["edges"]) == 1


# ============================================================
# 3. Saved cases on disk
# ============================================================

class TestCaseIsolation:
    def test_cases_are_per_workspace(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("case_manager.CASES_DIR", str(tmp_path))
        a, b = _ws(), _ws()
        for ws, name in ((a, "alpha"), (b, "beta")):
            token = workspace._current.set(ws)
            try:
                case_manager.save_case(name, _addr(1), [{"from": _addr(1), "to": _addr(2), "value": 1.0}],
                                       case_number="BT-2026-0001")
            finally:
                workspace._current.reset(token)

        names_a = [c["name"] for c in client.get("/cases", headers={"X-Workspace-Id": a}).json()["cases"]]
        names_b = [c["name"] for c in client.get("/cases", headers={"X-Workspace-Id": b}).json()["cases"]]
        assert names_a == ["alpha"]
        assert names_b == ["beta"]  # same case number allowed in another workspace

        assert client.delete("/cases/alpha", headers={"X-Workspace-Id": b}).status_code == 404
        assert client.delete("/cases/alpha", headers={"X-Workspace-Id": a}).status_code == 200

    def test_legacy_cases_move_to_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr("case_manager.CASES_DIR", str(tmp_path))
        (tmp_path / "old case.json").write_text("{}", encoding="utf-8")
        case_manager.migrate_legacy_cases()
        assert not (tmp_path / "old case.json").exists()
        assert (tmp_path / workspace.DEFAULT_WORKSPACE / "old case.json").exists()


# ============================================================
# 4. On-chain case key
# ============================================================

class TestOnchainKey:
    def test_default_workspace_keeps_plain_key(self):
        from web3 import Web3
        assert blockchain_service.case_number_to_hash("BT-2026-0001") == Web3.keccak(text="BT-2026-0001")

    def test_other_workspaces_are_namespaced(self):
        ws = _ws()
        token = workspace._current.set(ws)
        try:
            key = blockchain_service.case_number_to_hash("BT-2026-0001")
        finally:
            workspace._current.reset(token)
        assert key != blockchain_service.case_number_to_hash("BT-2026-0001")


# ============================================================
# 5. Query-string fallback (PDF download link)
# ============================================================

def test_query_param_selects_workspace(client, two_workspaces):
    a, _ = two_workspaces
    token = workspace._current.set(a)
    try:
        api.load_case_edges([{"from": _addr(1), "to": _addr(2), "value": 1.0}])
    finally:
        workspace._current.reset(token)
    assert client.get(f"/summary?ws={a}").json()["wallets_traced"] == 2
