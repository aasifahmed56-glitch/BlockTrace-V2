"""
Unit tests for case_manager.py and case anchoring logic.

Run with:
    pytest test_case_manager.py -v
"""

import os
import json
import tempfile
import pytest
import case_manager
from case_manager import (
    validate_case_number,
    generate_case_number,
    check_case_number_unique,
    build_case_snapshot,
    save_case,
    load_case,
    list_cases,
    delete_case,
    InvalidCaseNumberError,
    DuplicateCaseNumberError,
)


# ---------------- 1. case_number Validation ----------------

def test_validate_case_number_valid():
    assert validate_case_number("BT-2026-0001") == "BT-2026-0001"
    assert validate_case_number("CASE_99") == "CASE_99"
    assert validate_case_number("abc") == "abc"
    assert validate_case_number("12345678901234567890123456789012") == "12345678901234567890123456789012"
    # Trims leading/trailing whitespace
    assert validate_case_number("  BT-CASE-01  ") == "BT-CASE-01"


def test_validate_case_number_invalid_length():
    with pytest.raises(InvalidCaseNumberError, match="between 3 and 32 characters"):
        validate_case_number("ab")  # too short (<3)

    with pytest.raises(InvalidCaseNumberError, match="between 3 and 32 characters"):
        validate_case_number("a" * 33)  # too long (>32)

    with pytest.raises(InvalidCaseNumberError):
        validate_case_number("")


def test_validate_case_number_invalid_characters():
    with pytest.raises(InvalidCaseNumberError, match="letters, numbers, hyphens, and underscores"):
        validate_case_number("BT 2026 01")  # space inside

    with pytest.raises(InvalidCaseNumberError, match="letters, numbers, hyphens, and underscores"):
        validate_case_number("CASE#123")  # hash symbol

    with pytest.raises(InvalidCaseNumberError, match="letters, numbers, hyphens, and underscores"):
        validate_case_number("CASE.123")  # dot

    with pytest.raises(InvalidCaseNumberError, match="letters, numbers, hyphens, and underscores"):
        validate_case_number("CASE@2026")  # @ symbol


# ---------------- 2. Auto-generate Helper ----------------

def test_generate_case_number():
    generated = generate_case_number()
    assert generated.startswith("BT-")
    parts = generated.split("-")
    assert len(parts) == 3
    assert len(parts[1]) == 4  # Year
    assert len(parts[2]) == 4  # Sequence 0001+
    assert parts[2].isdigit()


# ---------------- 3. Deterministic Hashing ----------------

def test_deterministic_hashing_exact_match():
    edges = [
        {"from": "0xaaa", "to": "0xbbb", "value": 1.5},
        {"from": "0xccc", "to": "0xddd", "value": 10.0},
    ]
    snapshot1, hash1 = build_case_snapshot(
        "BT-2026-0001", "Investigation Alpha", "0xaaa", edges,
        findings={"score": 5}, saved_at="2026-10-09T10:00:00"
    )

    # Shuffled edges order in input — should still produce identical hash due to canonical sorting
    edges_shuffled = [
        {"from": "0xccc", "to": "0xddd", "value": 10},
        {"from": "0xaaa", "to": "0xbbb", "value": 1.5},
    ]
    snapshot2, hash2 = build_case_snapshot(
        "BT-2026-0001", "Investigation Alpha", "0xaaa", edges_shuffled,
        findings={"score": 5.0}, saved_at="2026-10-09T10:00:00"
    )

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex string


def test_different_data_produces_different_hash():
    edges = [{"from": "0xaaa", "to": "0xbbb", "value": 1.5}]
    _, hash1 = build_case_snapshot(
        "BT-2026-0001", "Case 1", "0xaaa", edges, saved_at="2026-10-09T10:00:00"
    )
    _, hash2 = build_case_snapshot(
        "BT-2026-0002", "Case 1", "0xaaa", edges, saved_at="2026-10-09T10:00:00"
    )
    assert hash1 != hash2


# ---------------- 4. Duplicate Rejection & Persistence ----------------

def test_duplicate_case_number_rejection(monkeypatch, tmp_path):
    # Redirect CASES_DIR to isolated temporary directory
    cases_tmp = tmp_path / "cases"
    cases_tmp.mkdir()
    monkeypatch.setattr("case_manager.CASES_DIR", str(cases_tmp))

    edges = [{"from": "0x111", "to": "0x222", "value": 0.5}]
    # Save first case
    save_case("First Case", "0x111", edges, case_number="BT-2026-TEST")

    # Attempt saving a different case with the same case number
    with pytest.raises(DuplicateCaseNumberError):
        save_case("Second Case", "0x111", edges, case_number="BT-2026-TEST")

    # Case-insensitive duplicate rejection
    with pytest.raises(DuplicateCaseNumberError):
        save_case("Third Case", "0x111", edges, case_number="bt-2026-test")


# ---------------- 5. Backward Compatibility (Legacy cases) ----------------

def test_backward_compatibility_legacy_case(monkeypatch, tmp_path):
    cases_tmp = tmp_path / "cases"
    cases_tmp.mkdir()
    monkeypatch.setattr("case_manager.CASES_DIR", str(cases_tmp))

    # Create a legacy case JSON file WITHOUT case_number
    legacy_payload = {
        "name": "Legacy Case 2025",
        "start_wallet": "0x999",
        "saved_at": "2025-01-01T12:00:00",
        "edge_count": 1,
        "edges": [{"from": "0x999", "to": "0x888", "value": 1.0}],
    }
    legacy_file = cases_tmp / "Legacy Case 2025.json"
    with open(legacy_file, "w", encoding="utf-8") as f:
        json.dump(legacy_payload, f)

    # Pre-workspace files sit directly in cases/; the API moves them on startup
    case_manager.migrate_legacy_cases()

    # list_cases should not crash and show case_number as 'Legacy'
    all_cases = list_cases()
    assert len(all_cases) == 1
    assert all_cases[0]["name"] == "Legacy Case 2025"
    assert all_cases[0]["case_number"] == "Legacy"

    # load_case should succeed and include case_number="Legacy"
    loaded = load_case("Legacy Case 2025")
    assert loaded is not None
    assert loaded["case_number"] == "Legacy"
    assert loaded["edge_count"] == 1
