"""
Pure business logic for BlockTrace — deliberately has NO Streamlit or Neo4j imports,
so it can be unit tested in isolation without a live database or web server.

app.py should import from this module rather than redefining these functions.
"""


def short(addr):
    """Shortens a wallet address for display, e.g. 0x098B716B... -> 0x098B716…6E96"""
    return addr[:8] + "…" + addr[-6:]


def risk_tier(score):
    """Maps a raw signal count to a human-readable, honest confidence tier.
    3+ signals = High, 2 = Medium, 0-1 = Low. Never implies certainty.
    Note: a direct sanctions-list match overrides this and is handled separately
    as 'Critical' — that is a verified fact, not a heuristic score."""
    if score >= 3:
        return "High", "high"
    elif score == 2:
        return "Medium", "medium"
    else:
        return "Low", "low"


def compute_wallet_risk(hub_data, fanout_data, peel_data, round_data, circular_data,
                         hub_threshold=10, sanctioned_addresses=None):
    """Combines all five detection signals per wallet into a simple, honest confidence tier.

    hub_data:      list of (address, total_txs)
    fanout_data:   list of (address, distinct_recipients)
    peel_data:     list of (address, main_amount, peel_amount)
    round_data:    list of (from_addr, to_addr, value)   -- signal attributed to from_addr
    circular_data: list of (address, hops)
    sanctioned_addresses: optional set of addresses directly on a sanctions list.
        A sanctions match is added as its own named signal ('OFAC Sanctioned') alongside the
        heuristic ones — it does not silently boost the score without being visible.

    Addresses are matched case-insensitively throughout (blockchain addresses are not
    case-sensitive), while the display casing shown to the user is preserved from
    whichever source first introduced that address.

    Returns a list of (address, [signal_names], score), sorted by score desc then address.
    """
    def index_by_lower(pairs):
        """Returns {lowercased_address: original_cased_address} for a list of (addr, *rest)."""
        return {p[0].lower(): p[0] for p in pairs}

    hub_lower = {addr.lower() for addr, c in hub_data if c >= hub_threshold}
    fanout_idx = index_by_lower(fanout_data)
    peel_idx = index_by_lower(peel_data)
    round_idx = {frm.lower(): frm for frm, to, v in round_data}
    circular_idx = index_by_lower(circular_data)
    hub_idx = index_by_lower(hub_data)
    sanctioned_idx = {a.lower(): a for a in (sanctioned_addresses or set())}
    sanctioned_lower = set(sanctioned_idx)

    all_lower_addrs = (
        hub_lower | set(fanout_idx) | set(peel_idx) | set(round_idx) | set(circular_idx) | sanctioned_lower
    )

    # Pick one canonical display casing per address, preferring whichever source has it.
    canonical = {}
    for idx in (hub_idx, fanout_idx, peel_idx, round_idx, circular_idx, sanctioned_idx):
        for lower_addr, cased_addr in idx.items():
            canonical.setdefault(lower_addr, cased_addr)

    rows = []
    for lower_addr in all_lower_addrs:
        display_addr = canonical[lower_addr]
        signals = []
        if lower_addr in sanctioned_lower:
            signals.append("OFAC Sanctioned")
        if lower_addr in hub_lower:
            signals.append("Hub Activity")
        if lower_addr in fanout_idx:
            signals.append("Fan-Out")
        if lower_addr in peel_idx:
            signals.append("Peel Chain")
        if lower_addr in round_idx:
            signals.append("Round-Number Sender")
        if lower_addr in circular_idx:
            signals.append("Circular Flow")
        rows.append((display_addr, signals, len(signals)))

    rows.sort(key=lambda r: (-r[2], r[0]))
    return rows


def describe_scope(scope):
    """One line saying what a trace covered, e.g. "Transactions 2022-03-23 to 2022-03-30 ·
    oldest first · up to 15 per wallet · 2 hops · Ethereum". Returns None without a scope."""
    if not scope:
        return None
    cap = scope.get("tx_per_wallet")
    order = "oldest first" if scope.get("sort") == "asc" else "newest first"
    start, end = scope.get("from_date"), scope.get("to_date")
    if start or end:
        parts = [f"Transactions {start or 'start'} to {end or 'today'}", order]
        if cap:
            parts.append(f"up to {cap} per wallet")
    else:
        parts = [f"All dates ({'oldest' if scope.get('sort') == 'asc' else 'newest'} {cap} per wallet)"]
    if scope.get("hops"):
        hops = scope["hops"]
        parts.append(f"{hops} hop" if hops == 1 else f"{hops} hops")
    if scope.get("chain"):
        parts.append(scope["chain"])
    if scope.get("incident_date"):
        parts.append(f"incident {scope['incident_date']}")
    # Scopes from before the option existed fetched internal transfers.
    if scope.get("include_internal", True):
        parts.append("normal + internal transfers")
    else:
        parts.append("normal transactions only")
    return " · ".join(parts)


