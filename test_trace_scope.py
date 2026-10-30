"""
Tests for trace scopes (date window, order, cap) and the transaction-cap warning:
request validation, the scope returned by /expand, /path and curated cases, the
scope saved with cases (without changing old case hashes) and the PDF dossier lines.

Etherscan and Neo4j are stubbed out, so these tests need no network or database.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import api
import case_manager
from logic import compute_certificate_hash, describe_cap, describe_scope, verify_certificate
from report_theme import build_header_band, build_report_styles

WALLET = "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"


# ---------- describe_scope / describe_cap ----------

def test_describe_scope_with_window():
    scope = {"from_date": "2022-03-23", "to_date": "2022-03-30", "sort": "asc",
             "tx_per_wallet": 15, "hops": 2, "chain": "Ethereum"}
    assert describe_scope(scope) == (
        "Transactions 2022-03-23 to 2022-03-30 · oldest first · up to 15 per wallet · 2 hops · Ethereum"
        " · normal + internal transfers"
    )


def test_describe_scope_without_dates():
    scope = {"from_date": None, "to_date": None, "sort": "desc", "tx_per_wallet": 15, "hops": 2, "chain": "Ethereum"}
    assert describe_scope(scope) == "All dates (newest 15 per wallet) · 2 hops · Ethereum · normal + internal transfers"


def test_describe_scope_open_ended_and_incident():
    scope = {"from_date": "2022-02-02", "to_date": None, "sort": "desc", "tx_per_wallet": 10,
             "hops": 1, "chain": "Polygon", "incident_date": "2022-02-02"}
    assert describe_scope(scope) == (
        "Transactions 2022-02-02 to today · newest first · up to 10 per wallet · 1 hop · Polygon · incident 2022-02-02"
        " · normal + internal transfers"
    )


def test_describe_scope_none():
    assert describe_scope(None) is None


def test_describe_cap():
    assert describe_cap([]) is None
    assert describe_cap(["0xa", "0xb"]) == "Cap reached for 2 wallets; results are a sample, not the full history."


# ---------- request validation ----------

def test_trace_window_blank_dates_become_none():
    req = api.ExpandRequest(wallet=WALLET, from_date="", to_date="  ")
    assert req.from_date is None and req.to_date is None


@pytest.mark.parametrize("bad", ["2022/03/23", "23-03-2022", "yesterday", "2022-13-01"])
def test_trace_window_rejects_malformed_dates(bad):
    with pytest.raises(ValidationError):
        api.ExpandRequest(wallet=WALLET, from_date=bad)


def test_trace_window_rejects_reversed_range():
    with pytest.raises(ValidationError):
        api.PathRequest(source=WALLET, destination=WALLET, from_date="2022-04-01", to_date="2022-03-01")


def test_normalize_sort():
    assert api.normalize_sort("asc") == "asc"
    assert api.normalize_sort("Oldest first") == "asc"
    assert api.normalize_sort(None) == "desc"
    assert api.normalize_sort("anything") == "desc"


# ---------- endpoints (Etherscan + Neo4j stubbed) ----------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "PUBLIC_MODE", False)
    monkeypatch.setattr(api, "_LAST_TRACE", {})
    blocks = []

    def fake_date_to_block(date_input, closest="after", chainid=1):
        blocks.append((date_input, closest, chainid))
        return 1000 if closest == "after" else 2000

    monkeypatch.setattr(api, "date_to_block", fake_date_to_block)
    monkeypatch.setattr(api, "get_data_window_stats", lambda: {
        "data_window": None, "earliest_timestamp": None, "latest_timestamp": None,
        "first_date": None, "last_date": None,
    })
    monkeypatch.setattr(api, "get_summary_stats", lambda: (3, 2))
    monkeypatch.setattr(api, "get_graph_quality", lambda: {
        "edges_stored": 2, "transactions_shown": 2, "zero_value_edges": 0, "zero_value_hidden": 0,
        "internal_shown": 0, "failed_included": 0, "show_zero_value": False,
    })
    c = TestClient(api.app)
    c.blocks = blocks
    return c


def test_expand_returns_and_remembers_scope(client, monkeypatch):
    calls = {}

    def fake_expand(start, hops, tx_per_wallet, chainid, startblock, endblock, sort, **kwargs):
        calls.update(startblock=startblock, endblock=endblock, sort=sort, tx=tx_per_wallet)
        return 4, ["0xaaa", "0xbbb"]

    monkeypatch.setattr(api, "expand_from_wallet", fake_expand)
    res = client.post("/expand", json={
        "wallet": WALLET, "hops": 2, "tx_per_wallet": 20, "chain": "Ethereum",
        "from_date": "2022-03-23", "to_date": "2022-03-30", "sort": "asc",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["scope"] == {"from_date": "2022-03-23", "to_date": "2022-03-30", "sort": "asc",
                             "tx_per_wallet": 20, "hops": 2, "chain": "Ethereum", "include_internal": False}
    assert body["hit_limit"] is True
    assert body["limited_wallets"] == ["0xaaa", "0xbbb"]
    assert body["limit_note"] == "Showing 20 of the wallet's transactions"
    assert calls == {"startblock": 1000, "endblock": 2000, "sort": "asc", "tx": 20}

    summary = client.get("/summary").json()
    assert summary["scope"] == body["scope"]
    assert summary["limited_wallets"] == ["0xaaa", "0xbbb"]


def test_expand_without_dates_keeps_old_behaviour(client, monkeypatch):
    calls = {}

    def fake_expand(start, hops, tx_per_wallet, chainid, startblock, endblock, sort, **kwargs):
        calls.update(startblock=startblock, endblock=endblock, sort=sort)
        return 1, []

    monkeypatch.setattr(api, "expand_from_wallet", fake_expand)
    body = client.post("/expand", json={"wallet": WALLET}).json()
    assert calls == {"startblock": 0, "endblock": 99999999, "sort": "desc"}
    assert client.blocks == []
    assert body["scope"]["from_date"] is None and body["scope"]["to_date"] is None
    assert body["hit_limit"] is False and body["limit_note"] is None


def test_expand_rejects_bad_date_with_422(client):
    res = client.post("/expand", json={"wallet": WALLET, "from_date": "not-a-date"})
    assert res.status_code == 422


def test_path_returns_scope_and_uses_its_tx_cap(client, monkeypatch):
    seen = {}

    def fake_until_found(source, destination, max_hops, tx_per_wallet, chainid, startblock, endblock, sort, **kwargs):
        seen.update(tx=tx_per_wallet, sort=sort, startblock=startblock)
        return 5, False, ["0xccc"]

    monkeypatch.setattr(api, "expand_until_found", fake_until_found)
    body = client.post("/path", json={
        "source": WALLET, "destination": "0x" + "1" * 40, "max_hops": 3,
        "tx_per_wallet": 25, "from_date": "2021-08-10", "sort": "asc",
    }).json()
    assert seen == {"tx": 25, "sort": "asc", "startblock": 1000}
    assert body["found"] is False
    assert body["scope"]["hops"] == 3 and body["scope"]["tx_per_wallet"] == 25
    assert body["limited_wallets"] == ["0xccc"]
    assert body["limit_note"] == "Showing 25 of the wallet's transactions"


def test_curated_cases_list_incident_windows(client):
    cases = {c["name"]: c for c in client.get("/curated-cases").json()["cases"]}
    ronin = cases["Ronin Bridge Hack ($600M, 2022)"]
    assert (ronin["from_date"], ronin["to_date"], ronin["sort"]) == ("2022-03-23", "2022-04-30", "asc")
    assert ronin["incident_date"] == "2022-03-23" and ronin["date_note"]
    poly = cases["Poly Network Hack ($611M, 2021)"]
    assert (poly["from_date"], poly["to_date"]) == ("2021-08-10", "2021-08-31")
    worm = cases["Wormhole Bridge Hack ($321M, 2022)"]
    assert (worm["from_date"], worm["to_date"]) == ("2022-02-02", "2022-02-09")


def test_curated_load_traces_incident_window(client, monkeypatch):
    calls = {}

    def fake_expand(start, hops, tx_per_wallet, chainid, startblock, endblock, sort, **kwargs):
        calls.update(start=start, startblock=startblock, endblock=endblock, sort=sort, tx=tx_per_wallet)
        return 7, ["0xddd"]

    monkeypatch.setattr(api, "expand_from_wallet", fake_expand)
    body = client.post("/curated-cases/Wormhole Bridge Hack ($321M, 2022)/load").json()
    assert ("2022-02-02", "after", 1) in client.blocks and ("2022-02-09", "before", 1) in client.blocks
    assert calls["sort"] == "asc" and calls["startblock"] == 1000 and calls["endblock"] == 2000
    scope = body["scope"]
    assert (scope["from_date"], scope["to_date"], scope["sort"]) == ("2022-02-02", "2022-02-09", "asc")
    assert scope["incident_date"] == "2022-02-02" and scope["chain"] == "Ethereum"
    assert body["limit_note"] == f"Showing {calls['tx']} of the wallet's transactions"


def test_clear_forgets_scope(client, monkeypatch):
    monkeypatch.setattr(api, "expand_from_wallet", lambda *a, **k: (1, ["0xeee"]))
    monkeypatch.setattr(api, "clear_graph", lambda: None)
    client.post("/expand", json={"wallet": WALLET})
    client.post("/clear")
    summary = client.get("/summary").json()
    assert summary["scope"] is None and summary["limited_wallets"] == []


def test_expand_visits_each_wallet_once_regardless_of_case(monkeypatch):
    """Etherscan returns lowercase addresses; a checksummed start wallet must not be
    fetched (and reported as capped) a second time in lowercase."""
    import contextlib

    fetched = []

    def fake_fetch(wallet, **kwargs):
        fetched.append(wallet)
        return [], True

    monkeypatch.setattr(api, "neo4j_session", lambda: contextlib.nullcontext())
    monkeypatch.setattr(api, "fetch_wallet_activity", fake_fetch)
    monkeypatch.setattr(api, "load_transactions", lambda session, txs, stats=None: {WALLET.lower(), "0x" + "2" * 40})
    monkeypatch.setattr(api.time, "sleep", lambda s: None)

    visited, limited = api.expand_from_wallet(WALLET, hops=2)
    assert [w.lower() for w in fetched] == [WALLET.lower(), "0x" + "2" * 40]
    assert visited == 2
    assert len(limited) == 2


# ---------- cases: scope saved without changing old hashes ----------

EDGES = [("0xA", "0xB", 1.5), ("0xB", "0xC", 0.25)]
SCOPE = {"from_date": "2022-03-23", "to_date": "2022-04-30", "sort": "asc",
         "tx_per_wallet": 15, "hops": 2, "chain": "Ethereum"}


def test_snapshot_hash_unchanged_without_scope():
    _, legacy_hash = case_manager.build_case_snapshot("BT-2026-0001", "c", WALLET, EDGES, {}, "2026-01-01T00:00:00")
    snap, none_hash = case_manager.build_case_snapshot("BT-2026-0001", "c", WALLET, EDGES, {}, "2026-01-01T00:00:00",
                                                       scope=None)
    assert none_hash == legacy_hash
    assert "scope" not in snap


def test_snapshot_includes_scope_when_present():
    _, legacy_hash = case_manager.build_case_snapshot("BT-2026-0001", "c", WALLET, EDGES, {}, "2026-01-01T00:00:00")
    snap, scoped_hash = case_manager.build_case_snapshot("BT-2026-0001", "c", WALLET, EDGES, {}, "2026-01-01T00:00:00",
                                                         scope=SCOPE)
    assert snap["scope"] == SCOPE
    assert scoped_hash != legacy_hash


def test_saved_case_keeps_scope(tmp_path, monkeypatch):
    monkeypatch.setattr("case_manager.CASES_DIR", str(tmp_path))
    saved = case_manager.save_case("Scoped case", WALLET, EDGES, case_number="BT-2026-0101", scope=SCOPE)
    listed = {c["case_number"]: c for c in case_manager.list_cases()}
    assert listed["BT-2026-0101"]["scope"] == SCOPE
    loaded = case_manager.load_case("BT-2026-0101")
    assert loaded["scope"] == SCOPE
    _, rehash = case_manager.build_case_snapshot(
        loaded["case_number"], loaded["name"], loaded["start_wallet"], loaded["edges"],
        loaded["findings"], loaded["saved_at"], scope=loaded.get("scope"),
    )
    assert rehash == saved["case_data_hash"]


def test_old_case_without_scope_still_rehashes(tmp_path, monkeypatch):
    monkeypatch.setattr("case_manager.CASES_DIR", str(tmp_path))
    saved = case_manager.save_case("Old case", WALLET, EDGES, case_number="BT-2026-0102")
    loaded = case_manager.load_case("BT-2026-0102")
    loaded.pop("scope", None)  # files written before scopes existed have no key at all
    _, rehash = case_manager.build_case_snapshot(
        loaded["case_number"], loaded["name"], loaded["start_wallet"], loaded["edges"],
        loaded["findings"], loaded["saved_at"], scope=loaded.get("scope"),
    )
    assert rehash == saved["case_data_hash"]
    assert {c["case_number"]: c for c in case_manager.list_cases()}["BT-2026-0102"]["scope"] is None


def test_certificates_verify_with_and_without_scope():
    payload = {"start_wallet": WALLET, "wallets_traced": 3}
    old_hash = compute_certificate_hash(payload, "GENESIS")
    assert verify_certificate(payload, "GENESIS", old_hash)
    scoped = {**payload, "scope": SCOPE}
    new_hash = compute_certificate_hash(scoped, "GENESIS")
    assert verify_certificate(scoped, "GENESIS", new_hash)
    assert new_hash != old_hash


# ---------- PDF dossier ----------

def _band_text(band):
    texts = []

    def walk(obj):
        if hasattr(obj, "text") and isinstance(getattr(obj, "text"), str):
            texts.append(obj.text)
        for cell_row in getattr(obj, "_cellvalues", []) or []:
            for cell in cell_row:
                for item in cell if isinstance(cell, (list, tuple)) else [cell]:
                    walk(item)
        for item in getattr(obj, "_content", []) or []:
            walk(item)

    walk(band)
    return " ".join(texts)


def test_pdf_header_shows_scope_and_cap():
    rows = [
        ("Investigation scope", describe_scope(SCOPE)),
        ("Transaction cap", describe_cap(["0xa", "0xb", "0xc"])),
    ]
    band = build_header_band(WALLET, styles=build_report_styles(), extra_rows=rows)
    text = _band_text(band)
    assert "INVESTIGATION SCOPE:" in text
    assert "Transactions 2022-03-23 to 2022-04-30 · oldest first" in text
    assert "Cap reached for 3 wallets; results are a sample, not the full history." in text
