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
import re as re_module
from collections import defaultdict
from threading import Lock

import requests
from dotenv import load_dotenv

# Ensure environment variables from .env strictly override any cached process environment
load_dotenv(override=True)

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired
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
import workspace
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

# ==================== Public deployment mode ====================
PUBLIC_MODE = os.getenv("PUBLIC_MODE", "false").lower() == "true"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
ALLOW_EXT_ORIGINS = [o.strip() for o in os.getenv("ALLOW_EXTENSION_ORIGINS", "").split(",") if o.strip()]

# Aura silently drops idle connections, which surfaced as intermittent 500s
# ("Unable to retrieve routing information"). Recycle connections well before that
# and health-check any that sat idle before reusing them.
driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
    max_connection_lifetime=240,
    liveness_check_timeout=30,
    keep_alive=True,
)


class _RetryingSession:
    """Session wrapper that retries a query once on a fresh session when the
    connection turns out to be dead. Graph writes use MERGE, so a retry is safe."""

    def __init__(self):
        self._session = driver.session(database=NEO4J_DATABASE)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._session.close()

    def run(self, query, *args, **params):
        try:
            return self._session.run(query, *args, **params)
        except (ServiceUnavailable, SessionExpired):
            self._session.close()
            self._session = driver.session(database=NEO4J_DATABASE)
            return self._session.run(query, *args, **params)


def neo4j_session():
    return _RetryingSession()

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

# CORS: use CORS_ORIGINS env in public mode, allow all in local dev.
_cors_origins = CORS_ORIGINS + ALLOW_EXT_ORIGINS if PUBLIC_MODE else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(workspace.WorkspaceMiddleware)


@app.on_event("startup")
def _prepare_workspaces():
    """Index wallets by workspace and move pre-workspace data into "default"."""
    try:
        with neo4j_session() as session:
            session.run("CREATE INDEX wallet_ws_address IF NOT EXISTS FOR (w:Wallet) ON (w.ws, w.address)")
            session.run("MATCH (w:Wallet) WHERE w.ws IS NULL SET w.ws = $ws", ws=workspace.DEFAULT_WORKSPACE)
    except Exception as e:
        print(f"Workspace setup skipped: {e}")
    case_manager.migrate_legacy_cases()


# ==================== In-memory rate limiter ====================
from fastapi import Request
from fastapi.responses import JSONResponse

_rate_limit_store: dict = defaultdict(list)
_rate_limit_lock = Lock()
RATE_LIMIT = 120  # max requests (loading one case fires ~12 API calls)
RATE_WINDOW = 60  # per this many seconds

# Endpoints that spend the server wallet's Sepolia gas and Pinata storage get a much
# tighter budget, so nobody can drain the wallet now that the API is open to everyone.
ONCHAIN_RATE_LIMIT = 5
ONCHAIN_RATE_WINDOW = 3600
_ONCHAIN_PATH = re_module.compile(r"^(/api)?/(report/publish|cases/[^/]+/(anchor|reanchor))$")


def _check_rate_limit(key: str, limit: int = RATE_LIMIT, window: int = RATE_WINDOW) -> bool:
    """Returns True if the request is allowed, False if rate-limited."""
    now = time.time()
    with _rate_limit_lock:
        timestamps = _rate_limit_store[key]
        timestamps[:] = [t for t in timestamps if now - t < window]
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        return True


def _client_ip(request: Request) -> str:
    # Render sits behind Cloudflare, so request.client is the proxy and every visitor
    # would share one bucket. Prefer the Cloudflare-set header, then X-Forwarded-For.
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ==================== Rate-limit middleware (public deployment) ====================

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if PUBLIC_MODE and request.method != "OPTIONS" and request.url.path != "/health":
        ip = _client_ip(request)
        allowed = _check_rate_limit(ip)
        retry_after = RATE_WINDOW
        if allowed and request.method == "POST" and _ONCHAIN_PATH.match(request.url.path):
            allowed = _check_rate_limit(f"onchain:{ip}", ONCHAIN_RATE_LIMIT, ONCHAIN_RATE_WINDOW)
            retry_after = ONCHAIN_RATE_WINDOW
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait before retrying."},
                headers={"Retry-After": str(retry_after)},
            )
    response = await call_next(request)
    return response


