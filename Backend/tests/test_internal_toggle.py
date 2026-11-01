"""
"Include internal transfers": off by default (counts match Etherscan's Transactions
tab), on for curated bridge-exploit cases, recorded in the scope, and followed by the
graph, summary, Findings and PDF alike. Old saved cases count internal transfers as
they did before the option existed.

Etherscan is mocked; endpoint tests use the real Neo4j database in throwaway
workspaces that are cleared afterwards.
"""

import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

import api
import case_manager
import report_generator
import workspace
from logic import describe_data_quality, describe_scope
from test_data_accuracy import DAY, START, _fake_etherscan


# ---------- wording ----------

def test_scope_says_normal_transactions_only():
    scope = {"from_date": "2026-10-24", "to_date": "2026-10-30", "sort": "asc", "tx_per_wallet": 30,
             "hops": 1, "chain": "Ethereum", "include_internal": False}
    assert describe_scope(scope) == (
        "Transactions 2026-10-24 to 2026-10-30 · oldest first · up to 30 per wallet · 1 hop · Ethereum"
        " · normal transactions only"
    )


def test_scope_with_internal_transfers():
    scope = {"from_date": None, "to_date": None, "sort": "desc", "tx_per_wallet": 15, "hops": 2,
             "chain": "Ethereum", "include_internal": True}
    assert describe_scope(scope).endswith("· normal + internal transfers")


def test_data_quality_line():
    quality = {"normal_stored": 7, "normal_with_eth": 3, "internal_stored": 0, "internal_counted": False,
               "failed_skipped": 1, "show_zero_value": False, "capped_wallets": 0}
    assert describe_data_quality(quality) == "Normal 7 (3 with ETH, 4 zero-value hidden) · Internal off · Failed skipped 1"


def test_data_quality_line_with_internal_and_stored_but_off():
    on = {"normal_stored": 2, "normal_with_eth": 2, "internal_stored": 5, "internal_counted": True,
          "failed_skipped": 0, "capped_wallets": 3}
    assert describe_data_quality(on) == "Normal 2 (2 with ETH) · Internal 5 · Failed skipped 0 · Capped wallets 3"
    off = {**on, "internal_counted": False, "capped_wallets": 0}
    assert describe_data_quality(off) == "Normal 2 (2 with ETH) · Internal off (5 stored, not counted) · Failed skipped 0"


def test_request_default_is_off():
    assert api.ExpandRequest(wallet=START).include_internal is False
    assert api.PathRequest(source=START, destination=START).include_internal is False


# ---------- endpoints ----------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "PUBLIC_MODE", False)
    monkeypatch.setattr(api.time, "sleep", lambda s: None)
    calls = []

    def recording_get(url, params=None, timeout=None):
        calls.append(params.get("action"))
        return _fake_etherscan(url, params=params, timeout=timeout)

    monkeypatch.setattr(api.requests, "get", recording_get)
    ws = f"test-{uuid.uuid4()}"
    c = TestClient(api.app)
    c.headers.update({"X-Workspace-Id": ws})
    c.calls, c.ws = calls, ws
    try:
        yield c
    finally:
        c.post("/clear")


def _trace(client, include_internal=None):
    body = {"wallet": START, "hops": 1, "from_date": DAY, "to_date": DAY, "sort": "asc"}
    if include_internal is not None:
        body["include_internal"] = include_internal
    res = client.post("/expand", json=body)
    assert res.status_code == 200
    return res.json()


def _agree(client):
    """Graph, summary, Findings (hub) and the PDF queries report the same totals."""
    graph = client.get("/graph").json()
    summary = client.get("/summary").json()
    hubs = client.get("/detections/hub").json()["results"]
    assert graph["returned_edges"] == summary["transactions_mapped"] == summary["data_quality"]["transactions_shown"]
    assert sum(h["total_txs"] for h in hubs) == 2 * summary["transactions_mapped"]
    wallets = {e["from"] for e in graph["edges"]} | {e["to"] for e in graph["edges"]}
    assert summary["wallets_traced"] == len(wallets)

    # The PDF reads the trace scope from the API's memory; run its queries the same way.
    token = workspace._current.set(client.ws)
    try:
        with report_generator.driver.session(database=report_generator.NEO4J_DATABASE) as session:
            assert report_generator.get_summary_stats(session) == (summary["wallets_traced"], summary["transactions_mapped"])
    finally:
        workspace._current.reset(token)
    return graph, summary


