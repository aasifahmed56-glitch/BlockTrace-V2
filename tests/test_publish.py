"""
Standalone verification scripts for the IPFS + blockchain publish feature.

Run individual checks:
    python test_publish.py pinata      — test Pinata upload with a dummy PDF
    python test_publish.py blockchain  — test on-chain write with a fake hash
    python test_publish.py both        — run both checks sequentially

Requires .env to be populated with valid credentials.
"""

import sys
import os
import hashlib
import time

# Make sure dotenv is loaded before anything else
from dotenv import load_dotenv
load_dotenv()


def test_pinata():
    """Upload a tiny test PDF to Pinata and print the CID."""
    from pinata_service import upload_pdf_to_pinata

    # Minimal valid PDF bytes (a blank single-page PDF)
    dummy_pdf = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )

    print("=" * 60)
    print("TEST: Pinata IPFS Upload")
    print("=" * 60)
    print(f"  PINATA_JWT set: {'yes' if os.getenv('PINATA_JWT') else 'NO — will fail'}")
    print(f"  Uploading {len(dummy_pdf)} bytes as test_blocktrace.pdf ...")

    try:
        result = upload_pdf_to_pinata(
            dummy_pdf,
            filename="test_blocktrace.pdf",
            investigation_id="test_run",
        )
        print(f"\n  ✓ SUCCESS")
        print(f"    CID:         {result['cid']}")
        print(f"    IPFS URL:    {result['ipfs_url']}")
        print(f"    Gateway URL: {result['gateway_url']}")
        return True
    except Exception as exc:
        print(f"\n  ✗ FAILED: {exc}")
        return False


def test_blockchain():
    """Send a test storeRecord transaction to Sepolia."""
    from blockchain_service import store_record_on_chain, is_hash_on_chain

    # Generate a unique-enough test hash so it won't collide with real data
    test_hash = hashlib.sha256(f"blocktrace_test_{time.time()}".encode()).hexdigest()
    test_cid = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"  # well-known test CID

    print("=" * 60)
    print("TEST: Sepolia On-Chain Write")
    print("=" * 60)
    print(f"  SEPOLIA_RPC_URL set:    {'yes' if os.getenv('SEPOLIA_RPC_URL') else 'NO'}")
    print(f"  CONTRACT_ADDRESS set:   {'yes' if os.getenv('CONTRACT_ADDRESS') else 'NO — deploy contract first'}")
    print(f"  WALLET_PRIVATE_KEY set: {'yes' if os.getenv('WALLET_PRIVATE_KEY') else 'NO'}")
    print(f"  Test hash: {test_hash[:20]}...")

    if not os.getenv("CONTRACT_ADDRESS"):
        print("\n  ⊘ SKIPPED: CONTRACT_ADDRESS not set. Deploy the contract first.")
        return None

    if not os.getenv("WALLET_PRIVATE_KEY"):
        print("\n  ⊘ SKIPPED: WALLET_PRIVATE_KEY not set.")
        return None

    print(f"  Checking if hash is already on-chain...")
    if is_hash_on_chain(test_hash):
        print(f"  Hash already exists (unlikely for a test hash — check for collision).")
        return False

    print(f"  Sending storeRecord transaction...")
    try:
        result = store_record_on_chain(test_hash, test_cid)
        print(f"\n  ✓ SUCCESS")
        print(f"    TX Hash:      {result['tx_hash']}")
        print(f"    Block:        {result['block_number']}")
        print(f"    Explorer URL: {result['explorer_url']}")
        return True
    except Exception as exc:
        print(f"\n  ✗ FAILED: {exc}")
        return False


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"

    if mode == "pinata":
        test_pinata()
    elif mode == "blockchain":
        test_blockchain()
    elif mode == "both":
        p = test_pinata()
        print()
        b = test_blockchain()
        print("\n" + "=" * 60)
        print("SUMMARY")
        print(f"  Pinata:     {'PASS' if p else 'FAIL'}")
        print(f"  Blockchain: {'PASS' if b else ('SKIP' if b is None else 'FAIL')}")
        print("=" * 60)
    else:
        print(f"Usage: python test_publish.py [pinata|blockchain|both]")
        sys.exit(1)
