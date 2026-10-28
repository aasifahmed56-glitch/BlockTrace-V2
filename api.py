"""
BlockTrace API — FastAPI backend.

Replaces the Streamlit UI entirely. All business logic (detection heuristics, risk
scoring, narrative generation, sanctions screening, certificates) is unchanged and
still lives in logic.py — this file only handles HTTP request/response wiring and
the Neo4j/Etherscan I/O that used to live inline in app.py.

Run with:
    uvicorn api:app --reload --port 8000

Interactive API docs (auto-generated) are then available at:
    http://localhost:8000/docs
"""

import os
import time
import hashlib
import json as jsonlib
from typing import Optional, List

import requests
from dotenv import load_dotenv

# Ensure environment variables from .env strictly override any cached process environment
load_dotenv(override=True)

from neo4j import GraphDatabase
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from logic import (
    short, risk_tier, compute_wallet_risk, build_narrative,
    check_sanctions, get_entity_label, compute_certificate_hash, verify_certificate
)
import case_manager
from case_manager import (
    DuplicateCaseNumberError, InvalidCaseNumberError, validate_case_number,
    generate_case_number, build_case_snapshot, update_case_blockchain_meta
)
from report_generator import generate_report
from pinata_service import (
    upload_pdf_to_pinata, upload_json_to_pinata, upload_encrypted_file_to_pinata,
    download_file_from_ipfs, PinataUploadError
)
from crypto_service import (
    encrypt_snapshot, decrypt_snapshot, is_encryption_configured,
    CryptoError, CryptoKeyMissingError
)
from blockchain_service import (
    store_record_on_chain, is_hash_on_chain, get_report_record, store_case_on_chain,
    get_case_from_chain, is_case_on_chain, BlockchainServiceError
)

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

CHAIN_OPTIONS = {
    "Ethereum": 1,
    "BNB Smart Chain": 56,
    "Polygon": 137,
}

CURATED_CASES = {
    "Ronin Bridge Hack ($600M, 2022)": {
        "address": "0x098B716B8Aaf21512996dC57EB0615e2383E2f96",
        "chainid": 1,
        "description": "Wallet linked to the Axie Infinity / Ronin Bridge exploit. "
                        "Sanctioned by the U.S. Treasury (OFAC) and attributed to the Lazarus Group."
    },
    "Poly Network Hack ($611M, 2021)": {
        "address": "0xC8a65Fadf0e0dDAf421F28FEAb69Bf6E2E589963",
        "chainid": 1,
        "description": "Largest DeFi exploit at the time, draining assets across Ethereum, BSC, "
                        "and Polygon. Most funds were later voluntarily returned by the attacker, "
                        "but the full on-chain trail remains public."
    },
    "Wormhole Bridge Hack ($321M, 2022)": {
        "address": "0x629e7Da20197a5429d30da36E77D06CdF796b71a",
        "chainid": 1,
        "description": "Exploit of the Ethereum-Solana Wormhole token bridge. This address is "
                        "directly labeled 'Wormhole Network Exploiter' on Etherscan."
    }
}

app = FastAPI(
    title="BlockTrace API",
    description="Explainable blockchain crime investigation — REST backend.",
    version="1.0.0",
)

# Dev-friendly CORS: allows any frontend (React dev server, etc.) to call this API.
# Tighten allow_origins to your actual frontend URL before deploying publicly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Request/response models ====================

class ExpandRequest(BaseModel):
    wallet: str
    hops: int = Field(2, ge=1, le=3)
    tx_per_wallet: int = Field(15, ge=5, le=30)
    chain: str = "Ethereum"


class PathRequest(BaseModel):
    source: str
    destination: str
    max_hops: int = Field(4, ge=1, le=6)
    tx_per_wallet: int = Field(15, ge=5, le=30)
    chain: str = "Ethereum"


class SaveCaseRequest(BaseModel):
    name: str
    case_number: Optional[str] = None
    start_wallet: Optional[str] = None
    anchor_on_chain: bool = True


class CertificateRequest(BaseModel):
    start_wallet: Optional[str] = None


class CertificateVerifyRequest(BaseModel):
    certificate_hash: str
    previous_hash: str
    payload: dict


class PublishReportRequest(BaseModel):
    start_wallet: Optional[str] = None


# ==================== Etherscan + Neo4j data layer ====================
# (Same logic as the old app.py — just with no Streamlit calls mixed in.)

def fetch_transactions(wallet_address, limit=15, chainid=1):
    params = {
        "chainid": chainid, "module": "account", "action": "txlist",
        "address": wallet_address, "startblock": 0, "endblock": 99999999,
        "sort": "desc", "apikey": ETHERSCAN_API_KEY
    }
    response = requests.get(ETHERSCAN_URL, params=params)
    data = response.json()
    if data["status"] != "1":
        return []
    return data["result"][:limit]


def load_transactions(session, transactions):
    new_wallets = set()
    for tx in transactions:
        from_addr, to_addr = tx["from"], tx["to"]
        if not to_addr:
            continue
        try:
            value_eth = int(tx["value"]) / 1e18
        except (ValueError, TypeError):
            continue

        # Sanity cap — see MASTER_ARCHITECTURE.md section 3.13 for why this exists.
        if value_eth < 0 or value_eth > 1_000_000:
            continue

        session.run(
            """
            MERGE (a:Wallet {address: $from_addr})
            MERGE (b:Wallet {address: $to_addr})
            MERGE (a)-[t:SENT {hash: $tx_hash}]->(b)
            SET t.value = $value_eth, t.timestamp = $timestamp
            """,
            from_addr=from_addr, to_addr=to_addr, tx_hash=tx["hash"],
            value_eth=value_eth, timestamp=tx["timeStamp"]
        )
        new_wallets.add(from_addr)
        new_wallets.add(to_addr)
    return new_wallets


