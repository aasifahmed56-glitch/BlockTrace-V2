"""
Tests for the OFAC SDN import script and the sanctions snapshot loader. They use the
small fixture in test_fixtures/sdn_sample.xml, so no network access is needed.
"""

import importlib.util
import json
import os

import pytest
from fastapi.testclient import TestClient

import api
import logic

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "test_fixtures", "sdn_sample.xml")
RONIN = "0x098b716b8aaf21512996dc57eb0615e2383e2f96"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "update_sanctions", os.path.join(HERE, "scripts", "update_sanctions.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load_script()


def test_parse_keeps_only_evm_addresses(script):
    pub_date, addresses = script.parse_sdn_xml(FIXTURE)
    assert pub_date == "2026-10-28"
    # BTC, TRX and a 0x string under a non-currency id type are all ignored
    assert set(addresses) == {RONIN, "0x00000000000000000000000000000000000000aa"}


def test_parse_maps_entry_fields(script):
    _, addresses = script.parse_sdn_xml(FIXTURE)
    ronin = addresses[RONIN]
    assert ronin == {
        "name": "LAZARUS GROUP",
        "authority": "U.S. Treasury OFAC",
        "program": "DPRK3",
        "uid": "27307",
        "currencies": ["ETH"],
        "list_published_date": "2026-10-28",
    }


def test_parse_merges_currencies_for_one_address(script):
    _, addresses = script.parse_sdn_xml(FIXTURE)
    entry = addresses["0x00000000000000000000000000000000000000aa"]
    assert entry["name"] == "Jane EXAMPLE"
    assert entry["program"] == "CYBER2; RUSSIA-EO14024"
    assert entry["currencies"] == ["USDT", "ETH"]


def test_script_writes_snapshot(script, tmp_path):
    out = tmp_path / "sanctions.json"
    assert script.main(["--xml", FIXTURE, "--output", str(out)]) == 0
    snapshot = json.loads(out.read_text(encoding="utf-8"))
    assert snapshot["list_publication_date"] == "2026-10-28"
    assert snapshot["count"] == 2
    assert snapshot["fetched_at"]
    assert snapshot["source_url"].endswith("sdn_sample.xml")
    assert RONIN in snapshot["addresses"]


def test_script_refuses_to_write_empty_snapshot(script, tmp_path):
    empty = tmp_path / "empty.xml"
    empty.write_text('<?xml version="1.0"?><sdnList><publshInformation><Publish_Date>01/01/2026</Publish_Date>'
                     '</publshInformation></sdnList>', encoding="utf-8")
    out = tmp_path / "out.json"
    assert script.main(["--xml", str(empty), "--output", str(out)]) == 1
    assert not out.exists()


def _write_snapshot(script, tmp_path):
    out = tmp_path / "snap.json"
    script.main(["--xml", FIXTURE, "--output", str(out)])
    return str(out)


def test_loader_merges_manual_entries(script, tmp_path):
    addresses, meta = logic.load_sanctions(_write_snapshot(script, tmp_path))
    assert meta["count"] == 2 and meta["list_publication_date"] == "2026-10-28"
    ronin = addresses[RONIN]
    # The manual entry's richer name and note win; the snapshot's program is kept.
    assert ronin["name"] == "Ronin Bridge Hacker (Lazarus Group)"
    assert "Ronin Bridge exploit" in ronin["note"]
    assert ronin["program"] == "DPRK3"
    assert "0x00000000000000000000000000000000000000aa" in addresses


def test_loader_falls_back_when_file_missing(tmp_path):
    addresses, meta = logic.load_sanctions(str(tmp_path / "missing.json"))
    assert set(addresses) == {RONIN}
    assert meta["count"] == 0 and meta["list_publication_date"] is None
    assert "unavailable" in logic.describe_sanctions_snapshot(meta)


@pytest.mark.parametrize("content", ["not json", "[]", '{"addresses": "nope"}'])
def test_loader_falls_back_when_file_invalid(tmp_path, content):
    bad = tmp_path / "bad.json"
    bad.write_text(content, encoding="utf-8")
    addresses, meta = logic.load_sanctions(str(bad))
    assert set(addresses) == {RONIN}
    assert meta["count"] == 0


def test_check_sanctions_is_case_insensitive_with_snapshot(script, tmp_path, monkeypatch):
    addresses, _ = logic.load_sanctions(_write_snapshot(script, tmp_path))
    monkeypatch.setattr(logic, "SANCTIONED_ADDRESSES", addresses)
    matches = logic.check_sanctions(["0x00000000000000000000000000000000000000AA", "0x" + "1" * 40])
    assert [addr for addr, _ in matches] == ["0x00000000000000000000000000000000000000AA"]


def test_committed_snapshot_is_loaded():
    """The repository ships a real snapshot, so the deployed backend screens the full list."""
    assert logic.SANCTIONS_META["count"] > 1
    assert logic.SANCTIONS_META["list_publication_date"]
    assert RONIN in logic.SANCTIONED_ADDRESSES
    assert all(addr == addr.lower() and addr.startswith("0x") for addr in logic.SANCTIONED_ADDRESSES)


def test_sanctions_check_reports_snapshot_metadata(monkeypatch):
    monkeypatch.setattr(api, "PUBLIC_MODE", False)
    body = TestClient(api.app).get("/sanctions/check", params={"address": RONIN.upper().replace("0X", "0x")}).json()
    assert body["sanctioned"] is True
    assert body["list_publication_date"] == logic.SANCTIONS_META["list_publication_date"]
    assert body["fetched_at"] == logic.SANCTIONS_META["fetched_at"]
    assert body["count"] == logic.SANCTIONS_META["count"]
    assert "dated snapshot" in body["note"]
