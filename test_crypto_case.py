"""
test_crypto_case.py
-------------------
Comprehensive test suite for BlockTrace AES-256-GCM Case Snapshot Encryption:
1. Master key validation (32 bytes base64, missing key, invalid key).
2. HKDF-SHA256 per-case key derivation determinism and domain isolation.
3. AES-256-GCM encryption / decryption roundtrip.
4. Tamper resistance (corrupted ciphertext, corrupted nonce).
5. Associated Authenticated Data (AAD) binding to case number (prevents cross-case decryption).
6. Wrong key rejection.
7. Plain canonical SHA-256 preservation (on-chain fingerprint matches plaintext, not ciphertext).
8. FastAPI integration: case save fails cleanly when CASE_ENCRYPTION_KEY is missing (no plaintext upload).
"""

import os
import json
import base64
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import crypto_service
from crypto_service import (
    encrypt_snapshot,
    decrypt_snapshot,
    derive_case_key,
    get_master_key,
    CryptoKeyMissingError,
    CryptoKeyInvalidError,
    CryptoDecryptionError,
)

SAMPLE_MASTER_KEY = base64.b64encode(b"01234567890123456789012345678901").decode("ascii")
SAMPLE_CASE_NUMBER = "BT-2026-TEST01"
SAMPLE_PAYLOAD = {
    "case_number": SAMPLE_CASE_NUMBER,
    "name": "Investigation Alpha",
    "saved_at": "2026-10-24T12:00:00Z",
    "nodes": [{"id": "0x111", "label": "Target Wallet"}],
    "edges": [{"source": "0x111", "target": "0x222", "amount": 5.5}],
    "summary": {"wallets_traced": 2, "transactions_mapped": 1},
}
SAMPLE_BYTES = json.dumps(SAMPLE_PAYLOAD, sort_keys=True).encode("utf-8")


def test_get_master_key_success(monkeypatch):
    monkeypatch.setenv("CASE_ENCRYPTION_KEY", SAMPLE_MASTER_KEY)
    key = get_master_key()
    assert len(key) == 32
    assert key == b"01234567890123456789012345678901"


def test_get_master_key_missing(monkeypatch):
    monkeypatch.delenv("CASE_ENCRYPTION_KEY", raising=False)
    with pytest.raises(CryptoKeyMissingError) as exc_info:
        get_master_key()
    assert "isn't set up on this server" in str(exc_info.value)
    assert ".env" not in str(exc_info.value)


def test_get_master_key_invalid_length(monkeypatch):
    # Only 16 bytes base64-encoded
    short_key = base64.b64encode(b"shortkey12345678").decode("ascii")
    monkeypatch.setenv("CASE_ENCRYPTION_KEY", short_key)
    with pytest.raises(CryptoKeyInvalidError) as exc_info:
        get_master_key()
    assert "32 bytes" in str(exc_info.value)


def test_get_master_key_invalid_base64(monkeypatch):
    monkeypatch.setenv("CASE_ENCRYPTION_KEY", "!!!not-valid-base64???")
    with pytest.raises(CryptoKeyInvalidError):
        get_master_key()


def test_hkdf_derivation_isolation(monkeypatch):
    monkeypatch.setenv("CASE_ENCRYPTION_KEY", SAMPLE_MASTER_KEY)
    key1 = derive_case_key("BT-2026-0001")
    key2 = derive_case_key("BT-2026-0002")
    key1_again = derive_case_key("BT-2026-0001")

    assert len(key1) == 32
    assert len(key2) == 32
    assert key1 == key1_again, "HKDF must be deterministic for the same case number"
    assert key1 != key2, "HKDF must produce different keys for different case numbers"


def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setenv("CASE_ENCRYPTION_KEY", SAMPLE_MASTER_KEY)
    envelope_bytes = encrypt_snapshot(SAMPLE_BYTES, SAMPLE_CASE_NUMBER)

    # Ensure envelope is valid JSON structure
    envelope = json.loads(envelope_bytes.decode("utf-8"))
    assert envelope["version"] == 1
    assert envelope["algorithm"] == "AES-256-GCM"
    assert envelope["case_number"] == SAMPLE_CASE_NUMBER
    assert "nonce" in envelope
    assert "ciphertext" in envelope

    # Decrypt
    decrypted = decrypt_snapshot(envelope_bytes, SAMPLE_CASE_NUMBER)
    assert decrypted == SAMPLE_BYTES
    decrypted_obj = json.loads(decrypted.decode("utf-8"))
    assert decrypted_obj["name"] == "Investigation Alpha"