def expand_from_wallet(start_wallet, hops=2, tx_per_wallet=15, chainid=1):
    visited = set()
    current_layer = {start_wallet}
    with driver.session(database=NEO4J_DATABASE) as session:
        for hop in range(hops):
            next_layer = set()
            for wallet in current_layer:
                if wallet in visited:
                    continue
                visited.add(wallet)
                txs = fetch_transactions(wallet, limit=tx_per_wallet, chainid=chainid)
                new_wallets = load_transactions(session, txs)
                next_layer.update(new_wallets)
                time.sleep(0.25)
            current_layer = next_layer - visited
    return len(visited)


def expand_until_found(source, destination, max_hops=6, tx_per_wallet=15, chainid=1):
    destination_lower = destination.lower()
    existing = {a.lower() for a in get_all_wallet_addresses()}
    if destination_lower in existing:
        return 0, True

    visited = set()
    current_layer = {source}
    found = False
    with driver.session(database=NEO4J_DATABASE) as session:
        for hop in range(max_hops):
            next_layer = set()
            for wallet in current_layer:
                if wallet in visited:
                    continue
                visited.add(wallet)
                txs = fetch_transactions(wallet, limit=tx_per_wallet, chainid=chainid)
                new_wallets = load_transactions(session, txs)
                next_layer.update(new_wallets)
                if destination_lower in {w.lower() for w in new_wallets}:
                    found = True
                time.sleep(0.25)
            current_layer = next_layer - visited
            if found:
                break
    return len(visited), found


def get_graph_data(limit=300):
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            "MATCH (a:Wallet)-[r:SENT]->(b:Wallet) RETURN a.address AS from_addr, b.address AS to_addr, r.value AS value LIMIT $limit",
            limit=limit
        )
        return [(r["from_addr"], r["to_addr"], r["value"]) for r in result]


def get_summary_stats():
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            "MATCH (w:Wallet) OPTIONAL MATCH (w)-[r:SENT]->() RETURN count(DISTINCT w) AS wallets, count(r) AS txs"
        )
        record = result.single()
        return record["wallets"], record["txs"]


def get_hub_wallets(limit=1000):
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            """
            MATCH (w:Wallet)-[r:SENT]-()
            RETURN w.address AS wallet, count(r) AS total_txs
            ORDER BY total_txs DESC LIMIT $limit
            """, limit=limit
        )
        return [(r["wallet"], r["total_txs"]) for r in result]


def get_fanout_wallets(min_recipients=4, limit=1000):
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            """
            MATCH (a:Wallet)-[:SENT]->(b:Wallet)
            WITH a, count(DISTINCT b) AS distinct_recipients
            WHERE distinct_recipients >= $min_recipients
            RETURN a.address AS wallet, distinct_recipients
            ORDER BY distinct_recipients DESC LIMIT $limit
            """, min_recipients=min_recipients, limit=limit
        )
        return [(r["wallet"], r["distinct_recipients"]) for r in result]


def get_peel_chains(limit=1000):
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            """
            MATCH (mid:Wallet)-[r2:SENT]->(next1:Wallet)
            MATCH (mid)-[r3:SENT]->(next2:Wallet)
            WHERE elementId(next1) < elementId(next2) AND r2.value > 0.001 AND r3.value > 0.001
            WITH mid,
                 CASE WHEN r2.value > r3.value THEN r2.value ELSE r3.value END AS bigger,
                 CASE WHEN r2.value > r3.value THEN r3.value ELSE r2.value END AS smaller
            WHERE (smaller / bigger) < 0.15
            WITH mid, bigger, smaller
            ORDER BY bigger DESC
            WITH mid, collect({main: bigger, peel: smaller})[0] AS top_match
            RETURN mid.address AS wallet, top_match.main AS main_amount, top_match.peel AS peel_amount
            ORDER BY main_amount DESC
            LIMIT $limit
            """, limit=limit
        )
        return [(r["wallet"], r["main_amount"], r["peel_amount"]) for r in result]


def get_round_number_transactions(min_value=1.0, limit=1000):
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            """
            MATCH (a:Wallet)-[r:SENT]->(b:Wallet)
            WHERE r.value >= $min_value AND r.value = toInteger(r.value)
            RETURN a.address AS from_addr, b.address AS to_addr, r.value AS value
            ORDER BY r.value DESC
            LIMIT $limit
            """, min_value=min_value, limit=limit
        )
        return [(r["from_addr"], r["to_addr"], r["value"]) for r in result]


def get_circular_flows(max_hops=4, limit=1000):
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            """
            MATCH path = (a:Wallet)-[:SENT*2..%d]->(a)
            RETURN DISTINCT a.address AS wallet, length(path) AS hops
            ORDER BY hops ASC
            LIMIT $limit
            """ % max_hops, limit=limit
        )
        return [(r["wallet"], r["hops"]) for r in result]


def get_all_wallet_addresses():
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run("MATCH (w:Wallet) RETURN w.address AS address")
        return [r["address"] for r in result]


def clear_graph():
    with driver.session(database=NEO4J_DATABASE) as session:
        session.run("MATCH (n:Wallet) DETACH DELETE n")


def load_case_edges(edges):
    with driver.session(database=NEO4J_DATABASE) as session:
        for i, e in enumerate(edges):
            synthetic_hash = hashlib.sha256(
                f"{e['from']}-{e['to']}-{e['value']}-{i}".encode()
            ).hexdigest()
            session.run(
                """
                MERGE (a:Wallet {address: $from_addr})
                MERGE (b:Wallet {address: $to_addr})
                MERGE (a)-[t:SENT {hash: $tx_hash}]->(b)
                SET t.value = $value_eth
                """,
                from_addr=e["from"], to_addr=e["to"], tx_hash=synthetic_hash, value_eth=e["value"]
            )


