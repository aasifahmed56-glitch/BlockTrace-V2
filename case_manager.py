"""
Case management — save and reload named investigations without re-hitting the
Etherscan API each time. A "case" is the set of transactions and findings currently in the
graph, saved as JSON under ./cases/<name>.json.

Supports unique case_number identifiers, deterministic JSON snapshot hashing,
and on-chain anchoring metadata.
"""

import os
import re
import json
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

CASES_DIR = "cases"
CASE_NUMBER_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,32}$")


class DuplicateCaseNumberError(Exception):
    """Raised when a case_number already exists."""
    pass


class InvalidCaseNumberError(ValueError):
    """Raised when a case_number format is invalid."""
    pass


def _ensure_cases_dir():
    os.makedirs(CASES_DIR, exist_ok=True)


def _canonicalize_numbers(obj):
    """Recursively normalizes numbers to float to match logic.py canonicalization."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _canonicalize_numbers(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize_numbers(v) for v in obj]
    return obj


def validate_case_number(case_number: str) -> str:
    """Validates case_number: required, trimmed, 3-32 chars, letters/digits/hyphens/underscores only.

    Raises InvalidCaseNumberError (subclass of ValueError) on invalid format.
    """
    if not case_number or not isinstance(case_number, str):
        raise InvalidCaseNumberError("Case number is required.")

    trimmed = case_number.strip()
    if not (3 <= len(trimmed) <= 32):
        raise InvalidCaseNumberError(
            f"Case number must be between 3 and 32 characters long (got {len(trimmed)})."
        )

    if not CASE_NUMBER_REGEX.match(trimmed):
        raise InvalidCaseNumberError(
            "Case number may only contain letters, numbers, hyphens, and underscores (no spaces or special symbols)."
        )

    return trimmed


def generate_case_number() -> str:
    """Auto-generates a unique case number in the format BT-YYYY-XXXX."""
    _ensure_cases_dir()
    year = datetime.now().year
    prefix = f"BT-{year}-"
    max_seq = 0

    for fname in os.listdir(CASES_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(CASES_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            num = data.get("case_number", "")
            if num.startswith(prefix):
                suffix = num[len(prefix):]
                if suffix.isdigit():
                    max_seq = max(max_seq, int(suffix))
        except Exception:
            continue

    return f"{prefix}{max_seq + 1:04d}"


def check_case_number_unique(case_number: str, current_case_name: Optional[str] = None):
    """Checks whether case_number is already used by an existing case.

    Raises DuplicateCaseNumberError if already taken by another case.
    """
    _ensure_cases_dir()
    target_lower = case_number.strip().lower()

    for fname in os.listdir(CASES_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(CASES_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            num = data.get("case_number")
            if num and num.strip().lower() == target_lower:
                # If it's the exact same case file being re-saved under the same name, allow update
                existing_name = data.get("name", "")
                if current_case_name and existing_name == current_case_name:
                    continue
                raise DuplicateCaseNumberError(
                    f"Case number '{case_number}' is already assigned to case '{existing_name}'."
                )
        except DuplicateCaseNumberError:
            raise
        except Exception:
            continue


def build_case_snapshot(case_number: str, name: str, start_wallet: str, edges: list,
                        findings: Optional[dict] = None, saved_at: Optional[str] = None) -> Tuple[dict, str]:
    """Builds a canonical JSON snapshot of the case and returns (snapshot_dict, sha256_hash).

    Deterministic serialization: sorted keys, canonicalized numbers, compact separators.
    """
    timestamp = saved_at or datetime.now().isoformat()

    # Sort edges deterministically
    sorted_edges = sorted(
        [{"from": e["from"] if isinstance(e, dict) else e[0],
          "to": e["to"] if isinstance(e, dict) else e[1],
          "value": float(e["value"] if isinstance(e, dict) else e[2])}
         for e in edges],
        key=lambda x: (x["from"].lower(), x["to"].lower(), x["value"])
    )

    # Extract unique sorted nodes
    nodes = sorted(list({e["from"].lower() for e in sorted_edges} | {e["to"].lower() for e in sorted_edges}))

    snapshot = {
        "case_number": case_number,
        "case_name": name,
        "saved_at": timestamp,
        "start_wallet": start_wallet.lower() if start_wallet else "",
        "graph": {
            "node_count": len(nodes),
            "edge_count": len(sorted_edges),
            "nodes": nodes,
            "edges": sorted_edges,
        },
        "findings": findings or {},
    }

    canonical_obj = _canonicalize_numbers(snapshot)
    canonical_json = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))
    case_data_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    return snapshot, case_data_hash


def save_case(name: str, start_wallet: str, edges: list, case_number: Optional[str] = None,
              findings: Optional[dict] = None, blockchain_meta: Optional[dict] = None) -> dict:
    """Saves a case locally under cases/<safe_name>.json.

    Args:
        name: Human-readable case name.
        start_wallet: Starting wallet address.
        edges: list of (from_addr, to_addr, value) tuples or dicts.
        case_number: Unique case number (validated, or auto-generated if None/blank).
        findings: Optional findings snapshot.
        blockchain_meta: Optional on-chain metadata (cid, tx_hash, blockchain_status, etc.)

    Returns:
        dict containing the saved case payload including case_number, path, case_data_hash.
    """
    _ensure_cases_dir()
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
    if not safe_name:
        raise ValueError("Case name must contain at least one alphanumeric character.")

    if case_number and case_number.strip():
        validated_case_num = validate_case_number(case_number)
    else:
        validated_case_num = generate_case_number()

    check_case_number_unique(validated_case_num, current_case_name=safe_name)

    saved_at = datetime.now().isoformat()
    snapshot, case_data_hash = build_case_snapshot(
        validated_case_num, safe_name, start_wallet, edges, findings=findings, saved_at=saved_at
    )

    meta = blockchain_meta or {}
    blockchain_status = meta.get("blockchain_status", "not_anchored")

    # Format edges as standard dicts for local storage
    formatted_edges = [
        {"from": e["from"] if isinstance(e, dict) else e[0],
         "to": e["to"] if isinstance(e, dict) else e[1],
         "value": float(e["value"] if isinstance(e, dict) else e[2])}
        for e in edges
    ]

    payload = {
        "name": safe_name,
        "case_number": validated_case_num,
        "start_wallet": start_wallet,
        "saved_at": saved_at,
        "edge_count": len(formatted_edges),
        "edges": formatted_edges,
        "findings": findings or {},
        "case_data_hash": case_data_hash,
        "blockchain_status": blockchain_status,
        "cid": meta.get("cid"),
        "ipfs_gateway_url": meta.get("ipfs_gateway_url"),
        "tx_hash": meta.get("tx_hash"),
        "explorer_url": meta.get("explorer_url"),
        "chain_error": meta.get("chain_error"),
        "version": meta.get("version", 1),
        "encrypted": meta.get("encrypted", False),
        "encryption_version": meta.get("encryption_version", 1 if meta.get("encrypted") else None),
    }

    path = os.path.join(CASES_DIR, f"{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    payload["path"] = path
    return payload


def update_case_blockchain_meta(identifier: str, meta: dict) -> Optional[dict]:
    """Updates blockchain anchoring metadata for an existing case (found by name or case_number)."""
    case_data = load_case(identifier)
    if not case_data:
        return None

    for k in ("blockchain_status", "cid", "ipfs_gateway_url", "tx_hash", "explorer_url", "chain_error", "version", "encrypted", "encryption_version"):
        if k in meta:
            case_data[k] = meta[k]

    safe_name = case_data["name"]
    path = os.path.join(CASES_DIR, f"{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(case_data, f, indent=2)

    case_data["path"] = path
    return case_data


def list_cases() -> List[Dict[str, Any]]:
    """Returns a list of dicts for every saved case, most recently saved first.

    Backward compatibility: existing saved cases without a case_number show 'Legacy'.
    """
    _ensure_cases_dir()
    cases = []
    for fname in os.listdir(CASES_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(CASES_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            case_info = {
                "name": data.get("name", fname[:-5]),
                "case_number": data.get("case_number") or "Legacy",
                "saved_at": data.get("saved_at", ""),
                "edge_count": data.get("edge_count", len(data.get("edges", []))),
                "blockchain_status": data.get("blockchain_status", "not_anchored"),
                "cid": data.get("cid"),
                "ipfs_gateway_url": data.get("ipfs_gateway_url"),
                "tx_hash": data.get("tx_hash"),
                "explorer_url": data.get("explorer_url"),
                "case_data_hash": data.get("case_data_hash"),
                "version": data.get("version", 1),
                "chain_error": data.get("chain_error"),
                "encrypted": data.get("encrypted", False),
                "encryption_version": data.get("encryption_version"),
            }
            cases.append(case_info)
        except (json.JSONDecodeError, KeyError, OSError):
            continue  # skip unreadable files rather than crashing
    cases.sort(key=lambda c: c.get("saved_at", ""), reverse=True)
    return cases


def load_case(identifier: str) -> Optional[Dict[str, Any]]:
    """Loads a case by either case_name or case_number.

    Backward compatibility: handles cases with or without case_number.
    """
    _ensure_cases_dir()
    # 1. Direct filename check by name
    path = os.path.join(CASES_DIR, f"{identifier}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "case_number" not in data:
                data["case_number"] = "Legacy"
            return data
        except Exception:
            return None

    # 2. Search by case_number or case_name inside files
    ident_lower = identifier.strip().lower()
    for fname in os.listdir(CASES_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(CASES_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            num = data.get("case_number", "")
            name = data.get("name", "")
            if (num and num.lower() == ident_lower) or name.lower() == ident_lower:
                if "case_number" not in data:
                    data["case_number"] = "Legacy"
                return data
        except Exception:
            continue

    return None


def delete_case(identifier: str) -> bool:
    """Deletes a saved case file by name or case_number."""
    _ensure_cases_dir()
    # Direct check
    path = os.path.join(CASES_DIR, f"{identifier}.json")
    if os.path.exists(path):
        os.remove(path)
        return True

    # Search by case_number or name
    ident_lower = identifier.strip().lower()
    for fname in os.listdir(CASES_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(CASES_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            num = data.get("case_number", "")
            name = data.get("name", "")
            if (num and num.lower() == ident_lower) or name.lower() == ident_lower:
                os.remove(os.path.join(CASES_DIR, fname))
                return True
        except Exception:
            continue

    return False
