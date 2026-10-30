"""
Neo4j read queries shared by the API (graph, summary, Findings) and the PDF dossier,
so every surface counts transactions the same way.

THE COUNTING RULE — a SENT edge is a "counted" transaction when:
  * it is an ETH transfer: a normal transaction (kind "normal", or no kind on edges
    written before kinds existed) or an internal transfer (kind "internal"); and
  * it moved ETH (value > 0), unless the viewer turned on "Show 0-ETH contract calls".
Failed transactions are not in the graph at all unless a trace was run with
include_failed, and the date window was applied when the trace was fetched, so the
rule needs no date or status test. Wallets are counted when they touch at least one
counted edge, so a wallet reachable only through hidden edges disappears too.

Sanctions screening is deliberately NOT filtered by this rule: a sanctioned wallet is
reported even if its only link is a hidden 0-ETH call (see all_wallet_addresses).

Every function takes an open session and reads the workspace and the 0-ETH option
from the request context unless they are passed explicitly.
"""

from datetime import datetime, timezone

import view_options
import workspace

COUNTED_KINDS = ["normal", "internal"]


def counted(rel="r"):
    """Cypher predicate for the counting rule on relationship variable `rel`.
    Needs the $kinds and $show_zero parameters (see _params)."""
    return f"(coalesce({rel}.kind, 'normal') IN $kinds AND ($show_zero OR {rel}.value > 0))"


def _params(ws=None, show_zero=None, **extra):
    return {
        "ws": ws or workspace.current(),
        "show_zero": view_options.show_zero() if show_zero is None else show_zero,
        "kinds": COUNTED_KINDS,
        **extra,
    }


def summary_stats(session, ws=None, show_zero=None):
    """(wallets, transactions) under the counting rule."""
    record = session.run(
        f"""
        MATCH (a:Wallet {{ws: $ws}})-[r:SENT]->(b:Wallet)
        WHERE {counted()}
        WITH collect(DISTINCT a) + collect(DISTINCT b) AS ends, count(r) AS txs
        UNWIND ends AS w
        RETURN count(DISTINCT w) AS wallets, txs
        """,
        **_params(ws, show_zero),
    ).single()
    if not record:
        return 0, 0
    return record["wallets"], record["txs"]


def data_quality(session, ws=None, show_zero=None):
    """Edge counts behind the "Data quality" box: everything stored, what the counting
    rule shows, and what it hides."""
    params = _params(ws, show_zero)
    record = session.run(
        f"""
        MATCH (:Wallet {{ws: $ws}})-[r:SENT]->(:Wallet)
        RETURN count(r) AS stored,
               sum(CASE WHEN {counted()} THEN 1 ELSE 0 END) AS shown,
               sum(CASE WHEN r.value = 0 THEN 1 ELSE 0 END) AS zero_value,
               sum(CASE WHEN r.kind = 'internal' AND {counted()} THEN 1 ELSE 0 END) AS internal_shown,
               sum(CASE WHEN coalesce(r.failed, false) THEN 1 ELSE 0 END) AS failed_stored
        """,
        **params,
    ).single()
    stored = record["stored"] if record else 0
    zero_value = (record["zero_value"] or 0) if record else 0
    return {
        "edges_stored": stored,
        "transactions_shown": (record["shown"] or 0) if record else 0,
        "zero_value_edges": zero_value,
        "zero_value_hidden": 0 if params["show_zero"] else zero_value,
        "internal_shown": (record["internal_shown"] or 0) if record else 0,
        "failed_included": (record["failed_stored"] or 0) if record else 0,
        "show_zero_value": params["show_zero"],
    }


def graph_edges(session, limit=5000, ws=None, show_zero=None):
    """Counted edges, oldest first, with hash, timestamp and kind.
    Returns (edges, total_edges) so callers can say "showing N of M"."""
    params = _params(ws, show_zero, limit=limit)
    total = session.run(
        f"MATCH (:Wallet {{ws: $ws}})-[r:SENT]->(:Wallet) WHERE {counted()} RETURN count(r) AS c", **params
    ).single()["c"]
    result = session.run(
        f"""
        MATCH (a:Wallet {{ws: $ws}})-[r:SENT]->(b:Wallet)
        WHERE {counted()}
        RETURN a.address AS from_addr, b.address AS to_addr, r.value AS value,
               coalesce(r.tx_hash, r.hash) AS tx_hash, r.timestamp AS timestamp,
               coalesce(r.kind, 'normal') AS kind, coalesce(r.failed, false) AS failed
        ORDER BY toInteger(coalesce(r.timestamp, '0')) ASC, tx_hash ASC
        LIMIT $limit
        """,
        **params,
    )
    edges = [
        {
            "from": r["from_addr"], "to": r["to_addr"], "value": r["value"],
            "hash": r["tx_hash"], "timestamp": int(r["timestamp"]) if r["timestamp"] else None,
            "kind": r["kind"], "failed": r["failed"],
        }
        for r in result
    ]
    return edges, total