# ==================== Generic error handler (suppress stack traces in public mode) ====================

@app.exception_handler(Exception)
async def _generic_exception_handler(request: Request, exc: Exception):
    if PUBLIC_MODE:
        # Log server-side for debugging but never expose internals to the client
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": "An internal error occurred."})
    # Local dev: let FastAPI show its default debug page
    raise exc


# ==================== Request/response models ====================

class ExpandRequest(BaseModel):
    wallet: str
    hops: int = Field(2, ge=1, le=3)
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    sort: Optional[str] = "desc"
    tx_per_wallet: int = Field(15, ge=5, le=30)
    chain: str = "Ethereum"


class PathRequest(BaseModel):
    source: str
    destination: str
    max_hops: int = Field(4, ge=1, le=6)
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    sort: Optional[str] = "desc"
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

def date_to_block(date_input, closest="after", chainid=1):
    default_block = 0 if closest == "after" else 99999999
    if not date_input:
        return default_block
    try:
        if isinstance(date_input, str):
            date_str = date_input.strip()
            if not date_str:
                return default_block
            if len(date_str) == 10 and date_str.count("-") == 2:
                dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if closest == "before":
                    dt = dt.replace(hour=23, minute=59, second=59)
                else:
                    dt = dt.replace(hour=0, minute=0, second=0)
            else:
                cleaned = date_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(cleaned)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
        elif hasattr(date_input, "year") and not hasattr(date_input, "hour"):
            dt = datetime(date_input.year, date_input.month, date_input.day, tzinfo=timezone.utc)
            if closest == "before":
                dt = dt.replace(hour=23, minute=59, second=59)
        elif hasattr(date_input, "timestamp"):
            dt = date_input
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            return default_block

        unix_ts = int(dt.timestamp())
        params = {
            "chainid": chainid,
            "module": "block",
            "action": "getblocknobytime",
            "timestamp": unix_ts,
            "closest": closest,
            "apikey": ETHERSCAN_API_KEY,
        }
        resp = requests.get(ETHERSCAN_URL, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("result"):
            return int(data["result"])
        return default_block
    except Exception:
        return default_block

def fetch_transactions(wallet_address, limit=15, chainid=1, startblock=0, endblock=99999999, sort="desc"):
    params = {
        "chainid": chainid, "module": "account", "action": "txlist",
        "address": wallet_address, "startblock": startblock, "endblock": endblock,
        "sort": sort, "apikey": ETHERSCAN_API_KEY
    }
    response = requests.get(ETHERSCAN_URL, params=params)
    data = response.json()
    if data.get("status") != "1":
        return [], False
    raw_txs = data.get("result", [])
    hit_limit = len(raw_txs) > limit
    return raw_txs[:limit], hit_limit


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
            MERGE (a:Wallet {address: $from_addr, ws: $ws})
            MERGE (b:Wallet {address: $to_addr, ws: $ws})
            MERGE (a)-[t:SENT {hash: $tx_hash}]->(b)
            SET t.value = $value_eth, t.timestamp = $timestamp
            """,
            ws=workspace.current(), from_addr=from_addr, to_addr=to_addr, tx_hash=tx["hash"],
            value_eth=value_eth, timestamp=tx["timeStamp"]
        )
        new_wallets.add(from_addr)
        new_wallets.add(to_addr)
    return new_wallets


def expand_from_wallet(start_wallet, hops=2, tx_per_wallet=15, chainid=1, startblock=0, endblock=99999999, sort="desc"):
    visited = set()
    current_layer = {start_wallet}
    limit_hit_wallets = []
    with neo4j_session() as session:
        for hop in range(hops):
            next_layer = set()
            for wallet in current_layer:
                if wallet in visited:
                    continue
                visited.add(wallet)
                txs, hit_limit = fetch_transactions(
                    wallet, limit=tx_per_wallet, chainid=chainid,
                    startblock=startblock, endblock=endblock, sort=sort
                )
                if hit_limit:
                    limit_hit_wallets.append(wallet)
                new_wallets = load_transactions(session, txs)
                next_layer.update(new_wallets)
                time.sleep(0.25)
            current_layer = next_layer - visited
    return len(visited), limit_hit_wallets


def expand_until_found(source, destination, max_hops=6, tx_per_wallet=15, chainid=1, startblock=0, endblock=99999999, sort="desc"):
    destination_lower = destination.lower()
    existing = {a.lower() for a in get_all_wallet_addresses()}
    if destination_lower in existing:
        return 0, True, []

    visited = set()
    current_layer = {source}
    found = False
    limit_hit_wallets = []
    with neo4j_session() as session:
        for hop in range(max_hops):
            next_layer = set()
            for wallet in current_layer:
                if wallet in visited:
                    continue
                visited.add(wallet)
                txs, hit_limit = fetch_transactions(
                    wallet, limit=tx_per_wallet, chainid=chainid,
                    startblock=startblock, endblock=endblock, sort=sort
                )
                if hit_limit:
                    limit_hit_wallets.append(wallet)
                new_wallets = load_transactions(session, txs)
                next_layer.update(new_wallets)
                if destination_lower in {w.lower() for w in new_wallets}:
                    found = True
                time.sleep(0.25)
            current_layer = next_layer - visited
            if found:
                break
    return len(visited), found, limit_hit_wallets


def get_graph_data(limit=300):
    with neo4j_session() as session:
        result = session.run(
            "MATCH (a:Wallet {ws: $ws})-[r:SENT]->(b:Wallet) RETURN a.address AS from_addr, b.address AS to_addr, r.value AS value LIMIT $limit",
            ws=workspace.current(), limit=limit
        )
        return [(r["from_addr"], r["to_addr"], r["value"]) for r in result]


def get_summary_stats():
    with neo4j_session() as session:
        result = session.run(
            "MATCH (w:Wallet {ws: $ws}) OPTIONAL MATCH (w)-[r:SENT]->() RETURN count(DISTINCT w) AS wallets, count(r) AS txs",
            ws=workspace.current()
        )
        record = result.single()
        return record["wallets"], record["txs"]


def get_data_window_stats():
    with neo4j_session() as session:
        result = session.run(
            """
            MATCH (:Wallet {ws: $ws})-[r:SENT]->()
            WHERE r.timestamp IS NOT NULL
            WITH toInteger(r.timestamp) AS ts
            WHERE ts IS NOT NULL AND ts > 0
            RETURN min(ts) AS min_ts, max(ts) AS max_ts
            """, ws=workspace.current()
        )
        record = result.single()
        if record and record["min_ts"] is not None and record["max_ts"] is not None:
            first_date = datetime.fromtimestamp(record["min_ts"], timezone.utc).strftime("%Y-%m-%d")
            last_date = datetime.fromtimestamp(record["max_ts"], timezone.utc).strftime("%Y-%m-%d")
            return {
                "data_window": f"Data window: {first_date} to {last_date} (UTC)",
                "earliest_timestamp": record["min_ts"],
                "latest_timestamp": record["max_ts"],
                "first_date": first_date,
                "last_date": last_date,
            }
        return {
            "data_window": None,
            "earliest_timestamp": None,
            "latest_timestamp": None,
            "first_date": None,
            "last_date": None,
        }


def get_hub_wallets(limit=1000):
    with neo4j_session() as session:
        result = session.run(
            """
            MATCH (w:Wallet {ws: $ws})-[r:SENT]-()
            RETURN w.address AS wallet, count(r) AS total_txs
            ORDER BY total_txs DESC LIMIT $limit
            """, ws=workspace.current(), limit=limit
        )
        return [(r["wallet"], r["total_txs"]) for r in result]


def get_fanout_wallets(min_recipients=4, limit=1000):
    with neo4j_session() as session:
        result = session.run(
            """
            MATCH (a:Wallet {ws: $ws})-[:SENT]->(b:Wallet)
            WITH a, count(DISTINCT b) AS distinct_recipients
            WHERE distinct_recipients >= $min_recipients
            RETURN a.address AS wallet, distinct_recipients
            ORDER BY distinct_recipients DESC LIMIT $limit
            """, ws=workspace.current(), min_recipients=min_recipients, limit=limit
        )
        return [(r["wallet"], r["distinct_recipients"]) for r in result]


def get_peel_chains(limit=1000):
    with neo4j_session() as session:
        result = session.run(
            """
            MATCH (mid:Wallet {ws: $ws})-[r2:SENT]->(next1:Wallet)
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
            """, ws=workspace.current(), limit=limit
        )
        return [(r["wallet"], r["main_amount"], r["peel_amount"]) for r in result]


def get_round_number_transactions(min_value=1.0, limit=1000):
    with neo4j_session() as session:
        result = session.run(
            """
            MATCH (a:Wallet {ws: $ws})-[r:SENT]->(b:Wallet)
            WHERE r.value >= $min_value AND r.value = toInteger(r.value)
            RETURN a.address AS from_addr, b.address AS to_addr, r.value AS value
            ORDER BY r.value DESC
            LIMIT $limit
            """, ws=workspace.current(), min_value=min_value, limit=limit
        )
        return [(r["from_addr"], r["to_addr"], r["value"]) for r in result]


def get_circular_flows(max_hops=4, limit=1000):
    with neo4j_session() as session:
        result = session.run(
            """
            MATCH path = (a:Wallet {ws: $ws})-[:SENT*2..%d]->(a)
            RETURN DISTINCT a.address AS wallet, length(path) AS hops
            ORDER BY hops ASC
            LIMIT $limit
            """ % max_hops, ws=workspace.current(), limit=limit
        )
        return [(r["wallet"], r["hops"]) for r in result]


def get_all_wallet_addresses():
    with neo4j_session() as session:
        result = session.run("MATCH (w:Wallet {ws: $ws}) RETURN w.address AS address", ws=workspace.current())
        return [r["address"] for r in result]


def clear_graph():
    with neo4j_session() as session:
        session.run("MATCH (n:Wallet {ws: $ws}) DETACH DELETE n", ws=workspace.current())


def load_case_edges(edges):
    with neo4j_session() as session:
        for i, e in enumerate(edges):
            synthetic_hash = hashlib.sha256(
                f"{e['from']}-{e['to']}-{e['value']}-{i}".encode()
            ).hexdigest()
            session.run(
                """
                MERGE (a:Wallet {address: $from_addr, ws: $ws})
                MERGE (b:Wallet {address: $to_addr, ws: $ws})
                MERGE (a)-[t:SENT {hash: $tx_hash}]->(b)
                SET t.value = $value_eth
                """,
                ws=workspace.current(), from_addr=e["from"], to_addr=e["to"], tx_hash=synthetic_hash, value_eth=e["value"]
            )


def get_paths_between(source, destination, max_hops=6, limit=10):
    with neo4j_session() as session:
        result = session.run(
            """
            MATCH (a:Wallet {ws: $ws}), (b:Wallet {ws: $ws})
            WHERE toLower(a.address) = toLower($source) AND toLower(b.address) = toLower($destination)
            MATCH p = (a)-[:SENT*1..%d]->(b)
            RETURN [n IN nodes(p) | n.address] AS wallets,
                   [r IN relationships(p) | {from: startNode(r).address, to: endNode(r).address, value: r.value}] AS rels,
                   length(p) AS hops
            ORDER BY hops ASC
            LIMIT $limit
            """ % max_hops,
            ws=workspace.current(), source=source, destination=destination, limit=limit
        )
        return [{"wallets": r["wallets"], "rels": r["rels"], "hops": r["hops"]} for r in result]


def get_last_certificate():
    with neo4j_session() as session:
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
    with neo4j_session() as session:
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
def root():
    """Lightweight root endpoint — same as /health but with a service label."""
    return {"status": "ok", "service": "BlockTrace API", "public_mode": PUBLIC_MODE}


@app.get("/health")
def health():
    """Fast health check with zero DB/network calls — used to wake Render free tier."""
    return {"status": "ok", "public_mode": PUBLIC_MODE}


@app.get("/contracts")
def contracts():
    """Returns smart contract addresses and Sepolia explorer links — no secrets."""
    return {
        "registry_contract": os.getenv("CONTRACT_ADDRESS", ""),
        "registry_explorer_url": f"https://sepolia.etherscan.io/address/{os.getenv('CONTRACT_ADDRESS', '')}",
        "case_contract": os.getenv("CASE_CONTRACT_ADDRESS", ""),
        "case_explorer_url": f"https://sepolia.etherscan.io/address/{os.getenv('CASE_CONTRACT_ADDRESS', '')}",
        "network": "Ethereum Sepolia (Chain ID 11155111)",
    }


@app.get("/sanctions/check")
def sanctions_check(address: str):
    """Public sanctions screening — looks up a single address against the built-in
    OFAC-based list. No Etherscan or Neo4j calls."""
    if not re_module.match(r'^0x[0-9a-fA-F]{40}$', address):
        raise HTTPException(
            status_code=400,
            detail="Invalid Ethereum address. Must be 0x followed by 40 hex characters.",
        )
    from logic import SANCTIONED_ADDRESSES
    normalized = address.lower()
    match = SANCTIONED_ADDRESSES.get(normalized)
    return {
        "address": address,
        "sanctioned": match is not None,
        "label": match.get("name") if match else None,
        "source": "built-in OFAC-based list",
        "note": "Indicator only; the list may be outdated. Verify with official OFAC sources.",
    }


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
    visited, limited = expand_from_wallet(info["address"], hops=2, tx_per_wallet=15, chainid=info["chainid"])
    dw = get_data_window_stats()
    note = f"Showing 15 of the wallet's transactions" if limited else None
    return {
        "wallets_visited": visited,
        "start_wallet": info["address"],
        "hit_limit": len(limited) > 0,
        "limit_note": note,
        "limited_wallets": limited,
        "data_window": dw["data_window"],
    }




@app.post("/expand")
def expand(req: ExpandRequest):
    chainid = _resolve_chainid(req.chain)
    startblock = date_to_block(req.from_date, "after", chainid) if req.from_date else 0
    endblock = date_to_block(req.to_date, "before", chainid) if req.to_date else 99999999
    sort_order = "asc" if (req.sort and req.sort.lower() in ("asc", "oldest", "oldest first")) else "desc"
    visited, limited = expand_from_wallet(
        req.wallet, hops=req.hops, tx_per_wallet=req.tx_per_wallet, chainid=chainid,
        startblock=startblock, endblock=endblock, sort=sort_order
    )
    dw = get_data_window_stats()
    note = f"Showing {req.tx_per_wallet} of the wallet's transactions" if limited else None
    return {
        "wallets_visited": visited,
        "start_wallet": req.wallet,
        "hit_limit": len(limited) > 0,
        "limit_note": note,
        "limited_wallets": limited,
        "data_window": dw["data_window"],
        "earliest_timestamp": dw["earliest_timestamp"],
        "latest_timestamp": dw["latest_timestamp"],
    }




@app.post("/clear")
def clear():
    clear_graph()
    return {"status": "cleared"}


@app.get("/summary")
def summary():
    wallets, txs = get_summary_stats()
    dw = get_data_window_stats()
    return {
        "wallets_traced": wallets,
        "transactions_mapped": txs,
        "data_window": dw["data_window"],
        "earliest_timestamp": dw["earliest_timestamp"],
        "latest_timestamp": dw["latest_timestamp"],
    }


@app.get("/data-window")
def data_window_endpoint():
    return get_data_window_stats()


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
    startblock = date_to_block(req.from_date, "after", chainid) if req.from_date else 0
    endblock = date_to_block(req.to_date, "before", chainid) if req.to_date else 99999999
    sort_order = "asc" if (req.sort and req.sort.lower() in ("asc", "oldest", "oldest first")) else "desc"
    visited, found, limited = expand_until_found(
        req.source, req.destination, max_hops=req.max_hops,
        tx_per_wallet=req.tx_per_wallet, chainid=chainid,
        startblock=startblock, endblock=endblock, sort=sort_order
    )
    limit_note = f"Showing {req.tx_per_wallet} of the wallet's transactions" if limited else None
    if not found:
        return {"found": False, "wallets_visited": visited, "paths": [], "hit_limit": len(limited) > 0, "limit_note": limit_note}

    paths = get_paths_between(req.source, req.destination, max_hops=req.max_hops)
    return {"found": len(paths) > 0, "wallets_visited": visited, "paths": paths, "hit_limit": len(limited) > 0, "limit_note": limit_note}


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
            "details": f"Decryption failed: {exc}",
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
    dw = get_data_window_stats()["data_window"]
    generate_report(wallet, output_path=output_path, data_window=dw)
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
    dw = get_data_window_stats()["data_window"]
    generate_report(start_wallet, output_path=pdf_path, data_window=dw)

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