def get_paths_between(source, destination, max_hops=6, limit=10):
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            """
            MATCH (a:Wallet), (b:Wallet)
            WHERE toLower(a.address) = toLower($source) AND toLower(b.address) = toLower($destination)
            MATCH p = (a)-[:SENT*1..%d]->(b)
            RETURN [n IN nodes(p) | n.address] AS wallets,
                   [r IN relationships(p) | {from: startNode(r).address, to: endNode(r).address, value: r.value}] AS rels,
                   length(p) AS hops
            ORDER BY hops ASC
            LIMIT $limit
            """ % max_hops,
            source=source, destination=destination, limit=limit
        )
        return [{"wallets": r["wallets"], "rels": r["rels"], "hops": r["hops"]} for r in result]


def get_last_certificate():
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            """
            MATCH (c:Certificate)
            RETURN c.hash AS hash, c.created_at AS created_at
            ORDER BY c.created_at DESC LIMIT 1
            """
        )
        record = result.single()
        if record:
            return record["hash"], record["created_at"]
        return None, None


def store_certificate(cert_hash, prev_hash, wallet, created_at):
    with driver.session(database=NEO4J_DATABASE) as session:
        session.run(
            """
            CREATE (c:Certificate {hash: $hash, prev_hash: $prev_hash, wallet: $wallet, created_at: $created_at})
            """,
            hash=cert_hash, prev_hash=prev_hash, wallet=wallet, created_at=created_at
        )


def _resolve_chainid(chain_name):
    if chain_name not in CHAIN_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown chain '{chain_name}'. Valid options: {list(CHAIN_OPTIONS.keys())}")
    return CHAIN_OPTIONS[chain_name]


# ==================== Endpoints ====================

@app.get("/")
def health_check():
    return {"status": "ok", "service": "BlockTrace API"}


@app.get("/chains")
def list_chains():
    return {"chains": list(CHAIN_OPTIONS.keys())}


@app.get("/curated-cases")
def list_curated_cases():
    return {
        "cases": [
            {"name": name, "address": info["address"], "chainid": info["chainid"], "description": info["description"]}
            for name, info in CURATED_CASES.items()
        ]
    }


@app.post("/curated-cases/{case_name}/load")
def load_curated_case(case_name: str):
    if case_name not in CURATED_CASES:
        raise HTTPException(status_code=404, detail="Unknown curated case name.")
    info = CURATED_CASES[case_name]
    visited = expand_from_wallet(info["address"], hops=2, tx_per_wallet=15, chainid=info["chainid"])
    return {"wallets_visited": visited, "start_wallet": info["address"]}


@app.post("/expand")
def expand(req: ExpandRequest):
    chainid = _resolve_chainid(req.chain)
    visited = expand_from_wallet(req.wallet, hops=req.hops, tx_per_wallet=req.tx_per_wallet, chainid=chainid)
    return {"wallets_visited": visited, "start_wallet": req.wallet}


@app.post("/clear")
def clear():
    clear_graph()
    return {"status": "cleared"}


@app.get("/summary")
def summary():
    wallets, txs = get_summary_stats()
    return {"wallets_traced": wallets, "transactions_mapped": txs}


@app.get("/graph")
def graph():
    edges = get_graph_data()
    return {"edges": [{"from": f, "to": t, "value": v} for f, t, v in edges]}


@app.get("/detections/hub")
def detections_hub():
    return {"results": [{"wallet": w, "total_txs": c, "label": get_entity_label(w)} for w, c in get_hub_wallets()]}


@app.get("/detections/fanout")
def detections_fanout():
    return {"results": [{"wallet": w, "distinct_recipients": c, "label": get_entity_label(w)} for w, c in get_fanout_wallets()]}


@app.get("/detections/peel-chains")
def detections_peel():
    return {"results": [{"wallet": w, "main_amount": m, "peel_amount": p, "label": get_entity_label(w)} for w, m, p in get_peel_chains()]}


@app.get("/detections/round-number")
def detections_round():
    return {"results": [{"from": f, "to": t, "value": v} for f, t, v in get_round_number_transactions()]}


@app.get("/detections/circular")
def detections_circular():
    return {"results": [{"wallet": w, "hops": h, "label": get_entity_label(w)} for w, h in get_circular_flows()]}


@app.get("/sanctions")
def sanctions():
    matches = check_sanctions(get_all_wallet_addresses())
    return {"matches": [{"wallet": addr, **entry} for addr, entry in matches]}


@app.get("/risk")
def risk():
    hub_data = get_hub_wallets()
    fanout_data = get_fanout_wallets()
    peel_data = get_peel_chains()
    round_data = get_round_number_transactions()
    circular_data = get_circular_flows()
    sanctioned = {addr for addr, _ in check_sanctions(get_all_wallet_addresses())}

    rows = compute_wallet_risk(hub_data, fanout_data, peel_data, round_data, circular_data,
                                sanctioned_addresses=sanctioned)
    result = []
    for wallet, signals, score in rows:
        tier_label, tier_class = risk_tier(score)
        result.append({
            "wallet": wallet, "signals": signals, "score": score,
            "tier": tier_label, "label": get_entity_label(wallet)
        })
    return {"results": result}


@app.get("/narrative")
def narrative(start_wallet: Optional[str] = None):
    hub_data = get_hub_wallets()
    fanout_data = get_fanout_wallets()
    peel_data = get_peel_chains()
    round_data = get_round_number_transactions()
    circular_data = get_circular_flows()
    sanctioned = {addr for addr, _ in check_sanctions(get_all_wallet_addresses())}
    risk_rows = compute_wallet_risk(hub_data, fanout_data, peel_data, round_data, circular_data,
                                     sanctioned_addresses=sanctioned)
    wallets_count, txs_count = get_summary_stats()

    if not start_wallet:
        edges = get_graph_data()
        start_wallet = edges[0][0] if edges else ""

    paragraphs = build_narrative(
        start_wallet, wallets_count, txs_count,
        hub_data, fanout_data, peel_data, round_data, circular_data, risk_rows
    )
    return {"paragraphs": paragraphs}