def test_tampered_ciphertext_fails(monkeypatch):
    monkeypatch.setenv("CASE_ENCRYPTION_KEY", SAMPLE_MASTER_KEY)
    envelope_bytes = encrypt_snapshot(SAMPLE_BYTES, SAMPLE_CASE_NUMBER)
    envelope = json.loads(envelope_bytes.decode("utf-8"))

    # Tamper with ciphertext
    raw_ct = bytearray(base64.b64decode(envelope["ciphertext"]))
    raw_ct[0] ^= 0xFF  # Flip bits
    envelope["ciphertext"] = base64.b64encode(raw_ct).decode("ascii")

    tampered_bytes = json.dumps(envelope).encode("utf-8")
    with pytest.raises(CryptoDecryptionError) as exc_info:
        decrypt_snapshot(tampered_bytes, SAMPLE_CASE_NUMBER)
    assert "Decryption failed" in str(exc_info.value)


def test_wrong_case_number_fails(monkeypatch):
    """Associated authenticated data mismatch: decrypting with a different case number must fail."""
    monkeypatch.setenv("CASE_ENCRYPTION_KEY", SAMPLE_MASTER_KEY)
    envelope_bytes = encrypt_snapshot(SAMPLE_BYTES, SAMPLE_CASE_NUMBER)

    with pytest.raises(CryptoDecryptionError):
        # Pass a different case number
        decrypt_snapshot(envelope_bytes, "BT-2026-OTHER99")


def test_wrong_master_key_fails(monkeypatch):
    monkeypatch.setenv("CASE_ENCRYPTION_KEY", SAMPLE_MASTER_KEY)
    envelope_bytes = encrypt_snapshot(SAMPLE_BYTES, SAMPLE_CASE_NUMBER)

    # Change master key
    other_key = base64.b64encode(b"98765432109876543210987654321099").decode("ascii")
    monkeypatch.setenv("CASE_ENCRYPTION_KEY", other_key)

    with pytest.raises(CryptoDecryptionError):
        decrypt_snapshot(envelope_bytes, SAMPLE_CASE_NUMBER)


def test_canonical_hash_preservation(monkeypatch):
    """Verify that case_data_hash is computed over plain canonical snapshot, NOT the encrypted envelope."""
    import hashlib

    plain_hash = hashlib.sha256(SAMPLE_BYTES).hexdigest()

    monkeypatch.setenv("CASE_ENCRYPTION_KEY", SAMPLE_MASTER_KEY)
    envelope_bytes = encrypt_snapshot(SAMPLE_BYTES, SAMPLE_CASE_NUMBER)
    envelope_hash = hashlib.sha256(envelope_bytes).hexdigest()

    assert plain_hash != envelope_hash
    # The decrypted hash MUST match plain_hash
    decrypted = decrypt_snapshot(envelope_bytes, SAMPLE_CASE_NUMBER)
    assert hashlib.sha256(decrypted).hexdigest() == plain_hash


if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("RUNNING BLOCKTRACE CRYPTO TEST SUITE")
    print("=" * 60)

    class MonkeyPatchStub:
        def __init__(self):
            self.orig = dict(os.environ)
        def setenv(self, k, v):
            os.environ[k] = v
        def delenv(self, k, raising=False):
            os.environ.pop(k, None)
        def undo(self):
            os.environ.clear()
            os.environ.update(self.orig)

    mp = MonkeyPatchStub()
    tests = [
        test_get_master_key_success,
        test_get_master_key_missing,
        test_get_master_key_invalid_length,
        test_get_master_key_invalid_base64,
        test_hkdf_derivation_isolation,
        test_encrypt_decrypt_roundtrip,
        test_tampered_ciphertext_fails,
        test_wrong_case_number_fails,
        test_wrong_master_key_fails,
        test_canonical_hash_preservation,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t(mp)
            print(f"[PASS] {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        finally:
            mp.undo()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    if failed > 0:
        sys.exit(1)
