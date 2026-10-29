"""
Unit tests for logic.py — run with: pytest test_logic.py -v

These test the pure decision logic (risk scoring, narrative wording) using synthetic
data, with no live Neo4j or Etherscan connection required.
"""

import pytest
from logic import (
    short, risk_tier, compute_wallet_risk, build_narrative,
    check_sanctions, compute_certificate_hash, verify_certificate, get_entity_label
)

WALLET_A = "0x098B716B8Aaf21512996dC57EB0615e2383E2f96"
WALLET_B = "0x4e5b2e1dc63f6b91cb6cd759936495434c7e972f"
WALLET_C = "0xb66cd966670d962c227b3eaba30a872dbfb995db"


# ---------------- short() ----------------

def test_short_truncates_correctly():
    result = short(WALLET_A)
    assert result.startswith("0x098B71")
    assert result.endswith(WALLET_A[-6:])
    assert "…" in result


def test_short_is_much_shorter_than_original():
    assert len(short(WALLET_A)) < len(WALLET_A)


# ---------------- risk_tier() ----------------

@pytest.mark.parametrize("score,expected_label", [
    (0, "Low"),
    (1, "Low"),
    (2, "Medium"),
    (3, "High"),
    (5, "High"),
])
def test_risk_tier_boundaries(score, expected_label):
    label, _ = risk_tier(score)
    assert label == expected_label


# ---------------- compute_wallet_risk() ----------------

def test_wallet_matching_all_five_signals_is_high():
    hub_data = [(WALLET_A, 50)]
    fanout_data = [(WALLET_A, 10)]
    peel_data = [(WALLET_A, 2.0, 0.1)]
    round_data = [(WALLET_A, WALLET_B, 5.0)]
    circular_data = [(WALLET_A, 3)]

    rows = compute_wallet_risk(hub_data, fanout_data, peel_data, round_data, circular_data)

    assert len(rows) == 1
    wallet, signals, score = rows[0]
    assert wallet == WALLET_A
    assert score == 5
    assert set(signals) == {"Hub Activity", "Fan-Out", "Peel Chain", "Round-Number Sender", "Circular Flow"}
    label, _ = risk_tier(score)
    assert label == "High"


def test_wallet_matching_one_signal_is_low():
    hub_data = []
    fanout_data = [(WALLET_A, 5)]
    peel_data = []
    round_data = []
    circular_data = []

    rows = compute_wallet_risk(hub_data, fanout_data, peel_data, round_data, circular_data)

    assert len(rows) == 1
    wallet, signals, score = rows[0]
    assert score == 1
    assert signals == ["Fan-Out"]


def test_hub_below_threshold_does_not_count_as_signal():
    """A wallet with only 3 transactions should NOT count as 'hub' if threshold is 10 —
    otherwise nearly every wallet in a real graph would trivially score as hub-flagged."""
    hub_data = [(WALLET_A, 3)]
    rows = compute_wallet_risk(hub_data, [], [], [], [], hub_threshold=10)
    assert rows == []


def test_hub_at_or_above_threshold_counts():
    hub_data = [(WALLET_A, 10)]
    rows = compute_wallet_risk(hub_data, [], [], [], [], hub_threshold=10)
    assert len(rows) == 1
    assert rows[0][2] == 1


def test_no_signals_returns_empty_list():
    rows = compute_wallet_risk([], [], [], [], [])
    assert rows == []


def test_multiple_wallets_sorted_by_score_descending():
    hub_data = [(WALLET_A, 50), (WALLET_B, 50), (WALLET_C, 50)]
    fanout_data = [(WALLET_A, 10), (WALLET_B, 10)]
    peel_data = [(WALLET_A, 1.0, 0.05)]

    rows = compute_wallet_risk(hub_data, fanout_data, peel_data, [], [])

    scores = [r[2] for r in rows]
    assert scores == sorted(scores, reverse=True)
    assert rows[0][0] == WALLET_A  # highest score (3 signals) should be first
    assert rows[0][2] == 3


# ---------------- build_narrative() ----------------

def test_narrative_always_includes_intro_paragraph():
    paragraphs = build_narrative(WALLET_A, 100, 250, [], [], [], [], [], [])
    assert len(paragraphs) >= 1
    assert "100 wallets" in paragraphs[0]
    assert "250 transactions" in paragraphs[0]