def describe_data_quality(quality):
    """The "Data quality" line, e.g. "Normal 7 (3 with ETH, 4 zero-value hidden) · Internal off
    · Failed skipped 1". Mirrored by describeDataQuality() in the frontend."""
    if not quality:
        return None

    def zero_part(zero):
        if not zero:
            return ""
        return f", {zero} zero-value {'shown' if quality.get('show_zero_value') else 'hidden'}"

    normal = quality.get("normal_stored") or 0
    with_eth = quality.get("normal_with_eth") or 0
    parts = [f"Normal {normal} ({with_eth} with ETH{zero_part(normal - with_eth)})"]

    internal = quality.get("internal_stored") or 0
    if quality.get("internal_counted"):
        parts.append(f"Internal {internal}")
    elif internal:
        parts.append(f"Internal off ({internal} stored, not counted)")
    else:
        parts.append("Internal off")

    if quality.get("failed_skipped") is not None:
        parts.append(f"Failed skipped {quality['failed_skipped']}")
    if quality.get("capped_wallets"):
        parts.append(f"Capped wallets {quality['capped_wallets']}")
    return " · ".join(parts)


def describe_cap(limited_wallets):
    """The dossier's warning when the per-wallet transaction cap cut a trace short."""
    if not limited_wallets:
        return None
    return f"Cap reached for {len(limited_wallets)} wallets; results are a sample, not the full history."


def build_narrative(start_wallet, wallets_count, txs_count, hub_data, fanout_data, peel_data,
                     round_data=None, circular_data=None, risk_rows=None):
    """Builds a plain-English summary from detection results. Uses cautious, non-absolute
    language throughout — flags are heuristic indicators, never presented as proof."""
    paragraphs = []

    paragraphs.append(
        f"This investigation traced <span class='tc-mono'>{short(start_wallet)}</span> across "
        f"<strong>{wallets_count} wallets</strong> and <strong>{txs_count} transactions</strong>, "
        f"following the flow of funds outward through the network."
    )

    if risk_rows:
        top_wallet, top_signals, top_score = risk_rows[0]
        if top_score >= 2:
            tier_label, _ = risk_tier(top_score)
            paragraphs.append(
                f"Wallet <span class='tc-mono'>{short(top_wallet)}</span> matched "
                f"<strong>{top_score} independent detection signals</strong> "
                f"({', '.join(top_signals)}) — placing it in the <strong>{tier_label} confidence</strong> tier, "
                f"the strongest overlap of indicators found in this trace so far."
            )

    if hub_data:
        top_hub, top_hub_count = hub_data[0]
        paragraphs.append(
            f"The most active wallet in this network, <span class='tc-mono'>{short(top_hub)}</span>, "
            f"was involved in <strong>{top_hub_count} transactions</strong> — a level of activity that often "
            f"marks either an exchange, a service, or a key point where funds converge or get redistributed."
        )

    if fanout_data:
        top_fanout, recipients = fanout_data[0]
        paragraphs.append(
            f"Wallet <span class='tc-mono'>{short(top_fanout)}</span> sent funds to "
            f"<strong>{recipients} distinct wallets</strong>. Splitting funds across many recipients like this "
            f"is a pattern commonly associated with attempts to obscure a money trail — though it can also "
            f"reflect ordinary exchange or payroll-style activity, so it is flagged as a signal, not a conclusion."
        )

    if peel_data:
        top_wallet, main_amt, peel_amt = peel_data[0]
        pct = (peel_amt / main_amt * 100) if main_amt else 0
        # Peel remainders are tiny by definition, so one decimal place would print "0.0%".
        if pct >= 1:
            pct_text = f"about {pct:.1f}%"
        elif pct >= 0.01:
            pct_text = f"about {pct:.2g}%"
        else:
            pct_text = "less than 0.01%"
        paragraphs.append(
            f"Wallet <span class='tc-mono'>{short(top_wallet)}</span> forwarded <strong>{main_amt:.4f} ETH</strong> "
            f"while retaining only <strong>{peel_amt:.4f} ETH</strong> ({pct_text}). This \"peel chain\" "
            f"shape — passing on the bulk of funds while keeping a small remainder — matches a technique "
            f"documented in known money-laundering cases."
        )

    if round_data:
        rf, rt, rv = round_data[0]
        paragraphs.append(
            f"A transfer of exactly <strong>{rv:.0f} ETH</strong> was sent from "
            f"<span class='tc-mono'>{short(rf)}</span> to <span class='tc-mono'>{short(rt)}</span>. "
            f"Round, whole-number amounts like this are statistically uncommon in organic activity and "
            f"can indicate scripted or automated movement of funds."
        )

    if circular_data:
        cw, chops = circular_data[0]
        paragraphs.append(
            f"Wallet <span class='tc-mono'>{short(cw)}</span> shows a circular flow — funds sent from this "
            f"wallet eventually return to it after {chops} hops. This pattern can indicate wash trading "
            f"or an attempt to simulate legitimate circulation of funds."
        )

    if not any([hub_data, fanout_data, peel_data, round_data, circular_data]):
        paragraphs.append(
            "No hub, fan-out, peel-chain, round-number, or circular-flow patterns were detected in the "
            "traced data so far. Expanding to more hops may reveal additional structure."
        )

    return paragraphs


