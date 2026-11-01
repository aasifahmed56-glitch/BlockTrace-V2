"""
Standalone verification script for Case Anchoring on IPFS & Sepolia.

Usage:
    python test_case_registry.py pinata      — test Pinata JSON pinning
    python test_case_registry.py blockchain  — test on-chain storeCase & getCase
    python test_case_registry.py verify      — test end-to-end case verification
    python test_case_registry.py all         — run all checks sequentially

Requires .env to have PINATA_JWT, SEPOLIA_RPC_URL, CASE_CONTRACT_ADDRESS, WALLET_PRIVATE_KEY.
"""

import sys
import os
import time
import hashlib
from dotenv import load_dotenv

load_dotenv()


def test_pinata_json():
    """Pin a sample case snapshot JSON to Pinata."""
    from pinata_service import upload_json_to_pinata

    sample_snapshot = {
        "case_number": f"BT-TEST-{int(time.time())}",
        "case_name": "Test Investigation",
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "graph": {"nodes": ["0xabc", "0xdef"], "edges": [{"from": "0xabc", "to": "0xdef", "value": 1.0}]},
    }

    print("=" * 60)
    print("TEST: Pinata Case JSON Pinning")
    print("=" * 60)
    print(f"  PINATA_JWT set: {'yes' if os.getenv('PINATA_JWT') else 'NO — will fail'}")

    try:
        res = upload_json_to_pinata(sample_snapshot, name="BlockTrace_Case_Test")
        print("\n  ✓ SUCCESS")
        print(f"    CID:         {res['cid']}")
        print(f"    Gateway URL: {res['gateway_url']}")
        return res
    except Exception as exc:
        print(f"\n  ✗ FAILED: {exc}")
        return None


def test_case_blockchain():
    """Anchor a test case snapshot hash to BlockTraceCaseRegistry on Sepolia."""
    from blockchain_service import store_case_on_chain, get_case_from_chain

    test_case_num = f"BT-2026-{int(time.time()) % 10000:04d}"
    test_hash = hashlib.sha256(f"case_payload_{time.time()}".encode()).hexdigest()
    test_cid = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"

    print("=" * 60)
    print("TEST: Sepolia Case Registry (storeCase & getCase)")
    print("=" * 60)
    print(f"  SEPOLIA_RPC_URL set:       {'yes' if os.getenv('SEPOLIA_RPC_URL') else 'NO'}")
    print(f"  CASE_CONTRACT_ADDRESS set: {'yes' if os.getenv('CASE_CONTRACT_ADDRESS') else 'NO — deploy contract first'}")
    print(f"  WALLET_PRIVATE_KEY set:    {'yes' if os.getenv('WALLET_PRIVATE_KEY') else 'NO'}")
    print(f"  Case Number:               {test_case_num}")
    print(f"  Case Data Hash:            {test_hash}")

    if not os.getenv("CASE_CONTRACT_ADDRESS"):
        print("\n  ⊘ SKIPPED: CASE_CONTRACT_ADDRESS is not set in .env.")
        print("    Deploy BlockTraceCaseRegistry.sol via Remix and add address to .env.")
        return None

    if not os.getenv("WALLET_PRIVATE_KEY"):
        print("\n  ⊘ SKIPPED: WALLET_PRIVATE_KEY not set.")
        return None

    try:
        print("\n  Submitting storeCase transaction to Sepolia...")
        res = store_case_on_chain(test_case_num, test_hash, test_cid)
        print("  ✓ Transaction Confirmed:")
        print(f"    Tx Hash:      {res['tx_hash']}")
        print(f"    Block:        {res['block_number']}")
        print(f"    Explorer URL: {res['explorer_url']}")
        print(f"    Version:      v{res['version']}")

        print("\n  Reading stored case record back from blockchain...")
        record = get_case_from_chain(test_case_num)
        print(f"    On-Chain Hash: {record['case_data_hash']}")
        print(f"    Submitter:     {record['submitter']}")
        print(f"    Version:       v{record['version']}")
        print(f"    IPFS CID:      {record['ipfs_cid']}")

        assert record["case_data_hash"].lower() == test_hash.lower(), "On-chain hash mismatch!"
        print("\n  ✓ VERIFICATION PASSED: On-chain record matches submitted hash exactly!")
        return True
    except Exception as exc:
        print(f"\n  ✗ FAILED: {exc}")
        return False


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "pinata":
        test_pinata_json()
    elif mode == "blockchain":
        test_case_blockchain()
    elif mode == "all":
        p = test_pinata_json()
        print()
        b = test_case_blockchain()
        print("\n" + "=" * 60)
        print("SUMMARY")
        print(f"  Pinata JSON: {'PASS' if p else 'FAIL'}")
        print(f"  Blockchain:  {'PASS' if b else ('SKIP' if b is None else 'FAIL')}")
        print("=" * 60)
    else:
        print("Usage: python test_case_registry.py [pinata|blockchain|all]")