@app.post("/path")
def find_path(req: PathRequest):
    chainid = _resolve_chainid(req.chain)
    visited, found = expand_until_found(
        req.source, req.destination, max_hops=req.max_hops,
        tx_per_wallet=req.tx_per_wallet, chainid=chainid
    )
    if not found:
        return {"found": False, "wallets_visited": visited, "paths": []}

    paths = get_paths_between(req.source, req.destination, max_hops=req.max_hops)
    return {"found": len(paths) > 0, "wallets_visited": visited, "paths": paths}


@app.get("/cases")
def list_cases():
    cases = case_manager.list_cases()
    return {"cases": cases}


@app.post("/cases")
def save_case(req: SaveCaseRequest):
    edges = get_graph_data()
    if not edges:
        raise HTTPException(status_code=400, detail="Nothing to save — the graph is empty.")
    start = req.start_wallet or edges[0][0]

    # Validate case number format if provided
    try:
        if req.case_number and req.case_number.strip():
            validated_case_num = validate_case_number(req.case_number)
        else:
            validated_case_num = generate_case_number()
    except InvalidCaseNumberError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Check case number uniqueness
    try:
        case_manager.check_case_number_unique(validated_case_num, current_case_name=req.name.strip())
    except DuplicateCaseNumberError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # Gather current findings snapshot
    hub_data = get_hub_wallets()
    fanout_data = get_fanout_wallets()
    peel_data = get_peel_chains()
    round_data = get_round_number_transactions()
    circular_data = get_circular_flows()
    sanctioned = [addr for addr, _ in check_sanctions(get_all_wallet_addresses())]
    wallets_count, txs_count = get_summary_stats()

    findings = {
        "wallets_traced": wallets_count,
        "transactions_mapped": txs_count,
        "hub_wallets": hub_data[:10],
        "fanout_wallets": fanout_data[:10],
        "peel_chains": [(w, m, p) for w, m, p in peel_data[:10]],
        "round_number_txs": round_data[:10],
        "circular_flows": circular_data[:10],
        "sanctions_matches": sanctioned,
    }

    initial_status = "pending" if req.anchor_on_chain else "skipped"
    try:
        local_result = case_manager.save_case(
            name=req.name,
            start_wallet=start,
            edges=edges,
            case_number=validated_case_num,
            findings=findings,
            blockchain_meta={"blockchain_status": initial_status}
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    cid = None
    ipfs_gateway_url = None
    tx_hash = None
    explorer_url = None
    version = 1
    chain_error = None
    blockchain_status = initial_status
    encrypted = False
    encryption_version = None

    if req.anchor_on_chain:
        snapshot, case_data_hash = build_case_snapshot(
            case_number=validated_case_num,
            name=local_result["name"],
            start_wallet=start,
            edges=edges,
            findings=findings,
            saved_at=local_result["saved_at"],
        )

        # 1. Encrypt snapshot before upload (do NOT upload plaintext if encryption fails)
        canonical_obj = case_manager._canonicalize_numbers(snapshot)
        canonical_bytes = jsonlib.dumps(canonical_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

        encrypted_bytes = None
        try:
            encrypted_bytes = encrypt_snapshot(canonical_bytes, validated_case_num)
            encrypted = True
            encryption_version = 1
        except Exception as exc:
            chain_error = f"Encryption failed: {exc}"
            blockchain_status = "failed"

        # 2. Upload ENCRYPTED snapshot to Pinata IPFS (never plaintext!)
        if encrypted_bytes:
            try:
                pinata_res = upload_encrypted_file_to_pinata(
                    encrypted_bytes,
                    filename=f"{validated_case_num}.enc",
                    metadata_name=f"BlockTrace_Case_{validated_case_num}_enc"
                )
                cid = pinata_res["cid"]
                ipfs_gateway_url = pinata_res["gateway_url"]
            except Exception as exc:
                chain_error = f"Pinata upload failed: {exc}"
                blockchain_status = "failed"

        # 3. Store anchor on Sepolia testnet
        if cid:
            try:
                chain_res = store_case_on_chain(
                    case_number=validated_case_num,
                    case_data_hash_hex=case_data_hash,
                    ipfs_cid=cid
                )
                tx_hash = chain_res["tx_hash"]
                explorer_url = chain_res["explorer_url"]
                version = chain_res.get("version", 1)
                blockchain_status = "anchored"
            except Exception as exc:
                chain_error = f"On-chain anchor failed: {exc}"
                blockchain_status = "failed"

        # Update local file with on-chain metadata including encryption fields
        case_manager.update_case_blockchain_meta(
            validated_case_num,
            {
                "blockchain_status": blockchain_status,
                "cid": cid,
                "ipfs_gateway_url": ipfs_gateway_url,
                "tx_hash": tx_hash,
                "explorer_url": explorer_url,
                "chain_error": chain_error,
                "version": version,
                "encrypted": encrypted,
                "encryption_version": encryption_version,
            }
        )

    response = {
        "status": "saved",
        "path": local_result["path"],
        "name": local_result["name"],
        "case_number": validated_case_num,
        "edge_count": len(edges),
        "blockchain_status": blockchain_status,
        "cid": cid,
        "ipfs_gateway_url": ipfs_gateway_url,
        "tx_hash": tx_hash,
        "explorer_url": explorer_url,
        "case_data_hash": local_result.get("case_data_hash"),
        "encrypted": encrypted,
    }
    if chain_error:
        response["chain_error"] = chain_error

    return response


@app.post("/cases/{case_number}/anchor")
@app.post("/api/cases/{case_number}/anchor")
def retry_anchor_case(case_number: str):
    case_data = case_manager.load_case(case_number)
    if not case_data:
        raise HTTPException(status_code=404, detail=f"Case '{case_number}' not found.")

    snapshot, case_data_hash = build_case_snapshot(
        case_number=case_data.get("case_number", case_number),
        name=case_data.get("name", ""),
        start_wallet=case_data.get("start_wallet", ""),
        edges=case_data.get("edges", []),
        findings=case_data.get("findings", {}),
        saved_at=case_data.get("saved_at"),
    )

    cid = case_data.get("cid")
    ipfs_gateway_url = case_data.get("ipfs_gateway_url")
    is_encrypted = case_data.get("encrypted", True)

    # 1. Encrypt and upload to Pinata if missing CID
    if not cid:
        canonical_obj = case_manager._canonicalize_numbers(snapshot)
        canonical_bytes = jsonlib.dumps(canonical_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

        try:
            encrypted_bytes = encrypt_snapshot(canonical_bytes, case_number)
        except Exception as exc:
            case_manager.update_case_blockchain_meta(
                case_number,
                {"blockchain_status": "failed", "chain_error": f"Encryption failed: {exc}"}
            )
            raise HTTPException(status_code=400, detail=f"Encryption failed: {exc}")

        try:
            pinata_res = upload_encrypted_file_to_pinata(
                encrypted_bytes,
                filename=f"{case_number}.enc",
                metadata_name=f"BlockTrace_Case_{case_number}_enc"
            )
            cid = pinata_res["cid"]
            ipfs_gateway_url = pinata_res["gateway_url"]
            is_encrypted = True
        except Exception as exc:
            case_manager.update_case_blockchain_meta(
                case_number,
                {"blockchain_status": "failed", "chain_error": f"Pinata upload failed: {exc}"}
            )
            raise HTTPException(status_code=502, detail=f"Pinata upload failed: {exc}")

    # 2. Store on chain
    try:
        chain_res = store_case_on_chain(case_number, case_data_hash, cid)
        version = chain_res.get("version", 1)
        case_manager.update_case_blockchain_meta(
            case_number,
            {
                "blockchain_status": "anchored",
                "cid": cid,
                "ipfs_gateway_url": ipfs_gateway_url,
                "tx_hash": chain_res["tx_hash"],
                "explorer_url": chain_res["explorer_url"],
                "version": version,
                "encrypted": is_encrypted,
                "encryption_version": 1 if is_encrypted else None,
                "chain_error": None,
            }
        )
        return {
            "status": "anchored",
            "case_number": case_number,
            "tx_hash": chain_res["tx_hash"],
            "explorer_url": chain_res["explorer_url"],
            "cid": cid,
            "version": version,
            "encrypted": is_encrypted,
        }
    except Exception as exc:
        case_manager.update_case_blockchain_meta(
            case_number,
            {"blockchain_status": "failed", "chain_error": f"On-chain anchor failed: {exc}"}
        )
        raise HTTPException(status_code=502, detail=f"On-chain anchor failed: {exc}")


@app.post("/cases/{case_number}/reanchor")
@app.post("/api/cases/{case_number}/reanchor")
def reanchor_case(case_number: str):
    """Re-anchors a case (e.g. a legacy unencrypted case) with an AES-256-GCM encrypted snapshot.

    Submits a new version to the BlockTraceCaseRegistry smart contract on Sepolia.
    """
    case_data = case_manager.load_case(case_number)
    if not case_data:
        raise HTTPException(status_code=404, detail=f"Case '{case_number}' not found.")

    snapshot, case_data_hash = build_case_snapshot(
        case_number=case_data.get("case_number", case_number),
        name=case_data.get("name", ""),
        start_wallet=case_data.get("start_wallet", ""),
        edges=case_data.get("edges", []),
        findings=case_data.get("findings", {}),
        saved_at=case_data.get("saved_at"),
    )

    canonical_obj = case_manager._canonicalize_numbers(snapshot)
    canonical_bytes = jsonlib.dumps(canonical_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

    # 1. Encrypt snapshot with per-case key derived from CASE_ENCRYPTION_KEY
    try:
        encrypted_bytes = encrypt_snapshot(canonical_bytes, case_number)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Encryption failed: {exc}")

    # 2. Upload encrypted snapshot to Pinata
    try:
        pinata_res = upload_encrypted_file_to_pinata(
            encrypted_bytes,
            filename=f"{case_number}.enc",
            metadata_name=f"BlockTrace_Case_{case_number}_enc_reanchor"
        )
        new_cid = pinata_res["cid"]
        new_gateway_url = pinata_res["gateway_url"]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Pinata upload failed: {exc}")

    # 3. Submit new version on-chain
    try:
        chain_res = store_case_on_chain(case_number, case_data_hash, new_cid)
        new_version = chain_res.get("version", 2)
        case_manager.update_case_blockchain_meta(
            case_number,
            {
                "blockchain_status": "anchored",
                "cid": new_cid,
                "ipfs_gateway_url": new_gateway_url,
                "tx_hash": chain_res["tx_hash"],
                "explorer_url": chain_res["explorer_url"],
                "version": new_version,
                "encrypted": True,
                "encryption_version": 1,
                "chain_error": None,
            }
        )
        return {
            "status": "reanchored",
            "case_number": case_number,
            "version": new_version,
            "tx_hash": chain_res["tx_hash"],
            "explorer_url": chain_res["explorer_url"],
            "cid": new_cid,
            "encrypted": True,
            "encryption_version": 1,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"On-chain re-anchor failed: {exc}")


@app.get("/cases/{case_number}/verify")
@app.get("/api/cases/{case_number}/verify")
def verify_case_endpoint(case_number: str):
    case_data = case_manager.load_case(case_number)
    if not case_data:
        raise HTTPException(status_code=404, detail=f"Case '{case_number}' not found locally.")

    snapshot, local_hash = build_case_snapshot(
        case_number=case_data.get("case_number", case_number),
        name=case_data.get("name", ""),
        start_wallet=case_data.get("start_wallet", ""),
        edges=case_data.get("edges", []),
        findings=case_data.get("findings", {}),
        saved_at=case_data.get("saved_at"),
    )
    local_hash = local_hash.lower()

    try:
        on_chain = get_case_from_chain(case_number)
    except Exception as exc:
        return {
            "valid": False,
            "case_number": case_number,
            "local_hash": local_hash,
            "error": str(exc),
            "details": "Case not found on Sepolia or RPC connection failed.",
        }

    on_chain_hash = on_chain["case_data_hash"].lower()
    is_encrypted = bool(case_data.get("encrypted"))

    if not is_encrypted:
        # Legacy unencrypted case: direct local vs on-chain verification
        is_valid = (local_hash == on_chain_hash)
        return {
            "valid": is_valid,
            "case_number": case_number,
            "local_hash": local_hash,
            "on_chain_hash": on_chain_hash,
            "on_chain_cid": on_chain["ipfs_cid"],
            "submitter": on_chain["submitter"],
            "version": on_chain["version"],
            "timestamp": on_chain["timestamp"],
            "encrypted": False,
            "details": (
                "Cryptographic integrity verified: Local case findings match the Sepolia on-chain anchor (legacy unencrypted snapshot)."
                if is_valid else
                "Integrity failure: Local case data does not match the Sepolia on-chain anchor."
            ),
        }

    # Encrypted case verification flow:
    # 1. Download CID from IPFS
    cid = on_chain["ipfs_cid"]
    try:
        encrypted_bytes = download_file_from_ipfs(cid, timeout=15)
    except Exception as exc:
        return {
            "valid": False,
            "case_number": case_number,
            "local_hash": local_hash,
            "on_chain_hash": on_chain_hash,
            "on_chain_cid": cid,
            "submitter": on_chain["submitter"],
            "version": on_chain["version"],
            "timestamp": on_chain["timestamp"],
            "encrypted": True,
            "error": f"IPFS download failed: {exc}",
            "details": f"Failed to retrieve encrypted snapshot from IPFS gateway: {exc}",
        }

    # 2. Decrypt envelope
    try:
        decrypted_plain_bytes = decrypt_snapshot(encrypted_bytes, case_number)
    except CryptoError as exc:
        return {
            "valid": False,
            "case_number": case_number,
            "local_hash": local_hash,
            "on_chain_hash": on_chain_hash,
            "on_chain_cid": cid,
            "submitter": on_chain["submitter"],
            "version": on_chain["version"],
            "timestamp": on_chain["timestamp"],
            "encrypted": True,
            "error": str(exc),
            "details": f"Decryption failed: {exc}. Ensure CASE_ENCRYPTION_KEY in .env matches the key used during anchoring.",
        }

    # 3. Re-hash decrypted plaintext snapshot
    try:
        decrypted_obj = jsonlib.loads(decrypted_plain_bytes.decode("utf-8"))
        canonical_decrypted = case_manager._canonicalize_numbers(decrypted_obj)
        canonical_json = jsonlib.dumps(canonical_decrypted, sort_keys=True, separators=(",", ":"))
        decrypted_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest().lower()
    except Exception:
        decrypted_hash = hashlib.sha256(decrypted_plain_bytes).hexdigest().lower()

    # 4. Confirm all three match
    match_local_chain = (local_hash == on_chain_hash)
    match_ipfs_chain = (decrypted_hash == on_chain_hash)
    match_local_ipfs = (local_hash == decrypted_hash)

    all_matched = match_local_chain and match_ipfs_chain and match_local_ipfs

    if all_matched:
        details = (
            "Triple cryptographic integrity confirmed: Local case data, decrypted IPFS snapshot, "
            "and Sepolia on-chain anchor all match perfectly."
        )
    elif not match_ipfs_chain:
        details = "Integrity failure: Decrypted IPFS snapshot does not match the Sepolia on-chain anchor."
    elif not match_local_chain:
        details = "Integrity failure: Local case data does not match the Sepolia on-chain anchor."
    else:
        details = "Integrity failure: Local case data does not match the decrypted IPFS snapshot."

    return {
        "valid": all_matched,
        "case_number": case_number,
        "local_hash": local_hash,
        "on_chain_hash": on_chain_hash,
        "decrypted_hash": decrypted_hash,
        "on_chain_cid": cid,
        "submitter": on_chain["submitter"],
        "version": on_chain["version"],
        "timestamp": on_chain["timestamp"],
        "encrypted": True,
        "details": details,
    }


@app.post("/cases/{name}/load")
def load_case(name: str):
    case_data = case_manager.load_case(name)
    if not case_data:
        raise HTTPException(status_code=404, detail="Case not found.")
    clear_graph()
    load_case_edges(case_data["edges"])
    return {
        "status": "loaded",
        "name": case_data["name"],
        "case_number": case_data.get("case_number", "Legacy"),
        "edge_count": case_data["edge_count"],
        "start_wallet": case_data.get("start_wallet"),
        "blockchain_status": case_data.get("blockchain_status", "not_anchored"),
        "cid": case_data.get("cid"),
        "tx_hash": case_data.get("tx_hash"),
    }


@app.delete("/cases/{name}")
def delete_case(name: str):
    deleted = case_manager.delete_case(name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found.")
    return {"status": "deleted"}


@app.post("/certificate")
def issue_certificate(req: CertificateRequest):
    edges = get_graph_data()
    if not edges:
        raise HTTPException(status_code=400, detail="Nothing to certify — the graph is empty.")

    hub_data = get_hub_wallets()
    fanout_data = get_fanout_wallets()
    peel_data = get_peel_chains()
    round_data = get_round_number_transactions()
    circular_data = get_circular_flows()
    sanctioned = {addr for addr, _ in check_sanctions(get_all_wallet_addresses())}
    risk_rows = compute_wallet_risk(hub_data, fanout_data, peel_data, round_data, circular_data,
                                     sanctioned_addresses=sanctioned)
    wallets_count, txs_count = get_summary_stats()
    start_wallet = req.start_wallet or edges[0][0]

    payload = {
        "start_wallet": start_wallet,
        "wallets_traced": wallets_count,
        "transactions_mapped": txs_count,
        "hub_wallets": hub_data[:10],
        "fanout_wallets": fanout_data[:10],
        "peel_chains": [(w, m, p) for w, m, p in peel_data[:10]],
        "round_number_txs": round_data[:10],
        "circular_flows": circular_data[:10],
        "sanctions_matches": list(sanctioned),
        "risk_summary": [(w, s, sc) for w, s, sc in risk_rows[:10]],
    }

    prev_hash, _ = get_last_certificate()
    prev_hash = prev_hash or "GENESIS"
    new_hash = compute_certificate_hash(payload, prev_hash)
    created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    store_certificate(new_hash, prev_hash, start_wallet, created_at)

    return {
        "certificate_hash": new_hash,
        "previous_hash": prev_hash,
        "created_at": created_at,
        "payload": payload,
        "verification_note": "To verify: POST this exact object to /certificate/verify."
    }


@app.post("/certificate/verify")
def verify_cert(req: CertificateVerifyRequest):
    is_valid = verify_certificate(req.payload, req.previous_hash, req.certificate_hash)
    return {"valid": is_valid}


@app.get("/report")
def report(start_wallet: Optional[str] = None):
    wallet = start_wallet or "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
    output_path = "investigation_report.pdf"
    generate_report(wallet, output_path=output_path)
    return FileResponse(output_path, media_type="application/pdf", filename="investigation_report.pdf")


@app.post("/report/publish")
def publish_report(req: PublishReportRequest):
    """Generate the PDF report, upload it to IPFS via Pinata, and store the
    investigation hash + IPFS CID on the Sepolia testnet via the
    BlockTraceRegistry smart contract.

    Returns the investigation hash, CID, gateway URL, and Sepolia tx info.
    Failures are handled gracefully:
      - If Pinata fails → returns an error, no on-chain tx attempted.
      - If the on-chain tx fails → CID is still returned with an error message.
      - If the hash is already on-chain → returns the CID without re-submitting.
    """
    # --- 1. Determine start wallet ---
    edges = get_graph_data()
    if not edges:
        raise HTTPException(status_code=400, detail="Nothing to publish — the graph is empty.")
    start_wallet = req.start_wallet or edges[0][0]

    # --- 2. Compute the investigation hash (reuse certificate logic) ---
    hub_data = get_hub_wallets()
    fanout_data = get_fanout_wallets()
    peel_data = get_peel_chains()
    round_data = get_round_number_transactions()
    circular_data = get_circular_flows()
    sanctioned = {addr for addr, _ in check_sanctions(get_all_wallet_addresses())}
    risk_rows = compute_wallet_risk(hub_data, fanout_data, peel_data, round_data, circular_data,
                                     sanctioned_addresses=sanctioned)
    wallets_count, txs_count = get_summary_stats()

    payload = {
        "start_wallet": start_wallet,
        "wallets_traced": wallets_count,
        "transactions_mapped": txs_count,
        "hub_wallets": hub_data[:10],
        "fanout_wallets": fanout_data[:10],
        "peel_chains": [(w, m, p) for w, m, p in peel_data[:10]],
        "round_number_txs": round_data[:10],
        "circular_flows": circular_data[:10],
        "sanctions_matches": list(sanctioned),
        "risk_summary": [(w, s, sc) for w, s, sc in risk_rows[:10]],
    }

    prev_hash, _ = get_last_certificate()
    prev_hash = prev_hash or "GENESIS"
    investigation_hash = compute_certificate_hash(payload, prev_hash)

    # --- 3. Generate the PDF ---
    import tempfile
    pdf_path = os.path.join(tempfile.gettempdir(), "blocktrace_publish_report.pdf")
    generate_report(start_wallet, output_path=pdf_path)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # --- 4. Upload to Pinata (IPFS) ---
    try:
        pinata_result = upload_pdf_to_pinata(
            pdf_bytes,
            filename=f"BlockTrace_Report_{start_wallet[:10]}.pdf",
            investigation_id=investigation_hash[:16],
        )
    except (PinataUploadError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"IPFS upload failed: {exc}")

    cid = pinata_result["cid"]
    gateway_url = pinata_result["gateway_url"]

    # --- 5. Store on Sepolia ---
    tx_hash = None
    block_number = None
    explorer_url = None
    chain_error = None

    # Check if hash is already on-chain before attempting
    if is_hash_on_chain(investigation_hash):
        chain_error = "This investigation hash is already recorded on-chain. The CID was still uploaded to IPFS."
    else:
        try:
            chain_result = store_record_on_chain(investigation_hash, cid)
            tx_hash = chain_result["tx_hash"]
            block_number = chain_result["block_number"]
            explorer_url = chain_result["explorer_url"]
        except (BlockchainServiceError, ValueError) as exc:
            chain_error = f"On-chain storage failed: {exc}"

    response = {
        "investigation_hash": investigation_hash,
        "cid": cid,
        "gateway_url": gateway_url,
        "tx_hash": tx_hash,
        "block_number": block_number,
        "explorer_url": explorer_url,
    }
    if chain_error:
        response["chain_error"] = chain_error

    return response


MAX_REPORT_SIZE = 25 * 1024 * 1024  # 25 MB cap


def extract_hash_from_pdf(pdf_bytes: bytes) -> Optional[str]:
    """Attempts to extract a 64-hex investigation/certificate hash from raw PDF bytes or streams."""
    import re
    import zlib
    raw_text = pdf_bytes.decode("latin1", errors="ignore")

    # 1. Look for explicit keyword labels in raw text
    m = re.search(r"(?:Certificate|Investigation)\s*Hash[:\s]+(?:<[^>]+>)?\s*([0-9a-fA-F]{64})", raw_text, re.IGNORECASE)
    if m:
        return m.group(1).lower()

    # 2. Look inside compressed streams
    for match in re.finditer(rb'stream\r?\n', pdf_bytes):
        start = match.end()
        end = pdf_bytes.find(b'endstream', start)
        if end > start:
            stream_data = pdf_bytes[start:end].strip()
            try:
                decomp = zlib.decompress(stream_data).decode('latin1', errors='ignore')
                m_decomp = re.search(r"(?:Certificate|Investigation)\s*Hash[:\s]+(?:<[^>]+>)?\s*([0-9a-fA-F]{64})", decomp, re.IGNORECASE)
                if m_decomp:
                    return m_decomp.group(1).lower()
                all_hex = re.findall(r"\b([0-9a-fA-F]{64})\b", decomp)
                if all_hex:
                    return all_hex[0].lower()
            except Exception:
                pass

    # 3. Fallback: match any 64-hex string in raw content
    all_raw = re.findall(r"\b([0-9a-fA-F]{64})\b", raw_text)
    if all_raw:
        return all_raw[0].lower()

    return None


@app.post("/api/report/verify")
@app.post("/report/verify")
async def verify_report(
    file: UploadFile = File(...),
    investigation_hash: Optional[str] = Form(None)
):
    """Public, read-only verification of a forensic report PDF against Sepolia blockchain and IPFS.

    Validates:
      - Valid PDF document (checks %PDF magic header)
      - File size cap (25 MB max)
      - Valid 64-hex investigation hash (or auto-extracted from PDF)

    Fetches the on-chain record from Sepolia BlockTraceRegistry.
    Downloads the archived report from IPFS via PINATA_GATEWAY.
    Compares the SHA-256 of the uploaded file against the on-chain IPFS artifact.
    """
    if not file:
        raise HTTPException(status_code=400, detail="A PDF file is required for verification.")

    uploaded_bytes = await file.read(MAX_REPORT_SIZE + 1)
    if len(uploaded_bytes) > MAX_REPORT_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds the 25 MB limit.")

    if len(uploaded_bytes) < 4 or not uploaded_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Invalid file type. The file must be a valid PDF document (missing %PDF header).")

    # Hash normalization & fallback extraction
    target_hash = (investigation_hash or "").strip().lower().removeprefix("0x")
    if not target_hash:
        extracted = extract_hash_from_pdf(uploaded_bytes)
        if extracted:
            target_hash = extracted
        else:
            raise HTTPException(
                status_code=400,
                detail="Investigation hash was not provided and could not be automatically detected in the PDF text. Please enter the 64-character hash."
            )

    if len(target_hash) != 64 or not all(c in "0123456789abcdef" for c in target_hash):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid investigation hash '{target_hash}'. Must be exactly 64 hexadecimal characters."
        )

    # 1. Query on-chain record from Sepolia
    try:
        record = get_report_record(target_hash)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to query Sepolia blockchain: {exc}")

    if not record:
        return {
            "status": "not_found",
            "investigation_hash": target_hash,
            "message": "No on-chain record found for this investigation hash on Sepolia."
        }

    cid = record["ipfs_cid"]
    submitter = record["submitter"]
    ts = record["timestamp"]
    contract_addr = record.get("contract_address") or os.getenv("CONTRACT_ADDRESS")
    explorer_url = record.get("explorer_address_url") or f"https://sepolia.etherscan.io/address/{contract_addr}"

    try:
        timestamp_utc = datetime.fromtimestamp(ts, timezone.utc).isoformat()
    except Exception:
        timestamp_utc = str(ts)

    # 2. Download from IPFS gateway
    configured_gw = (os.getenv("PINATA_GATEWAY") or "https://gateway.pinata.cloud").strip().rstrip("/")
    if not configured_gw.startswith("http://") and not configured_gw.startswith("https://"):
        configured_gw = f"https://{configured_gw}"
    primary_gateway_url = f"{configured_gw}/ipfs/{cid}"

    # Try configured gateway, then public fallbacks if necessary
    download_urls = [
        primary_gateway_url,
        f"https://gateway.pinata.cloud/ipfs/{cid}",
        f"https://ipfs.io/ipfs/{cid}",
        f"https://cloudflare-ipfs.com/ipfs/{cid}"
    ]

    stored_bytes = None
    last_download_error = None

    headers = {}
    jwt = os.getenv("PINATA_JWT")
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"

    for gw_url in download_urls:
        try:
            req_headers = headers if ("mypinata.cloud" in gw_url or "pinata.cloud" in gw_url) else {}
            resp = requests.get(gw_url, headers=req_headers, stream=True, timeout=15)
            if resp.status_code == 200:
                chunks = []
                total = 0
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        chunks.append(chunk)
                        total += len(chunk)
                        if total > MAX_REPORT_SIZE:
                            last_download_error = "File on IPFS exceeds 25 MB size cap."
                            chunks = None
                            break
                if chunks is not None:
                    stored_bytes = b"".join(chunks)
                    break
            else:
                last_download_error = f"Gateway HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            last_download_error = "Gateway request timed out (15s)"
        except Exception as err:
            last_download_error = str(err)

    if stored_bytes is None:
        return {
            "status": "unavailable",
            "message": f"Could not retrieve file from IPFS gateways: {last_download_error}",
            "investigation_hash": target_hash,
            "ipfs_cid": cid,
            "gateway_url": primary_gateway_url,
            "submitter": submitter,
            "timestamp_utc": timestamp_utc,
            "contract_address": contract_addr,
            "explorer_url": explorer_url,
        }

    # 3. Compute SHA-256 digests
    uploaded_sha256 = hashlib.sha256(uploaded_bytes).hexdigest()
    stored_sha256 = hashlib.sha256(stored_bytes).hexdigest()

    is_authentic = (uploaded_sha256.lower() == stored_sha256.lower())

    return {
        "status": "authentic" if is_authentic else "tampered",
        "uploaded_sha256": uploaded_sha256,
        "stored_sha256": stored_sha256,
        "ipfs_cid": cid,
        "gateway_url": primary_gateway_url,
        "submitter": submitter,
        "timestamp_utc": timestamp_utc,
        "contract_address": contract_addr,
        "explorer_url": explorer_url,
        "investigation_hash": target_hash,
    }
