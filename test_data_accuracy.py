"""
Data-fetch accuracy: failed and 0-ETH transactions, internal transfers, duplicate
hashes, contract creations, inclusive UTC day windows, and one counting rule shared
by the graph, the summary, the Findings queries and the PDF dossier.

Etherscan is mocked. The endpoint tests use the real Neo4j database in a throwaway
workspace that is cleared afterwards.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import api
import graph_queries
import report_generator
import workspace

START = "0x" + "a1" * 20
PEER = "0x" + "b2" * 20
ZERO_ONLY = "0x" + "c3" * 20      # reached only through a 0-ETH contract call
CONTRACT = "0x" + "d4" * 20       # created by START
INTERNAL_PEER = "0x" + "e5" * 20  # paid by a contract through an internal transfer
FAILED_PEER = "0x" + "f6" * 20    # only in a failed transaction

DAY = "2022-03-23"
T0 = int(datetime(2022, 3, 23, tzinfo=timezone.utc).timestamp())  # 00:00:00 UTC
T_END = T0 + 86399                                                    # 23:59:59 UTC
ETH = 10**18


def tx(h, frm, to, value_eth, ts, **extra):
    row = {"hash": h, "from": frm, "to": to, "value": str(int(value_eth * ETH)), "timeStamp": str(ts),
           "isError": "0", "txreceipt_status": "1", "contractAddress": ""}
    row.update(extra)
    return row


NORMAL = [
    tx("0xh1", START, PEER, 2.0, T0),                        # 00:00:00 — first second of the day
    tx("0xh1", START, PEER, 2.0, T0),                        # duplicate row from Etherscan
    tx("0xh2", PEER, START, 0.5, T_END),                     # 23:59:59 — last second of the day
    tx("0xh3", START, ZERO_ONLY, 0, T0 + 100),               # 0-ETH contract call
    tx("0xh4", START, FAILED_PEER, 7.0, T0 + 200, isError="1", txreceipt_status="0"),
    tx("0xh5", START, "", 0.25, T0 + 300, contractAddress=CONTRACT),   # contract creation
    tx("0xh6", START, PEER, 9.0, T_END + 1),                 # next day 00:00:00 — outside the window
]
INTERNAL = [
    {"hash": "0xh7", "from": CONTRACT, "to": INTERNAL_PEER, "value": str(ETH), "timeStamp": str(T0 + 400),
     "traceId": "0_1", "isError": "0", "type": "call", "contractAddress": ""},
    {"hash": "0xh7", "from": CONTRACT, "to": INTERNAL_PEER, "value": str(ETH), "timeStamp": str(T0 + 400),
     "traceId": "0_1", "isError": "0", "type": "call", "contractAddress": ""},   # duplicate
]


# ---------- pure helpers ----------

def test_day_bounds_cover_whole_utc_days():
    assert api.day_bounds(DAY, DAY) == (T0, T_END)
    assert api.day_bounds(None, None) == (None, None)


def test_take_filters_and_normalises():
    stats = api.TraceStats()
    rows, hit = api._take(NORMAL, 15, "normal", False, *api.day_bounds(DAY, DAY), stats)
    assert [r["hash"] for r in rows] == ["0xh1", "0xh2", "0xh3", "0xh5"]
    assert hit is False
    assert stats.failed == {"0xh4"}
    creation = rows[-1]
    assert creation["to"] == CONTRACT


def test_take_includes_failed_when_asked():
    rows, _ = api._take(NORMAL, 15, "normal", True, None, None, None)
    failed = [r for r in rows if r["hash"] == "0xh4"]
    assert failed and failed[0]["failed"] is True


def test_take_window_boundaries():
    ts_from, ts_to = api.day_bounds(DAY, DAY)
    rows, _ = api._take(NORMAL, 15, "normal", False, ts_from, ts_to, None)
    stamps = {int(r["timeStamp"]) for r in rows}
    assert T0 in stamps and T_END in stamps
    assert T_END + 1 not in stamps


def test_take_cap_reports_more_available():
    rows, hit = api._take(NORMAL, 2, "normal", False, None, None, None)
    assert len(rows) == 2 and hit is True


def test_internal_rows_are_keyed_by_trace():
    rows, _ = api._take(INTERNAL, 15, "internal", False, None, None, None)
    assert len(rows) == 1
    assert rows[0]["edge_key"] == "0xh7:internal:0_1" and rows[0]["kind"] == "internal"


def test_date_to_block_uses_whole_day(monkeypatch):
    sent = []

    def fake_get(url, params=None, timeout=None):
        sent.append((params["timestamp"], params["closest"]))
        resp = MagicMock()
        resp.json.return_value = {"status": "1", "result": "100"}
        return resp

    monkeypatch.setattr(api.requests, "get", fake_get)
    api.date_to_block(DAY, "after")
    api.date_to_block(DAY, "before")
    assert sent == [(T0, "after"), (T_END, "before")]


def test_counting_rule_predicate():
    assert graph_queries.counted("r") == "(coalesce(r.kind, 'normal') IN $kinds AND ($show_zero OR r.value > 0))"
    assert graph_queries.COUNTED_KINDS == ["normal", "internal"]


# ---------- endpoints against the real graph ----------

def _fake_etherscan(url, params=None, timeout=None):
    resp = MagicMock()
    if params.get("module") == "block":
        resp.json.return_value = {"status": "1", "result": "14440000"}
    elif params.get("address", "").lower() != START:
        resp.json.return_value = {"status": "0", "message": "No transactions found", "result": []}
    elif params.get("action") == "txlistinternal":
        resp.json.return_value = {"status": "1", "result": INTERNAL}
    else:
        resp.json.return_value = {"status": "1", "result": NORMAL}
    return resp


@pytest.fixture
def traced(monkeypatch):
    monkeypatch.setattr(api, "PUBLIC_MODE", False)
    monkeypatch.setattr(api.requests, "get", _fake_etherscan)
    monkeypatch.setattr(api.time, "sleep", lambda s: None)
    ws = f"test-{uuid.uuid4()}"
    client = TestClient(api.app)
    client.headers.update({"X-Workspace-Id": ws})
    res = client.post("/expand", json={"wallet": START, "hops": 1, "tx_per_wallet": 15,
                                       "from_date": DAY, "to_date": DAY, "sort": "asc"})
    assert res.status_code == 200
    try:
        yield client, ws, res.json()
    finally:
        client.post("/clear")


def test_trace_reports_what_it_fetched_and_skipped(traced):
    _, _, body = traced
    q = body["data_quality"]
    # h1, h2, h3 (0 ETH), h5 (creation) and the internal transfer; h4 failed, h6 outside the day
    assert q["transactions_fetched"] == 5
    assert q["failed_skipped"] == 1
    assert q["internal_included"] == 1
    assert q["zero_value_fetched"] == 1
    assert q["zero_value_hidden"] == 1
    assert q["transactions_shown"] == 4
    assert q["capped_wallets"] == 0


def test_graph_summary_and_report_agree(traced):
    client, ws, _ = traced
    graph = client.get("/graph").json()
    summary = client.get("/summary").json()
    shown = summary["data_quality"]["transactions_shown"]
    assert graph["returned_edges"] == graph["total_edges"] == summary["transactions_mapped"] == shown == 4

    wallets = {e["from"] for e in graph["edges"]} | {e["to"] for e in graph["edges"]}
    assert summary["wallets_traced"] == len(wallets)
    assert ZERO_ONLY not in wallets and FAILED_PEER not in wallets
    assert {e["kind"] for e in graph["edges"]} == {"normal", "internal"}
    assert all(e["hash"] and e["timestamp"] for e in graph["edges"])
    stamps = [e["timestamp"] for e in graph["edges"]]
    assert stamps == sorted(stamps)

    token = workspace._current.set(ws)
    try:
        with report_generator.driver.session(database=report_generator.NEO4J_DATABASE) as session:
            assert report_generator.get_summary_stats(session) == (summary["wallets_traced"], summary["transactions_mapped"])
    finally:
        workspace._current.reset(token)


def test_hub_counts_follow_the_same_rule(traced):
    client, _, _ = traced
    hubs = {r["wallet"]: r["total_txs"] for r in client.get("/detections/hub").json()["results"]}
    # START: h1, h2, h5 (the 0-ETH call h3 is hidden)
    assert hubs[START] == 3


def test_show_zero_toggle_reveals_contract_calls(traced):
    client, _, _ = traced
    hidden = client.get("/summary").json()
    shown = client.get("/summary", headers={"X-Show-Zero-Value": "1"}).json()
    assert shown["transactions_mapped"] == hidden["transactions_mapped"] + 1
    assert shown["wallets_traced"] == hidden["wallets_traced"] + 1
    assert shown["data_quality"]["zero_value_hidden"] == 0
    graph = client.get("/graph", params={"show_zero": "1"}).json()
    assert any(e["to"] == ZERO_ONLY and e["value"] == 0 for e in graph["edges"])


def test_include_failed_stores_flagged_edge(monkeypatch):
    monkeypatch.setattr(api, "PUBLIC_MODE", False)
    monkeypatch.setattr(api.requests, "get", _fake_etherscan)
    monkeypatch.setattr(api.time, "sleep", lambda s: None)
    client = TestClient(api.app)
    client.headers.update({"X-Workspace-Id": f"test-{uuid.uuid4()}"})
    try:
        body = client.post("/expand", json={"wallet": START, "hops": 1, "from_date": DAY, "to_date": DAY,
                                             "include_failed": True}).json()
        assert body["data_quality"]["failed_skipped"] == 0
        edges = client.get("/graph").json()["edges"]
        assert [e["failed"] for e in edges if e["to"] == FAILED_PEER] == [True]
    finally:
        client.post("/clear")
