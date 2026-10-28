import streamlit as st
import os
import time
import hashlib
import requests
from dotenv import load_dotenv

# Ensure environment variables from .env strictly override any cached process environment
load_dotenv(override=True)

from neo4j import GraphDatabase
from pyvis.network import Network
import streamlit.components.v1 as components
from report_generator import generate_report
from logic import (
    short, risk_tier, compute_wallet_risk, build_narrative,
    check_sanctions, get_entity_label, compute_certificate_hash, verify_certificate
)
import case_manager

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"

# Etherscan's v2 API serves multiple EVM chains through the same key via the
# 'chainid' parameter. This gives genuine multi-chain support without needing
# separate API keys or a completely different data source per chain.
CHAIN_OPTIONS = {
    "Ethereum": 1,
    "BNB Smart Chain": 56,
    "Polygon": 137,
}

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

st.set_page_config(page_title="BlockTrace", layout="wide")

# ---------------- Curated example cases (verified, publicly documented) ----------------

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

# ---------------- Branding CSS ----------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg: #0A0E17;
    --surface: #131A2B;
    --border: #223047;
    --accent: #00E5A0;
    --danger: #FF6B6B;
    --text: #E6ECF5;
    --muted: #8291AB;
    --peel: #4DA6FF;
    --round: #FFC107;
    --circular: #BA68FF;
}

html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif;
}

[data-testid="stSidebar"] {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--border);
}

h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; letter-spacing: -0.01em; }

.tc-hero {
    display: flex; align-items: center; gap: 14px;
    padding: 18px 0 6px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 22px;
}
.tc-logo {
    width: 42px; height: 42px; border-radius: 10px;
    background: linear-gradient(135deg, var(--accent), #0090FF);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 18px; color: #0A0E17;
}
.tc-title { font-family: 'Space Grotesk', sans-serif; font-size: 26px; font-weight: 700; color: var(--text); margin: 0; }
.tc-tagline { font-family: 'Inter', sans-serif; font-size: 13px; color: var(--muted); margin: 0; }

.tc-section-desc {
    color: var(--muted); font-size: 12px; margin: -6px 0 12px 0; line-height: 1.5;
}

.tc-card {
    background: var(--surface); border: 1px solid var(--border); border-left: 3px solid transparent;
    border-radius: 10px; padding: 10px 12px; margin-bottom: 7px;
    display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 4px;
}
.tc-card-hub { border-left-color: var(--accent); }
.tc-card-fanout { border-left-color: var(--danger); }
.tc-card-peel { border-left-color: var(--peel); }
.tc-card-round { border-left-color: var(--round); }
.tc-card-circular { border-left-color: var(--circular); }
.tc-card-risk-low { border-left-color: var(--accent); }
.tc-card-risk-medium { border-left-color: var(--round); }
.tc-card-risk-high { border-left-color: var(--danger); }

.tc-addr { font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: var(--text); word-break: break-all; }
.tc-risk-signals { color: var(--muted); font-size: 10.5px; margin-top: 3px; }
.tc-badge {
    font-family: 'Inter', sans-serif; font-size: 11px; font-weight: 600;
    padding: 3px 9px; border-radius: 20px; white-space: nowrap;
}
.tc-badge-hub { background: rgba(0,229,160,0.12); color: var(--accent); }
.tc-badge-fanout { background: rgba(255,107,107,0.12); color: var(--danger); }
.tc-badge-peel { background: rgba(0,144,255,0.14); color: var(--peel); }
.tc-badge-round { background: rgba(255,193,7,0.14); color: var(--round); }
.tc-badge-circular { background: rgba(186,104,255,0.16); color: var(--circular); }
.tc-badge-risk-low { background: rgba(0,229,160,0.12); color: var(--accent); }
.tc-badge-risk-medium { background: rgba(255,193,7,0.16); color: var(--round); }
.tc-badge-risk-high { background: rgba(255,107,107,0.16); color: var(--danger); }

.tc-empty {
    background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
    padding: 32px; text-align: center; margin: 20px 0;
}
.tc-empty h3 { margin-top: 0; }
.tc-case-desc { color: var(--muted); font-size: 13.5px; max-width: 560px; margin: 8px auto 20px auto; }

.tc-narrative {
    background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--accent);
    border-radius: 10px; padding: 18px 20px; margin: 16px 0;
}
.tc-narrative p { font-size: 14px; line-height: 1.6; color: var(--text); margin: 0 0 10px 0; }
.tc-narrative p:last-child { margin-bottom: 0; }
.tc-narrative .tc-disclaimer { color: var(--muted); font-size: 12px; font-style: italic; margin-top: 12px; }
.tc-narrative .tc-mono { font-family: 'JetBrains Mono', monospace; font-size: 12.5px; background: rgba(0,229,160,0.08); padding: 1px 5px; border-radius: 4px; }