def test_narrative_with_no_detections_says_so_honestly():
    paragraphs = build_narrative(WALLET_A, 10, 20, [], [], [], [], [], [])
    joined = " ".join(paragraphs)
    assert "No hub, fan-out, peel-chain" in joined


def test_narrative_never_states_certainty_language():
    """Guards against accidentally introducing absolute/accusatory claims like
    'is committing fraud' — the narrative should always hedge."""
    hub_data = [(WALLET_A, 50)]
    fanout_data = [(WALLET_A, 20)]
    peel_data = [(WALLET_A, 2.0, 0.1)]
    round_data = [(WALLET_A, WALLET_B, 5.0)]
    circular_data = [(WALLET_A, 3)]

    paragraphs = build_narrative(
        WALLET_A, 50, 100, hub_data, fanout_data, peel_data, round_data, circular_data,
        compute_wallet_risk(hub_data, fanout_data, peel_data, round_data, circular_data)
    )
    joined = " ".join(paragraphs).lower()

    forbidden_phrases = ["is laundering", "is committing", "is guilty", "proven", "confirmed fraud"]
    for phrase in forbidden_phrases:
        assert phrase not in joined, f"Narrative used overclaiming language: '{phrase}'"


def test_narrative_mentions_top_risk_wallet_when_score_is_high():
    hub_data = [(WALLET_A, 50)]
    fanout_data = [(WALLET_A, 20)]
    peel_data = [(WALLET_A, 2.0, 0.1)]
    risk_rows = compute_wallet_risk(hub_data, fanout_data, peel_data, [], [])

    paragraphs = build_narrative(WALLET_A, 50, 100, hub_data, fanout_data, peel_data, [], [], risk_rows)
    joined = " ".join(paragraphs)
    assert "independent detection signals" in joined
    assert "confidence" in joined.lower()


def test_narrative_omits_risk_mention_when_score_is_only_one():
    """A single-signal wallet shouldn't trigger the 'strongest overlap' sentence —
    that sentence is reserved for score >= 2."""
    fanout_data = [(WALLET_A, 20)]
    risk_rows = compute_wallet_risk([], fanout_data, [], [], [])

    paragraphs = build_narrative(WALLET_A, 50, 100, [], fanout_data, [], [], [], risk_rows)
    joined = " ".join(paragraphs)
    assert "independent detection signals" not in joined


# ---------------- check_sanctions() ----------------

def test_sanctions_match_found():
    matches = check_sanctions([WALLET_A])  # WALLET_A is the Ronin hacker address
    assert len(matches) == 1
    assert matches[0][0] == WALLET_A
    assert "Ronin" in matches[0][1]["name"]


def test_sanctions_no_match():
    matches = check_sanctions([WALLET_B, WALLET_C])
    assert matches == []


def test_sanctions_case_insensitive():
    matches = check_sanctions([WALLET_A.upper()])
    assert len(matches) == 1


def test_sanctions_empty_input():
    assert check_sanctions([]) == []


# ---------------- compute_wallet_risk() with sanctions ----------------

def test_sanctioned_wallet_gets_named_signal():
    rows = compute_wallet_risk([], [], [], [], [], sanctioned_addresses={WALLET_A})
    assert len(rows) == 1
    wallet, signals, score = rows[0]
    assert wallet == WALLET_A
    assert "OFAC Sanctioned" in signals
    assert score == 1


def test_sanctioned_wallet_combines_with_other_signals():
    fanout_data = [(WALLET_A, 10)]
    rows = compute_wallet_risk([], fanout_data, [], [], [], sanctioned_addresses={WALLET_A})
    assert len(rows) == 1
    wallet, signals, score = rows[0]
    assert set(signals) == {"OFAC Sanctioned", "Fan-Out"}
    assert score == 2


# ---------------- get_entity_label() ----------------

def test_known_entity_label_returned():
    label = get_entity_label(WALLET_A)
    assert label is not None
    assert "Ronin" in label


def test_unknown_address_returns_none():
    assert get_entity_label("0x0000000000000000000000000000000000dEaD") is None


