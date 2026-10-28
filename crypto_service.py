"""
Cryptographic encryption & decryption service for BlockTrace case snapshots.

Uses authenticated encryption:
- Master key: 32 bytes (256-bit), base64-encoded, read from CASE_ENCRYPTION_KEY in .env.
- Key derivation: HKDF-SHA256 per-case key derived using case_number as context info.
- Cipher: AES-256-GCM with a unique 12-byte random nonce per encryption.
- Associated data: case_number bound into the GCM auth tag to prevent cross-case replay.
"""

import os
import json
import base64
from typing import Optional
from dotenv import load_dotenv

load_dotenv(override=True)

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


class CryptoError(Exception):
    """Base exception for all cryptographic operations."""
    pass


class CryptoKeyMissingError(CryptoError):
    """Raised when CASE_ENCRYPTION_KEY is not set in the environment."""
    pass


class CryptoKeyInvalidError(CryptoError):
    """Raised when CASE_ENCRYPTION_KEY is malformed or not 32 bytes."""
    pass


class CryptoDecryptionError(CryptoError):
    """Raised when decryption fails due to invalid key, tampered data, or wrong case number."""
    pass


_HKDF_SALT = b"blocktrace-case-encryption-v1"


def get_master_key() -> bytes:
    """Retrieves and validates the 32-byte master key from CASE_ENCRYPTION_KEY.

    Never logs or exposes the key material.
    """
    raw_b64 = os.getenv("CASE_ENCRYPTION_KEY")
    if not raw_b64 or not raw_b64.strip():
        raise CryptoKeyMissingError(
            "CASE_ENCRYPTION_KEY is not set in .env. "
            "Run 'python generate_key.py' to generate a secure master key, "
            "and add it to your .env file."
        )

    clean_b64 = raw_b64.strip()
    try:
        key_bytes = base64.b64decode(clean_b64, validate=True)
    except Exception as exc:
        raise CryptoKeyInvalidError(
            f"CASE_ENCRYPTION_KEY is not a valid base64 string: {exc}"
        )

    if len(key_bytes) != 32:
        raise CryptoKeyInvalidError(
            f"CASE_ENCRYPTION_KEY must decode to exactly 32 bytes (256 bits). "
            f"Got {len(key_bytes)} bytes."
        )

    return key_bytes


def is_encryption_configured() -> bool:
    """Returns True if a valid CASE_ENCRYPTION_KEY is configured in .env."""
    try:
        get_master_key()
        return True
    except Exception:
        return False


def derive_case_key(arg1, arg2: Optional[str] = None) -> bytes:
    """Derives a deterministic 32-byte key for a specific case using HKDF-SHA256.

    Supports either:
        derive_case_key(master_key: bytes, case_number: str)
    or:
        derive_case_key(case_number: str)  # loads master key automatically
    """
    if arg2 is not None:
        master_key = arg1
        case_number = arg2
    elif isinstance(arg1, str):
        master_key = get_master_key()
        case_number = arg1
    else:
        raise ValueError("Invalid arguments for derive_case_key: pass (master_key, case_number) or (case_number).")

    if not case_number or not isinstance(case_number, str):
        raise ValueError("A valid case_number string is required for key derivation.")

    info = case_number.strip().encode("utf-8")
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=info,
    )
    return hkdf.derive(master_key)


def encrypt_snapshot(plain_bytes: bytes, case_number: str) -> bytes:
    """Encrypts case snapshot bytes using AES-256-GCM with a per-case derived key.

    Args:
        plain_bytes: Canonical JSON snapshot bytes.
        case_number: Plaintext case number (e.g. 'BT-2026-0001').

    Returns:
        bytes of a UTF-8 encoded JSON envelope containing version, nonce, and ciphertext.

    Raises:
        CryptoKeyMissingError if CASE_ENCRYPTION_KEY is not configured.
        CryptoKeyInvalidError if the key format is invalid.
    """
    if not isinstance(plain_bytes, (bytes, bytearray)):
        raise TypeError("plain_bytes must be bytes or bytearray.")

    master_key = get_master_key()
    case_key = derive_case_key(master_key, case_number)

    # 12-byte random nonce per AES-GCM specification
    nonce = os.urandom(12)
    aesgcm = AESGCM(case_key)

    # Authenticate the case_number as associated data to prevent cross-case swapping
    ad = case_number.strip().encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plain_bytes, associated_data=ad)

    envelope = {
        "version": 1,
        "algorithm": "AES-256-GCM",
        "case_number": case_number.strip(),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }

    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")


def decrypt_snapshot(envelope_bytes: bytes, case_number: str) -> bytes:
    """Decrypts an encrypted case snapshot envelope.

    Args:
        envelope_bytes: UTF-8 JSON envelope bytes as produced by encrypt_snapshot.
        case_number: Case number for key derivation and associated data validation.

    Returns:
        Original plaintext bytes.

    Raises:
        CryptoDecryptionError if the key is wrong, data is corrupted, or auth tag fails.
        CryptoKeyMissingError if CASE_ENCRYPTION_KEY is not configured.
    """
    if not isinstance(envelope_bytes, (bytes, bytearray)):
        raise TypeError("envelope_bytes must be bytes or bytearray.")

    master_key = get_master_key()

    try:
        envelope = json.loads(envelope_bytes.decode("utf-8"))
    except Exception as exc:
        raise CryptoDecryptionError(
            f"Failed to parse encrypted snapshot envelope: {exc}"
        )

    if envelope.get("version") != 1:
        raise CryptoDecryptionError(
            f"Unsupported encryption envelope version: {envelope.get('version')}"
        )

    try:
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
    except Exception as exc:
        raise CryptoDecryptionError(
            f"Failed to decode base64 nonce/ciphertext from envelope: {exc}"
        )

    case_key = derive_case_key(master_key, case_number)
    aesgcm = AESGCM(case_key)
    ad = case_number.strip().encode("utf-8")

    try:
        plain_bytes = aesgcm.decrypt(nonce, ciphertext, associated_data=ad)
        return plain_bytes
    except InvalidTag as exc:
        raise CryptoDecryptionError(
            "Decryption failed: cryptographic authentication tag mismatch. "
            "The data may be corrupted, tampered with, or encrypted with a different key."
        ) from exc
    except Exception as exc:
        raise CryptoDecryptionError(
            f"Decryption failed: {exc}"
        ) from exc