# ---------------- Sanctions screening ----------------
#
# IMPORTANT: this is a small, manually-curated demonstration list — NOT a live feed.
# It only contains addresses independently verified (at time of writing) as CURRENTLY
# listed on the U.S. Treasury OFAC Specially Designated Nationals (SDN) list.
#
# A worked example of why a static list is risky: Tornado Cash's associated addresses
# were OFAC-sanctioned in August 2022, but a U.S. Court of Appeals ruled OFAC exceeded
# its authority, and Treasury formally lifted those sanctions in March 2025. A hardcoded
# list that still flagged Tornado Cash today would itself be spreading false information.
#
# So the list is not hand-maintained: data/sanctions_ofac.json is a dated snapshot of every
# EVM address on the OFAC SDN list, regenerated from scratch by scripts/update_sanctions.py
# (which drops delisted addresses) and committed, so the server needs no network at startup.
# A 0x address listed under any EVM currency is treated as sanctioned on every EVM chain
# BlockTrace supports (Ethereum, BNB Chain, Polygon) — it is the same account on each.
#
# Manual entries below add richer context for addresses we describe elsewhere in the app;
# their fields override the snapshot's for the same address.

import json
import os as _os

OFAC_SNAPSHOT_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "sanctions_ofac.json")

MANUAL_SANCTIONED_ADDRESSES = {
    "0x098b716b8aaf21512996dc57eb0615e2383e2f96": {
        "name": "Ronin Bridge Hacker (Lazarus Group)",
        "authority": "U.S. Treasury OFAC",
        "note": "Sanctioned April 2022 following the $600M Ronin Bridge exploit."
    },
}


def load_sanctions(snapshot_path=OFAC_SNAPSHOT_PATH, manual=None):
    """Merges the OFAC snapshot with the manual entries. Returns (addresses, metadata).

    A missing or unreadable snapshot is not fatal: screening falls back to the manual
    entries alone, and the metadata says no snapshot was loaded."""
    manual = MANUAL_SANCTIONED_ADDRESSES if manual is None else manual
    meta = {"source_url": None, "fetched_at": None, "list_publication_date": None, "count": 0}
    snapshot_addresses = {}
    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        raw = snapshot.get("addresses")
        if not isinstance(raw, dict):
            raise ValueError("snapshot has no address map")
        snapshot_addresses = {addr.lower(): dict(entry) for addr, entry in raw.items() if isinstance(entry, dict)}
        meta.update(
            source_url=snapshot.get("source_url"),
            fetched_at=snapshot.get("fetched_at"),
            list_publication_date=snapshot.get("list_publication_date"),
            count=len(snapshot_addresses),
        )
    except (OSError, ValueError, AttributeError):
        snapshot_addresses = {}

    merged = snapshot_addresses
    for addr, entry in manual.items():
        merged[addr.lower()] = {**merged.get(addr.lower(), {}), **entry}
    return merged, meta


