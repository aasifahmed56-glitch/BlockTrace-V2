"""
Regression tests for duplicated rows in the PDF dossier and Findings.

The dossier's queries used to ignore the workspace, so after other visitors had
traced the same case every wallet, sanctions hit and round-number transfer was
listed once per workspace, and the totals exceeded what one trace can produce.

Etherscan is mocked; Neo4j is the real database, written only in throwaway
workspaces that are cleared afterwards.
"""

import uuid
from collections import Counter
from unittest.mock import MagicMock

import pytest

import api
import report_generator
import workspace
from logic import check_sanctions, unique_rows

RONIN = "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"  # checksummed, as in CURATED_CASES
HOPS, TX_PER_WALLET = 2, 15
# One trace visits at most 1 + 15 wallets per hop and loads at most 15 txs per visited wallet.
MAX_VISITED = 1 + TX_PER_WALLET
MAX_TXS = MAX_VISITED * TX_PER_WALLET
MAX_WALLETS = MAX_VISITED + MAX_TXS


def _addr(n):
    # Hex letters in every address, so a mixed-case spelling really differs.
    return "0x" + f"{0xabcdef << 136 | n:040x}"


def _checksummish(addr):
    """Mixed-case spelling of an address, like Etherscan's checksummed form."""
    return "0x" + "".join(c.upper() if i % 2 else c for i, c in enumerate(addr[2:]))


def _fake_txlist(address):
    """Deterministic transactions for an address: the start wallet receives round-number
    transfers from senders spelled in mixed case; every wallet sends a few small amounts."""
    address = address.lower()
    txs = []
    if address == RONIN.lower():
        for i, value in enumerate([3390, 330, 300, 40]):
            txs.append({"hash": f"0xin{i}", "from": _checksummish(_addr(100 + i)), "to": RONIN,
                        "value": str(value * 10**18), "timeStamp": str(1648000000 + i)})
        for i in range(20):
            txs.append({"hash": f"0xout{i}", "from": RONIN, "to": _addr(200 + i % 6),
                        "value": str(i * 10**17 + 5 * 10**16), "timeStamp": str(1648100000 + i)})
    else:
        for i in range(3):
            txs.append({"hash": f"0x{address[2:12]}{i}", "from": address, "to": _addr(300 + i),
                        "value": str(10**16), "timeStamp": str(1648200000 + i)})
    return txs


def _fake_get(url, params=None, timeout=None):
    resp = MagicMock()
    if params.get("module") == "block":
        resp.json.return_value = {"status": "1", "result": "14400000"}
    else:
        resp.json.return_value = {"status": "1", "result": _fake_txlist(params["address"])}
    return resp


@pytest.fixture
def etherscan(monkeypatch):
    monkeypatch.setattr(api.requests, "get", _fake_get)
    monkeypatch.setattr(api.time, "sleep", lambda s: None)


@pytest.fixture
def traced_twice(etherscan):
    """Loads the Ronin case into two fresh workspaces (the second is "another visitor")."""
    mine, other = f"test-{uuid.uuid4()}", f"test-{uuid.uuid4()}"
    for ws in (other, mine):
        token = workspace._current.set(ws)
        try:
            api.load_curated_case("Ronin Bridge Hack ($600M, 2022)")
        finally:
            workspace._current.reset(token)
    token = workspace._current.set(mine)
    try:
        yield mine
    finally:
        api.clear_graph()
        workspace._current.reset(token)
        token = workspace._current.set(other)
        api.clear_graph()
        workspace._current.reset(token)


def _assert_no_duplicate_wallets(rows, label):
    counts = Counter(r[0].lower() for r in rows)
    assert not [w for w, c in counts.items() if c > 1], f"duplicate wallets in {label}: {rows}"


def test_api_counts_and_rows_are_distinct(traced_twice):
    wallets, txs = api.get_summary_stats()
    assert wallets <= MAX_WALLETS and txs <= MAX_TXS

    addresses = api.get_all_wallet_addresses()
    assert len(addresses) == len({a.lower() for a in addresses}) == wallets
    assert all(a == a.lower() for a in addresses), "addresses must be stored lowercase"

    assert [a.lower() for a, _ in check_sanctions(addresses)] == [RONIN.lower()]
    for label, rows in [("hub", api.get_hub_wallets()), ("fanout", api.get_fanout_wallets()),
                        ("peel", api.get_peel_chains()), ("circular", api.get_circular_flows())]:
        _assert_no_duplicate_wallets(rows, label)
    round_rows = api.get_round_number_transactions()
    assert sorted(v for _, _, v in round_rows) == [40.0, 300.0, 330.0, 3390.0]


def test_report_queries_see_only_this_workspace(traced_twice):
    with report_generator.driver.session(database=report_generator.NEO4J_DATABASE) as session:
        assert report_generator.get_summary_stats(session) == api.get_summary_stats()
        addresses = report_generator.get_all_wallet_addresses(session)
        assert sorted(addresses) == sorted(api.get_all_wallet_addresses())
        assert len(check_sanctions(addresses)) == 1

        round_rows = report_generator.get_round_number_transactions(session)
        assert sorted(v for _, _, v in round_rows) == [40.0, 300.0, 330.0, 3390.0]
        for label, rows in [("hub", report_generator.get_hub_wallets(session)),
                            ("fanout", report_generator.get_fanout_wallets(session)),
                            ("peel", report_generator.get_peel_chains(session)),
                            ("circular", report_generator.get_circular_flows(session))]:
            _assert_no_duplicate_wallets(rows, label)


def test_mixed_case_spellings_share_one_node(traced_twice):
    """A sender seen as checksummed text must not create a second node."""
    addresses = api.get_all_wallet_addresses()
    assert _addr(100) in addresses
    assert _checksummish(_addr(100)) not in addresses


def test_saved_case_edges_reload_lowercase(etherscan):
    ws = f"test-{uuid.uuid4()}"
    token = workspace._current.set(ws)
    try:
        api.load_case_edges([{"from": RONIN, "to": _checksummish(_addr(5)), "value": 1.0},
                             {"from": RONIN.lower(), "to": _addr(5), "value": 2.0}])
        assert sorted(api.get_all_wallet_addresses()) == sorted([RONIN.lower(), _addr(5)])
    finally:
        api.clear_graph()
        workspace._current.reset(token)


def test_check_sanctions_reports_each_address_once():
    matches = check_sanctions([RONIN, RONIN.lower(), RONIN.upper().replace("0X", "0x"), _addr(1)])
    assert [a for a, _ in matches] == [RONIN]


def test_unique_rows_keeps_first_per_wallet():
    rows = [("0xAA", 5), ("0xaa", 5), ("0xbb", 3)]
    assert unique_rows(rows) == [("0xAA", 5), ("0xbb", 3)]