.tc-section-title {
    display: flex; align-items: center; gap: 8px; margin: 22px 0 2px 0;
}
.tc-section-title h3 { font-size: 17px !important; margin: 0; }

.stButton>button {
    background: var(--accent) !important; color: #0A0E17 !important; border: none !important;
    font-weight: 600 !important; border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------- Header ----------------

st.markdown("""
<div class="tc-hero">
  <div class="tc-logo">TC</div>
  <div>
    <p class="tc-title">BlockTrace</p>
    <p class="tc-tagline">Explainable blockchain crime investigation</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------- Etherscan + Neo4j helpers ----------------

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
            continue  # skip malformed value fields rather than storing garbage

        # Sanity cap: total ETH supply is ~120 million, so any single transaction
        # claiming more than 1 million ETH is certainly corrupted/malformed data,
        # not a real transfer. Skip it rather than let it pollute detection results.
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


def expand_from_wallet(start_wallet, hops=2, tx_per_wallet=15, progress_callback=None, chainid=1):
    visited = set()
    current_layer = {start_wallet}
    with driver.session(database=NEO4J_DATABASE) as session:
        for hop in range(hops):
            next_layer = set()
            for wallet in current_layer:
                if wallet in visited:
                    continue
                visited.add(wallet)
                if progress_callback:
                    progress_callback(f"Hop {hop+1}: fetching {wallet[:12]}...")
                txs = fetch_transactions(wallet, limit=tx_per_wallet, chainid=chainid)
                new_wallets = load_transactions(session, txs)
                next_layer.update(new_wallets)
                time.sleep(0.25)
            current_layer = next_layer - visited
    return len(visited)

# ---------------- Analysis queries ----------------

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
    """One row per wallet — its strongest (highest main-amount) peel-chain match."""
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
    """Flags transactions with suspiciously 'clean' amounts (e.g. exactly 1.0, 5.0, 10.0 ETH).
    Organic transfers rarely land on exact whole numbers; round amounts often indicate
    scripted, automated, or scam-related payouts."""
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
    """Detects wallets where funds eventually flow back to their own address within a
    few hops — a pattern associated with wash trading or laundering via fake circulation."""
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


def expand_until_found(source, destination, max_hops=6, tx_per_wallet=15,
                        progress_callback=None, chainid=1):
    """Like expand_from_wallet, but stops early as soon as the destination wallet is
    discovered — no point expanding the whole network if we only care about one route.
    Returns (wallets_visited, found: bool)."""
    destination_lower = destination.lower()

    existing = {a.lower() for a in get_all_wallet_addresses()}
    if destination_lower in existing:
        return 0, True  # already in the graph from a previous fetch — nothing to do

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
                if progress_callback:
                    progress_callback(f"Hop {hop+1}: fetching {wallet[:12]}...")
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


def get_paths_between(source, destination, max_hops=6, limit=10):
    """Finds directed paths from source to destination already present in the graph
    (source must have SENT, directly or through intermediaries, to destination).
    Case-insensitive address matching. Returns a list of dicts: {wallets, rels, hops},
    shortest paths first, capped at `limit` distinct paths."""
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


def clear_graph():
    """Wipes all wallets/transactions from the database. Used before loading a saved
    case, so cases don't get mixed together in the same graph view."""
    with driver.session(database=NEO4J_DATABASE) as session:
        session.run("MATCH (n:Wallet) DETACH DELETE n")


def load_case_edges(edges):
    """Loads a previously-saved case's edges directly into Neo4j, without calling the
    Etherscan API again. edges: list of dicts with 'from', 'to', 'value' keys."""
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


def get_last_certificate():
    """Returns (hash, created_at) of the most recently issued certificate, or
    (None, None) if no certificate has been issued yet (start of the chain)."""
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


def render_section(icon, title, description, rows, card_class, badge_class,
                    addr_fn, badge_fn, top_n=5, empty_text="No matches detected."):
    """Renders a detection section with a top-N preview and a 'show all' expander
    (clicking it again collapses it back — that's the show-less behavior)."""
    st.markdown(f'<div class="tc-section-title"><h3>{icon} {title}</h3></div>', unsafe_allow_html=True)
    st.markdown(f'<p class="tc-section-desc">{description}</p>', unsafe_allow_html=True)

    if not rows:
        st.caption(empty_text)
        return

    def render_rows(subset):
        for row in subset:
            st.markdown(f"""
            <div class="tc-card {card_class}">
              <span class="tc-addr">{addr_fn(row)}</span>
              <span class="tc-badge {badge_class}">{badge_fn(row)}</span>
            </div>
            """, unsafe_allow_html=True)

    render_rows(rows[:top_n])

    if len(rows) > top_n:
        with st.expander(f"Show all {len(rows)} matches"):
            render_rows(rows)


def render_risk_section(risk_rows, top_n=5):
    st.markdown('<div class="tc-section-title"><h3>🎯 Wallet Risk Overview</h3></div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="tc-section-desc">Wallets scored by how many independent detection signals they '
        'triggered. More overlapping signals suggest stronger — though still not conclusive — grounds '
        'for review. 🟢 Low = 1 signal · 🟡 Medium = 2 signals · 🔴 High = 3+ signals.</p>',
        unsafe_allow_html=True
    )

    if not risk_rows:
        st.caption("No wallets triggered any detection signal in this dataset.")
        return

    def render_rows(subset):
        for wallet, signals, score in subset:
            tier_label, tier_class = risk_tier(score)
            st.markdown(f"""
            <div class="tc-card tc-card-risk-{tier_class}">
              <div>
                <div class="tc-addr">{wallet}</div>
                <div class="tc-risk-signals">{" · ".join(signals)}</div>
              </div>
              <span class="tc-badge tc-badge-risk-{tier_class}">{tier_label} · {score} signals</span>
            </div>
            """, unsafe_allow_html=True)

    render_rows(risk_rows[:top_n])

    if len(risk_rows) > top_n:
        with st.expander(f"Show all {len(risk_rows)} flagged wallets"):
            render_rows(risk_rows)

# ---------------- Session state for wallet input ----------------

if "wallet_input" not in st.session_state:
    st.session_state.wallet_input = ""
if "path_mode" not in st.session_state:
    st.session_state.path_mode = False
if "path_result" not in st.session_state:
    st.session_state.path_result = []

# ---------------- Sidebar: curated cases ----------------

st.sidebar.header("📁 Example Investigations")
st.sidebar.caption("Verified, publicly documented cases — load one to explore instantly.")

for case_name, case_info in CURATED_CASES.items():
    if st.sidebar.button(f"▶ {case_name}", key=f"case_{case_name}"):
        st.session_state.wallet_input = case_info["address"]
        status = st.sidebar.empty()
        def progress(msg):
            status.info(msg)
        with st.spinner(f"Loading {case_name}..."):
            visited_count = expand_from_wallet(case_info["address"], hops=2, tx_per_wallet=15, progress_callback=progress, chainid=case_info.get("chainid", 1))
        status.success(f"Loaded — {visited_count} wallets traced.")
        st.rerun()

st.sidebar.markdown("---")

# ---------------- Sidebar: expand controls ----------------

st.sidebar.header("🔎 Investigate a Wallet")
selected_chain = st.sidebar.selectbox("Chain", list(CHAIN_OPTIONS.keys()), index=0)
new_wallet = st.sidebar.text_input("Wallet address to expand from", value=st.session_state.wallet_input, key="wallet_input_box")
hops = st.sidebar.slider("Hops deep", 1, 3, 2)
tx_per_wallet = st.sidebar.slider("Transactions per wallet", 5, 30, 15)

if st.sidebar.button("🚀 Expand Graph"):
    if new_wallet.strip() == "":
        st.sidebar.error("Enter a wallet address first.")
    else:
        status = st.sidebar.empty()
        def progress(msg):
            status.info(msg)
        with st.spinner("Fetching and expanding..."):
            visited_count = expand_from_wallet(
                new_wallet.strip(), hops=hops, tx_per_wallet=tx_per_wallet,
                progress_callback=progress, chainid=CHAIN_OPTIONS[selected_chain]
            )
        status.success(f"Done — visited {visited_count} wallets.")
        st.rerun()

st.sidebar.markdown("---")
wallet_filter = st.sidebar.text_input("Filter displayed graph by address (optional)")

st.sidebar.markdown("---")
st.sidebar.header("🎯 Trace a Specific Path")
st.sidebar.caption("Show only the route(s) connecting two specific wallets — not the whole surrounding network.")

path_source = st.sidebar.text_input("From wallet (source)", key="path_source")
path_destination = st.sidebar.text_input("To wallet (destination)", key="path_destination")
path_max_hops = st.sidebar.slider("Max hops to search", 1, 6, 4, key="path_max_hops")

if st.sidebar.button("🔍 Find Path"):
    if not path_source.strip() or not path_destination.strip():
        st.sidebar.error("Enter both a source and destination wallet.")
    else:
        status = st.sidebar.empty()
        def path_progress(msg):
            status.info(msg)
        with st.spinner("Expanding network until destination is found (or hop limit reached)..."):
            visited_count, found = expand_until_found(
                path_source.strip(), path_destination.strip(),
                max_hops=path_max_hops, tx_per_wallet=15,
                progress_callback=path_progress, chainid=CHAIN_OPTIONS[selected_chain]
            )
        if not found:
            status.warning(
                f"Destination not reached within {path_max_hops} hops (visited {visited_count} new wallets). "
                "Try increasing the hop limit."
            )
            st.session_state.path_mode = False
        else:
            paths = get_paths_between(path_source.strip(), path_destination.strip(), max_hops=path_max_hops)
            if not paths:
                status.warning("Both wallets are in the graph, but no directed path connects them "
                                "within the hop limit (funds may only flow the other direction, or not at all).")
                st.session_state.path_mode = False
            else:
                status.success(f"Found {len(paths)} path(s), shortest is {paths[0]['hops']} hop(s).")
                st.session_state.path_mode = True
                st.session_state.path_result = paths
                st.session_state.path_source_label = path_source.strip()
                st.session_state.path_dest_label = path_destination.strip()
        st.rerun()

if st.session_state.get("path_mode"):
    if st.sidebar.button("❌ Clear Path Filter"):
        st.session_state.path_mode = False
        st.session_state.path_result = []
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("💼 Investigation Cases")
st.sidebar.caption("Save the current graph as a named case, or reload one later without re-fetching from the API.")

case_number_input = st.sidebar.text_input("Case number (e.g. BT-2026-0001, optional)", key="case_number_input")
case_name_input = st.sidebar.text_input("Case name", key="case_name_input")
if st.sidebar.button("💾 Save Current Case"):
    if case_name_input.strip() == "":
        st.sidebar.error("Enter a case name first.")
    else:
        current_edges = get_graph_data()
        if not current_edges:
            st.sidebar.error("Nothing to save — the graph is empty.")
        else:
            start_addr = new_wallet.strip() if new_wallet.strip() else current_edges[0][0]
            try:
                saved_res = case_manager.save_case(
                    case_name_input.strip(),
                    start_addr,
                    current_edges,
                    case_number=case_number_input.strip() or None
                )
                st.sidebar.success(f"Saved case [{saved_res['case_number']}] '{saved_res['name']}' ({len(current_edges)} edges).")
            except (ValueError, case_manager.DuplicateCaseNumberError) as err:
                st.sidebar.error(f"Save failed: {err}")

saved_cases = case_manager.list_cases()
if saved_cases:
    case_labels = [f"[{c.get('case_number', 'Legacy')}] {c['name']} ({c['edge_count']} edges)" for c in saved_cases]
    selected_case_idx = st.sidebar.selectbox("Load a saved case", range(len(saved_cases)),
                                              format_func=lambda i: case_labels[i])
    if st.sidebar.button("📂 Load Selected Case"):
        case_data = case_manager.load_case(saved_cases[selected_case_idx]["name"])
        if case_data:
            with st.spinner("Clearing current graph and loading saved case..."):
                clear_graph()
                load_case_edges(case_data["edges"])
            st.session_state.wallet_input = case_data.get("start_wallet", "")
            st.sidebar.success(f"Loaded '[{case_data.get('case_number', 'Legacy')}] {case_data['name']}' — {case_data['edge_count']} edges restored.")
            st.rerun()
else:
    st.sidebar.caption("No saved cases yet.")

st.sidebar.markdown("---")
st.sidebar.header("📄 Investigation Report")

if st.sidebar.button("Generate PDF Report"):
    with st.spinner("Generating report..."):
        report_wallet = new_wallet.strip() if new_wallet.strip() else "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
        generate_report(report_wallet, output_path="investigation_report.pdf")

    with open("investigation_report.pdf", "rb") as f:
        pdf_bytes = f.read()

    st.sidebar.success("Report generated!")
    st.sidebar.download_button(
        label="⬇️ Download Report",
        data=pdf_bytes,
        file_name="investigation_report.pdf",
        mime="application/pdf"
    )

# ---------------- Main: graph visualization ----------------

st.subheader("Transaction Graph")

if st.session_state.get("path_mode") and st.session_state.get("path_result"):
    # Union all edges across the returned paths, deduplicated
    seen_edges = set()
    path_edges = []
    for path in st.session_state.path_result:
        for rel in path["rels"]:
            key = (rel["from"], rel["to"], rel["value"])
            if key not in seen_edges:
                seen_edges.add(key)
                path_edges.append(key)
    edges = path_edges
    st.info(
        f"🎯 Showing only path(s) from `{short(st.session_state.path_source_label)}` to "
        f"`{short(st.session_state.path_dest_label)}` — {len(st.session_state.path_result)} path(s) found, "
        f"shortest is {st.session_state.path_result[0]['hops']} hop(s). "
        f"Use 'Clear Path Filter' in the sidebar to return to the full graph."
    )
else:
    edges = get_graph_data()


if not edges:
    st.markdown(f"""
    <div class="tc-empty">
      <h3>Start exploring</h3>
      <p class="tc-case-desc">
        Load one of the {len(CURATED_CASES)} verified example cases from the sidebar, or paste
        any Ethereum wallet address into "Investigate a Wallet" to trace it yourself.
      </p>
    </div>
    """, unsafe_allow_html=True)
else:
    net = Network(height="600px", width="100%", bgcolor="#0A0E17", font_color="#E6ECF5", directed=True)
    added_nodes = set()
    for from_addr, to_addr, value in edges:
        if wallet_filter and wallet_filter.lower() not in from_addr.lower() and wallet_filter.lower() not in to_addr.lower():
            continue
        for addr in (from_addr, to_addr):
            if addr in added_nodes:
                continue
            entity = get_entity_label(addr)
            sanctioned_match = check_sanctions([addr])
            if sanctioned_match:
                node_color = "#FF6B6B"
                node_label = f"🚫 {entity or addr[:10] + '...'}"
            elif entity:
                node_color = "#FFC107"
                node_label = f"⭐ {entity}"
            else:
                node_color = "#00E5A0"
                node_label = addr[:10] + "..."
            net.add_node(addr, label=node_label, color=node_color)
            added_nodes.add(addr)
        net.add_edge(from_addr, to_addr, value=value, title=f"{value:.4f} ETH")

    net.save_graph("graph.html")
    with open("graph.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=620)

# ---------------- Load detection data once (used by narrative + sections) ----------------

hub_data = get_hub_wallets()
fanout_data = get_fanout_wallets()
peel_data = get_peel_chains()
round_data = get_round_number_transactions()
circular_data = get_circular_flows()
sanctions_matches = check_sanctions(get_all_wallet_addresses())
sanctioned_addr_set = {addr for addr, entry in sanctions_matches}
risk_rows = compute_wallet_risk(
    hub_data, fanout_data, peel_data, round_data, circular_data,
    sanctioned_addresses=sanctioned_addr_set
)

# ---------------- Plain-English narrative ----------------

if edges:
    st.subheader("📖 What this trail shows")

    wallets_count, txs_count = get_summary_stats()
    narrative_start = new_wallet.strip() if new_wallet.strip() else (edges[0][0] if edges else "")

    paragraphs = build_narrative(
        narrative_start, wallets_count, txs_count,
        hub_data, fanout_data, peel_data, round_data, circular_data, risk_rows
    )

    narrative_html = "<div class='tc-narrative'>"
    for p in paragraphs:
        narrative_html += f"<p>{p}</p>"
    narrative_html += (
        "<p class='tc-disclaimer'>These patterns are heuristic indicators derived from public "
        "blockchain data, not proof of wrongdoing. Review by a qualified investigator is recommended "
        "before drawing conclusions.</p>"
    )
    narrative_html += "</div>"

    st.markdown(narrative_html, unsafe_allow_html=True)

# ---------------- Sanctions screening (direct match, not a heuristic) ----------------

if edges:
    st.markdown('<div class="tc-section-title"><h3>🚫 Sanctions Screening</h3></div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="tc-section-desc">Direct matches against a verified list of addresses currently '
        'on the U.S. Treasury OFAC sanctions list. Unlike the heuristics below, this is a factual match, '
        'not a statistical inference — but the underlying list must be kept current (see disclaimer).</p>',
        unsafe_allow_html=True
    )
    if sanctions_matches:
        for addr, entry in sanctions_matches:
            st.markdown(f"""
            <div class="tc-card" style="border-left-color:#FF6B6B;">
              <div>
                <div class="tc-addr">{addr}</div>
                <div class="tc-risk-signals">{entry['name']} — {entry['authority']}: {entry['note']}</div>
              </div>
              <span class="tc-badge" style="background:rgba(255,107,107,0.2);color:#FF6B6B;">SANCTIONED</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No wallets in this trace match the (small, manually-verified) sanctions list on file.")

# ---------------- Wallet risk overview (full width) ----------------

render_risk_section(risk_rows)

# ---------------- Detection technique grid ----------------

grid_row1_a, grid_row1_b, grid_row1_c = st.columns(3)

with grid_row1_a:
    render_section(
        "🏦", "Hub Wallets",
        "Unusually high transaction counts — often exchanges or key redistribution points.",
        hub_data, "tc-card-hub", "tc-badge-hub",
        addr_fn=lambda r: r[0],
        badge_fn=lambda r: f"{r[1]} txs",
        empty_text="No data yet."
    )

with grid_row1_b:
    render_section(
        "⚠️", "High Fan-Out",
        "Wallets sending funds to many addresses — a common way to split and obscure a trail.",
        fanout_data, "tc-card-fanout", "tc-badge-fanout",
        addr_fn=lambda r: r[0],
        badge_fn=lambda r: f"→ {r[1]} wallets",
        empty_text="No fan-out patterns detected."
    )

with grid_row1_c:
    render_section(
        "🔗", "Peel Chains",
        "Wallets forwarding most funds while keeping a small remainder — a documented laundering pattern.",
        peel_data, "tc-card-peel", "tc-badge-peel",
        addr_fn=lambda r: r[0],
        badge_fn=lambda r: f"{r[1]:.4f} → {r[2]:.4f} ETH",
        empty_text="No peel chain patterns detected."
    )

grid_row2_a, grid_row2_b = st.columns(2)

with grid_row2_a:
    render_section(
        "🔵", "Round-Number Transactions",
        "Exact whole-ETH transfers are statistically uncommon organically and often indicate scripted activity.",
        round_data, "tc-card-round", "tc-badge-round",
        addr_fn=lambda r: f"{short(r[0])} → {short(r[1])}",
        badge_fn=lambda r: f"{r[2]:.0f} ETH",
        empty_text="No round-number transactions detected."
    )

with grid_row2_b:
    render_section(
        "🟣", "Circular Flows",
        "Funds that loop back to their own origin wallet — a pattern associated with wash trading.",
        circular_data, "tc-card-circular", "tc-badge-circular",
        addr_fn=lambda r: r[0],
        badge_fn=lambda r: f"loops in {r[1]} hops",
        empty_text="No circular flows detected."
    )

# ---------------- Verifiable investigation certificate ----------------

if edges:
    st.markdown('<div class="tc-section-title"><h3>🔐 Verification Certificate</h3></div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="tc-section-desc">Generates a cryptographic hash of this investigation\'s current '
        'findings, chained to the previous certificate. Anyone holding the certificate file can later '
        're-verify it matches — without needing to trust this server, this database, or this session.</p>',
        unsafe_allow_html=True
    )

    cert_col1, cert_col2 = st.columns(2)

    with cert_col1:
        st.markdown("**Issue a new certificate**")
        if st.button("🔐 Generate Certificate for Current Findings"):
            payload = {
                "start_wallet": narrative_start if edges else "",
                "wallets_traced": wallets_count if edges else 0,
                "transactions_mapped": txs_count if edges else 0,
                "hub_wallets": hub_data[:10],
                "fanout_wallets": fanout_data[:10],
                "peel_chains": [(w, m, p) for w, m, p in peel_data[:10]],
                "round_number_txs": round_data[:10],
                "circular_flows": circular_data[:10],
                "sanctions_matches": [addr for addr, _ in sanctions_matches],
                "risk_summary": [(w, s, sc) for w, s, sc in risk_rows[:10]],
            }
            prev_hash, _ = get_last_certificate()
            prev_hash = prev_hash or "GENESIS"
            new_hash = compute_certificate_hash(payload, prev_hash)
            created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            store_certificate(new_hash, prev_hash, narrative_start, created_at)

            certificate_json = {
                "certificate_hash": new_hash,
                "previous_hash": prev_hash,
                "created_at": created_at,
                "payload": payload,
                "verification_note": "To verify: recompute SHA-256 of '{previous_hash}|<canonical JSON of payload>' "
                                      "and confirm it equals certificate_hash. If it does not match, the recorded "
                                      "findings have been altered since this certificate was issued."
            }
            import json as _json
            cert_bytes = _json.dumps(certificate_json, indent=2, default=str).encode("utf-8")

            st.success(f"Certificate issued: `{new_hash[:16]}...`")
            st.download_button(
                "⬇️ Download Certificate",
                data=cert_bytes,
                file_name=f"tracechain_certificate_{new_hash[:12]}.json",
                mime="application/json"
            )

    with cert_col2:
        st.markdown("**Verify an existing certificate**")
        uploaded_cert = st.file_uploader("Upload a certificate JSON file", type=["json"], key="cert_upload")
        if uploaded_cert is not None:
            import json as _json
            try:
                cert_data = _json.loads(uploaded_cert.read())
                is_valid = verify_certificate(
                    cert_data["payload"], cert_data["previous_hash"], cert_data["certificate_hash"]
                )
                if is_valid:
                    st.success("✅ Certificate is intact — the recorded findings match the certified hash.")
                else:
                    st.error("❌ Certificate does NOT match — the recorded findings appear to have been altered.")
            except (KeyError, ValueError) as e:
                st.error(f"Could not parse certificate file: {e}")