SANCTIONED_ADDRESSES, SANCTIONS_META = load_sanctions()


def describe_sanctions_snapshot(meta=None):
    """One line naming the snapshot date and size, for the UI and the PDF dossier."""
    meta = SANCTIONS_META if meta is None else meta
    if not meta.get("list_publication_date"):
        return "OFAC list snapshot unavailable; only built-in entries were checked."
    return f"OFAC list snapshot: {meta['list_publication_date']}, {meta['count']} addresses"


def check_sanctions(wallet_addresses):
    """Cross-references a list/set of wallet addresses against the sanctions list.
    Case-insensitive. Returns a list of (address, entry_dict) for every distinct
    sanctioned address, in first-seen order — an address listed twice (or in two
    letter cases) is reported once."""
    matches = []
    seen = set()
    for addr in wallet_addresses:
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        entry = SANCTIONED_ADDRESSES.get(key)
        if entry:
            matches.append((addr, entry))
    return matches


def unique_rows(rows):
    """Drops repeated detection rows keyed on their wallet address (first column,
    case-insensitive), keeping the first. A safety net for report tables."""
    seen = set()
    result = []
    for row in rows:
        key = row[0].lower() if isinstance(row[0], str) else row[0]
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


# ---------------- Verifiable investigation certificate ----------------
#
# Produces a tamper-evident "certificate" for a given investigation: a SHA-256 hash of
# the investigation's findings, chained to the hash of the previous certificate (like a
# minimal hash-chain / blockchain-style ledger). Anyone holding the certificate JSON can
# later recompute the hash from its contents and confirm it matches — proving the
# recorded findings have not been altered since the certificate was issued, without
# needing to trust BlockTrace's server or database.

import hashlib
import json


def _canonicalize_numbers(obj):
    """Recursively normalizes every numeric value to a float before hashing.

    Why this is necessary: JavaScript has no separate integer/float type. When a
    certificate payload round-trips through any JS-based client (a browser frontend,
    or even Swagger UI's own request/response editor), a Python float like 5.0 can
    silently become the JSON integer 5. Without this normalization, that harmless
    round-trip would produce a completely different SHA-256 hash and make every
    legitimate certificate fail verification. Applying this same normalization both
    when a certificate is issued and when it's verified makes the hash immune to
    that int/float ambiguity, regardless of which language or library touched the
    payload in between.
    """
    if isinstance(obj, bool):
        return obj  # bool is technically an int subclass in Python; leave as-is
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _canonicalize_numbers(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize_numbers(v) for v in obj]
    return obj


def compute_certificate_hash(payload, prev_hash):
    """payload: a JSON-serializable dict describing the investigation's findings.
    prev_hash: the hash of the previous certificate in the chain (or 'GENESIS' for the first).
    Returns a hex SHA-256 digest. Deterministic: same payload + same prev_hash always
    produces the same hash, and changing either changes the hash completely."""
    canonical_payload = _canonicalize_numbers(payload)
    canonical = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    combined = f"{prev_hash}|{canonical}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def verify_certificate(payload, prev_hash, claimed_hash):
    """Recomputes the hash from the payload + prev_hash and checks it matches the
    claimed hash. Returns True if the certificate is intact/unmodified, False if it
    has been tampered with (or the payload/prev_hash don't match what was certified)."""
    return compute_certificate_hash(payload, prev_hash) == claimed_hash


# ---------------- Known entity labels ----------------
#
# A small, manually-verified starter set of labeled addresses, so the graph shows
# human-readable context ("Ronin Bridge Hacker") instead of just raw hex. Extend this
# dict with any address you have independently verified — never guess or assume.

KNOWN_ENTITIES = {
    "0x098b716b8aaf21512996dc57eb0615e2383e2f96": "Ronin Bridge Hacker (Lazarus Group)",
    "0xc8a65fadf0e0ddaf421f28feab69bf6e2e589963": "Poly Network Hacker",
    "0x629e7da20197a5429d30da36e77d06cdf796b71a": "Wormhole Network Exploiter",
}


def get_entity_label(address):
    """Returns a human-readable label for a known address, or None if unlabeled."""
    return KNOWN_ENTITIES.get(address.lower())

