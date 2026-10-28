#!/usr/bin/env python3
"""
Helper utility to generate a cryptographically secure 256-bit (32-byte)
AES key for BlockTrace case snapshot encryption.

Usage:
    python generate_key.py
"""

import os
import base64


def main():
    # 32 cryptographically secure random bytes = 256 bits
    key_bytes = os.urandom(32)
    key_b64 = base64.b64encode(key_bytes).decode("ascii")

    print("=" * 64)
    print("BlockTrace -- Master Case Encryption Key Generator")
    print("=" * 64)
    print("\nGenerated 256-bit AES-GCM master key.\n")
    print("Copy and paste the following line into your .env file:\n")
    print(f"CASE_ENCRYPTION_KEY={key_b64}\n")
    print("=" * 64)
    print("SECURITY NOTICE:")
    print("  * Keep this key confidential -- never commit it to source control.")
    print("  * If this key is lost, case snapshots uploaded to IPFS cannot")
    print("    be decrypted.")
    print("=" * 64)


if __name__ == "__main__":
    main()
