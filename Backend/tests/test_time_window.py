import pytest
from datetime import datetime, timezone, date
from unittest.mock import patch, MagicMock

from api import date_to_block, fetch_transactions, ExpandRequest, PathRequest, get_data_window_stats
from report_generator import generate_report
from report_theme import build_header_band, build_report_styles


def test_date_to_block_none_and_empty():
    assert date_to_block(None, closest="after") == 0
    assert date_to_block(None, closest="before") == 99999999
    assert date_to_block("", closest="after") == 0
    assert date_to_block("", closest="before") == 99999999


@patch("api.requests.get")
def test_date_to_block_conversion(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "1", "message": "OK", "result": "14440544"}
    mock_get.return_value = mock_resp

    # String date YYYY-MM-DD
    block = date_to_block("2022-03-23", closest="after", chainid=1)
    assert block == 14440544
    assert mock_get.called
    args, kwargs = mock_get.call_args
    assert kwargs["params"]["timestamp"] == int(datetime(2022, 3, 23, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    assert kwargs["params"]["closest"] == "after"
    assert kwargs["params"]["chainid"] == 1

    # Date object for 'before'
    mock_resp.json.return_value = {"status": "1", "message": "OK", "result": "14450000"}
    block_before = date_to_block(date(2022, 3, 24), closest="before", chainid=56)
    assert block_before == 14450000
    _, kwargs2 = mock_get.call_args
    assert kwargs2["params"]["timestamp"] == int(datetime(2022, 3, 24, 23, 59, 59, tzinfo=timezone.utc).timestamp())
    assert kwargs2["params"]["closest"] == "before"
    assert kwargs2["params"]["chainid"] == 56


@patch("api.requests.get")
def test_date_to_block_failure_fallback(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "0", "message": "NOTOK", "result": "Error"}
    mock_get.return_value = mock_resp

    assert date_to_block("2022-03-23", closest="after") == 0
    assert date_to_block("2022-03-23", closest="before") == 99999999


@patch("api.requests.get")
def test_fetch_transactions_limit_hit(mock_get):
    mock_resp = MagicMock()
    # Return 20 mock txs
    mock_txs = [{"hash": f"0x{i}", "from": "0xa", "to": "0xb", "value": "1000000000000000000", "timeStamp": "1648011234"} for i in range(20)]
    mock_resp.json.return_value = {"status": "1", "result": mock_txs}
    mock_get.return_value = mock_resp

    txs, hit_limit = fetch_transactions("0x123", limit=15, chainid=1, startblock=100, endblock=200, sort="asc")
    assert len(txs) == 15
    assert hit_limit is True

    _, kwargs = mock_get.call_args
    assert kwargs["params"]["startblock"] == 100
    assert kwargs["params"]["endblock"] == 200
    assert kwargs["params"]["sort"] == "asc"


@patch("api.requests.get")
def test_fetch_transactions_under_limit(mock_get):
    mock_resp = MagicMock()
    mock_txs = [{"hash": "0x1", "from": "0xa", "to": "0xb", "value": "1000000000000000000", "timeStamp": "1648011234"}]
    mock_resp.json.return_value = {"status": "1", "result": mock_txs}
    mock_get.return_value = mock_resp

    txs, hit_limit = fetch_transactions("0x123", limit=15)
    assert len(txs) == 1
    assert hit_limit is False


def test_expand_request_model():
    req = ExpandRequest(
        wallet="0x1234567890abcdef1234567890abcdef12345678",
        hops=2,
        tx_per_wallet=15,
        from_date="2022-03-20",
        to_date="2022-03-25",
        sort="desc"
    )
    assert req.from_date == "2022-03-20"
    assert req.to_date == "2022-03-25"
    assert req.sort == "desc"


def test_pdf_header_band_with_data_window():
    styles = build_report_styles()
    band = build_header_band(
        start_wallet="0x098B716B8Aaf21512996dC57EB0615e2383E2f96",
        styles=styles,
        data_window="Data window: 2022-03-23 to 2022-03-29 (UTC)"
    )
    assert band is not None