def data_window(session, ws=None, show_zero=None):
    record = session.run(
        f"""
        MATCH (:Wallet {{ws: $ws}})-[r:SENT]->(:Wallet)
        WHERE {counted()} AND r.timestamp IS NOT NULL
        WITH toInteger(r.timestamp) AS ts
        WHERE ts IS NOT NULL AND ts > 0
        RETURN min(ts) AS min_ts, max(ts) AS max_ts
        """,
        **_params(ws, show_zero),
    ).single()
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
    return {"data_window": None, "earliest_timestamp": None, "latest_timestamp": None,
            "first_date": None, "last_date": None}


def hub_wallets(session, limit=1000, ws=None, show_zero=None):
    result = session.run(
        f"""
        MATCH (w:Wallet {{ws: $ws}})-[r:SENT]-()
        WHERE {counted()}
        RETURN w.address AS wallet, count(r) AS total_txs
        ORDER BY total_txs DESC, wallet ASC LIMIT $limit
        """,
        **_params(ws, show_zero, limit=limit),
    )
    return [(r["wallet"], r["total_txs"]) for r in result]


def fanout_wallets(session, min_recipients=4, limit=1000, ws=None, show_zero=None):
    result = session.run(
        f"""
        MATCH (a:Wallet {{ws: $ws}})-[r:SENT]->(b:Wallet)
        WHERE {counted()}
        WITH a, count(DISTINCT b) AS distinct_recipients
        WHERE distinct_recipients >= $min_recipients
        RETURN a.address AS wallet, distinct_recipients
        ORDER BY distinct_recipients DESC, wallet ASC LIMIT $limit
        """,
        **_params(ws, show_zero, min_recipients=min_recipients, limit=limit),
    )
    return [(r["wallet"], r["distinct_recipients"]) for r in result]


def peel_chains(session, limit=1000, ws=None, show_zero=None):
    # The 0.001 ETH floor already excludes 0-ETH calls, so the toggle cannot change this.
    result = session.run(
        f"""
        MATCH (mid:Wallet {{ws: $ws}})-[r2:SENT]->(next1:Wallet)
        MATCH (mid)-[r3:SENT]->(next2:Wallet)
        WHERE elementId(next1) < elementId(next2) AND r2.value > 0.001 AND r3.value > 0.001
          AND {counted('r2')} AND {counted('r3')}
        WITH mid,
             CASE WHEN r2.value > r3.value THEN r2.value ELSE r3.value END AS bigger,
             CASE WHEN r2.value > r3.value THEN r3.value ELSE r2.value END AS smaller
        WHERE (smaller / bigger) < 0.15
        WITH mid, bigger, smaller
        ORDER BY bigger DESC
        WITH mid, collect({{main: bigger, peel: smaller}})[0] AS top_match
        RETURN mid.address AS wallet, top_match.main AS main_amount, top_match.peel AS peel_amount
        ORDER BY main_amount DESC
        LIMIT $limit
        """,
        **_params(ws, show_zero, limit=limit),
    )
    return [(r["wallet"], r["main_amount"], r["peel_amount"]) for r in result]


def round_number_transactions(session, min_value=1.0, limit=1000, ws=None, show_zero=None):
    """Whole-ETH transfers. Rows are distinct transactions (keyed on the edge), so two
    real transfers of the same amount between the same wallets are both listed."""
    result = session.run(
        f"""
        MATCH (a:Wallet {{ws: $ws}})-[r:SENT]->(b:Wallet)
        WHERE {counted()} AND r.value >= $min_value AND r.value = toInteger(r.value)
        RETURN a.address AS from_addr, b.address AS to_addr, r.value AS value
        ORDER BY r.value DESC, from_addr ASC, to_addr ASC
        LIMIT $limit
        """,
        **_params(ws, show_zero, min_value=min_value, limit=limit),
    )
    return [(r["from_addr"], r["to_addr"], r["value"]) for r in result]


def circular_flows(session, max_hops=4, limit=1000, ws=None, show_zero=None):
    result = session.run(
        f"""
        MATCH path = (a:Wallet {{ws: $ws}})-[:SENT*2..{int(max_hops)}]->(a)
        WHERE all(r IN relationships(path) WHERE {counted()})
        RETURN DISTINCT a.address AS wallet, length(path) AS hops
        ORDER BY hops ASC, wallet ASC
        LIMIT $limit
        """,
        **_params(ws, show_zero, limit=limit),
    )
    return [(r["wallet"], r["hops"]) for r in result]


def all_wallet_addresses(session, ws=None):
    """Every wallet in the workspace, hidden edges or not — used for sanctions screening."""
    result = session.run("MATCH (w:Wallet {ws: $ws}) RETURN w.address AS address", ws=ws or workspace.current())
    return [r["address"] for r in result]