def test_default_trace_skips_internal_transfers(client):
    body = _trace(client)
    assert "txlistinternal" not in client.calls
    assert body["scope"]["include_internal"] is False
    assert body["data_quality"]["internal_included"] == 0
    graph, summary = _agree(client)
    assert {e["kind"] for e in graph["edges"]} == {"normal"}
    q = summary["data_quality"]
    assert q["internal_counted"] is False and q["internal_stored"] == 0
    # h1, h2 and the contract creation h5 move ETH; h3 is a hidden 0-ETH call
    assert (q["normal_stored"], q["normal_with_eth"], q["transactions_shown"]) == (4, 3, 3)


def test_opted_in_trace_stores_internal_transfers(client):
    body = _trace(client, include_internal=True)
    assert "txlistinternal" in client.calls
    assert body["scope"]["include_internal"] is True
    graph, summary = _agree(client)
    assert {e["kind"] for e in graph["edges"]} == {"normal", "internal"}
    assert summary["data_quality"]["internal_counted"] is True
    assert summary["transactions_mapped"] == 4


def test_internal_transfers_from_an_earlier_trace_stop_counting(client):
    _trace(client, include_internal=True)
    _trace(client, include_internal=False)
    graph, summary = _agree(client)
    q = summary["data_quality"]
    assert q["internal_stored"] == 1 and q["internal_counted"] is False
    assert {e["kind"] for e in graph["edges"]} == {"normal"}
    assert "Internal off (1 stored, not counted)" in describe_data_quality(q)


def test_path_search_respects_the_option(client):
    res = client.post("/path", json={"source": START, "destination": "0x" + "99" * 20, "max_hops": 1,
                                     "from_date": DAY, "to_date": DAY})
    assert res.status_code == 200
    assert "txlistinternal" not in client.calls
    assert res.json()["scope"]["include_internal"] is False


def test_curated_cases_include_internal_transfers(client, monkeypatch):
    seen = {}

    def fake_expand(*args, **kwargs):
        seen.update(kwargs)
        return 1, []

    monkeypatch.setattr(api, "expand_from_wallet", fake_expand)
    cases = client.get("/curated-cases").json()["cases"]
    assert all(c["include_internal"] is True for c in cases)
    body = client.post("/curated-cases/Ronin Bridge Hack ($600M, 2022)/load").json()
    assert seen["include_internal"] is True
    assert body["scope"]["include_internal"] is True
    assert describe_scope(body["scope"]).endswith("normal + internal transfers")


def test_old_saved_case_counts_internal_transfers(client, tmp_path, monkeypatch):
    monkeypatch.setattr("case_manager.CASES_DIR", str(tmp_path))
    old_scope = {"from_date": DAY, "to_date": DAY, "sort": "asc", "tx_per_wallet": 15, "hops": 1, "chain": "Ethereum"}
    token = workspace._current.set(client.ws)
    try:
        saved = case_manager.save_case("Old scoped case", START, [(START, "0x" + "77" * 20, 1.0)],
                                       case_number="BT-2026-0201", scope=old_scope)
    finally:
        workspace._current.reset(token)
    path = os.path.join(str(tmp_path), client.ws, "Old scoped case.json")
    before = open(path, "rb").read()

    body = client.post("/cases/BT-2026-0201/load").json()
    assert body["scope"]["include_internal"] is True
    summary = client.get("/summary").json()
    assert summary["scope"]["include_internal"] is True
    assert summary["data_quality"]["internal_counted"] is True

    # The saved file — and so the anchored hash — is untouched.
    assert open(path, "rb").read() == before
    stored = json.loads(before)
    _, rehash = case_manager.build_case_snapshot(
        stored["case_number"], stored["name"], stored["start_wallet"], stored["edges"],
        stored["findings"], stored["saved_at"], scope=stored.get("scope"),
    )
    assert rehash == saved["case_data_hash"]


def test_failed_skipped_is_split_when_internal_ones_failed():
    from logic import describe_failed_skipped
    assert describe_failed_skipped({"failed_skipped": 2}) == "Failed skipped 2"
    assert describe_failed_skipped({"failed_skipped": 3, "failed_skipped_normal": 1,
                                    "failed_skipped_internal": 2}) == "Failed skipped 1 (normal) / 2 (internal)"
    # Without the per-kind normal count, it is derived from the total
    assert describe_failed_skipped({"failed_skipped": 3, "failed_skipped_internal": 1}) == "Failed skipped 2 (normal) / 1 (internal)"


def test_trace_stats_split_failed_by_kind():
    stats = api.TraceStats()
    stats.failed.update({"0xa", "0xb", "0xc:internal:0_1"})
    d = stats.as_dict()
    assert (d["failed_skipped"], d["failed_skipped_normal"], d["failed_skipped_internal"]) == (3, 2, 1)