# ---------------- Certificate hash-chain ----------------

def test_certificate_hash_is_deterministic():
    payload = {"wallet": WALLET_A, "count": 5}
    h1 = compute_certificate_hash(payload, "GENESIS")
    h2 = compute_certificate_hash(payload, "GENESIS")
    assert h1 == h2


def test_certificate_hash_changes_if_payload_changes():
    h1 = compute_certificate_hash({"count": 5}, "GENESIS")
    h2 = compute_certificate_hash({"count": 6}, "GENESIS")
    assert h1 != h2


def test_certificate_hash_changes_if_prev_hash_changes():
    payload = {"count": 5}
    h1 = compute_certificate_hash(payload, "GENESIS")
    h2 = compute_certificate_hash(payload, "some_other_prev_hash")
    assert h1 != h2


def test_certificate_key_order_does_not_affect_hash():
    """A tampering attempt that just reorders dict keys should NOT produce a different
    hash by accident — but reordering also shouldn't let someone sneak in a change.
    This confirms canonical (sorted-key) serialization is actually being used."""
    payload_a = {"a": 1, "b": 2}
    payload_b = {"b": 2, "a": 1}
    assert compute_certificate_hash(payload_a, "GENESIS") == compute_certificate_hash(payload_b, "GENESIS")


def test_certificate_hash_immune_to_int_vs_float_representation():
    """Regression test for a real bug: JavaScript has no separate int/float type, so a
    Python float like 5.0 can silently become the JSON integer 5 after round-tripping
    through any JS-based client (a browser frontend, or even Swagger UI's own request
    editor). Before the fix, this made every legitimate certificate fail verification
    the moment its payload passed through a browser. The hash must be identical whether
    a number arrives as an int or a float, at any nesting depth."""
    payload_as_floats = {"count": 5.0, "nested": [{"value": 2.0, "items": [1.0, 2.0, 3.0]}]}
    payload_as_ints = {"count": 5, "nested": [{"value": 2, "items": [1, 2, 3]}]}
    assert compute_certificate_hash(payload_as_floats, "GENESIS") == compute_certificate_hash(payload_as_ints, "GENESIS")


def test_certificate_hash_immune_to_int_vs_float_in_tuples():
    """Same as above, but specifically for the (wallet, amount) tuple shape used
    throughout the real certificate payloads (hub_wallets, peel_chains, etc.)."""
    payload_a = {"peel_chains": [(WALLET_A, 5.0, 0.01)]}
    payload_b = {"peel_chains": [(WALLET_A, 5, 0.01)]}
    assert compute_certificate_hash(payload_a, "GENESIS") == compute_certificate_hash(payload_b, "GENESIS")


def test_verify_certificate_accepts_untampered_data():
    payload = {"wallet": WALLET_A, "score": 3}
    h = compute_certificate_hash(payload, "GENESIS")
    assert verify_certificate(payload, "GENESIS", h) is True


def test_verify_certificate_rejects_tampered_payload():
    payload = {"wallet": WALLET_A, "score": 3}
    h = compute_certificate_hash(payload, "GENESIS")
    tampered_payload = {"wallet": WALLET_A, "score": 999}  # attacker changes the score
    assert verify_certificate(tampered_payload, "GENESIS", h) is False


def test_verify_certificate_rejects_tampered_prev_hash():
    payload = {"wallet": WALLET_A, "score": 3}
    h = compute_certificate_hash(payload, "GENESIS")
    assert verify_certificate(payload, "some_forged_prev_hash", h) is False


@pytest.mark.parametrize("main_amt, peel_amt, expected", [
    (49.68, 0.0064, "about 0.013%"),   # tiny peel used to print "about 0.0%"
    (10.0, 0.5, "about 5.0%"),
    (100.0, 0.5, "about 0.5%"),
    (1000.0, 0.00001, "less than 0.01%"),
])
def test_peel_percentage_is_readable(main_amt, peel_amt, expected):
    paragraphs = build_narrative(WALLET_A, 10, 20, [], [], [(WALLET_B, main_amt, peel_amt)], [], [])
    peel_para = next(p for p in paragraphs if "peel chain" in p)
    assert f"({expected})" in peel_para
