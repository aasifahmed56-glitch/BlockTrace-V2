"""
Blockchain service for BlockTrace — writes investigation records to the
BlockTraceRegistry smart contract on Sepolia via web3.py.

Usage:
    from blockchain_service import store_record_on_chain, is_hash_on_chain
    result = store_record_on_chain("abcdef1234...64hex", "bafybeig...")
    # result = {"tx_hash": "0x...", "block_number": 123, "explorer_url": "https://..."}
"""

import os
import json
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

try:
    from web3 import Web3
    _WEB3_IMPORT_ERROR = None
except Exception as _w3_exc:
    Web3 = None
    _WEB3_IMPORT_ERROR = str(_w3_exc)

load_dotenv(override=True)

SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
CASE_CONTRACT_ADDRESS = os.getenv("CASE_CONTRACT_ADDRESS")
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY")

EXPLORER_BASE = "https://sepolia.etherscan.io/tx"

# Load the ABI from the local JSON files.
_ABI_PATH = Path(__file__).parent / "contracts" / "BlockTraceRegistry.abi.json"
_CASE_ABI_PATH = Path(__file__).parent / "contracts" / "BlockTraceCaseRegistry.abi.json"


class BlockchainServiceError(Exception):
    """Raised when any on-chain interaction fails."""
    pass


def _load_contract(require_wallet: bool = True):
    """Initialise the Web3 provider and contract object. Validates config."""
    if Web3 is None:
        raise BlockchainServiceError(f"Web3 library is unavailable: {_WEB3_IMPORT_ERROR}")

    rpc_url = os.getenv("SEPOLIA_RPC_URL") or SEPOLIA_RPC_URL
    contract_addr = os.getenv("CONTRACT_ADDRESS") or CONTRACT_ADDRESS
    priv_key = os.getenv("WALLET_PRIVATE_KEY") or WALLET_PRIVATE_KEY

    if not rpc_url:
        raise ValueError("SEPOLIA_RPC_URL is not set in .env")
    if not contract_addr:
        raise ValueError("CONTRACT_ADDRESS is not set in .env (deploy the contract first)")
    if require_wallet and not priv_key:
        raise ValueError("WALLET_PRIVATE_KEY is not set in .env")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise BlockchainServiceError(
            f"Cannot connect to Sepolia RPC at {rpc_url}. "
            "Check the URL and your internet connection."
        )

    with open(_ABI_PATH, "r") as f:
        abi = json.load(f)

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_addr),
        abi=abi,
    )
    account = w3.eth.account.from_key(priv_key) if (require_wallet and priv_key) else None
    return w3, contract, account


def _hex_to_bytes32(hex_str: str) -> bytes:
    """Convert a 64-char hex string (with or without 0x prefix) to a 32-byte value
    suitable for Solidity bytes32."""
    clean = hex_str.lower().removeprefix("0x")
    if len(clean) != 64:
        raise ValueError(
            f"Investigation hash must be exactly 64 hex characters (got {len(clean)}). "
            f"Value: {hex_str[:20]}..."
        )
    return bytes.fromhex(clean)


def get_report_record(investigation_hash_hex: str) -> Optional[dict]:
    """Read an investigation report record from the BlockTraceRegistry contract on Sepolia.

    Does NOT require WALLET_PRIVATE_KEY (read-only call).

    Args:
        investigation_hash_hex: 64-character hex hash (with or without '0x' prefix).

    Returns:
        dict with keys:
            investigation_hash   — 64-character lowercase hex string
            ipfs_cid             — IPFS CID stored on-chain
            submitter            — address that submitted the record
            timestamp            — block timestamp (int)
            explorer_address_url — link to the contract on Sepolia Etherscan
            contract_address     — checksummed contract address
        Or None if the record does not exist on-chain.
    """
    if not investigation_hash_hex or not isinstance(investigation_hash_hex, str):
        raise ValueError("Investigation hash must be a non-empty string.")

    clean_hash = investigation_hash_hex.strip().lower().removeprefix("0x")
    if len(clean_hash) != 64 or not all(c in "0123456789abcdef" for c in clean_hash):
        raise ValueError(
            f"Investigation hash must be exactly 64 hexadecimal characters. Got: {investigation_hash_hex}"
        )

    hash_bytes = bytes.fromhex(clean_hash)

    try:
        w3, contract, _ = _load_contract(require_wallet=False)
    except Exception as exc:
        raise BlockchainServiceError(f"Could not connect to Sepolia contract: {exc}")

    contract_addr = os.getenv("CONTRACT_ADDRESS") or CONTRACT_ADDRESS
    try:
        record = contract.functions.getRecord(hash_bytes).call()
        # Outputs: [bytes32 investigationHash, string ipfsCid, address submitter, uint256 timestamp]
        return {
            "investigation_hash": clean_hash,
            "ipfs_cid": record[1],
            "submitter": record[2],
            "timestamp": int(record[3]),
            "explorer_address_url": f"https://sepolia.etherscan.io/address/{contract_addr}",
            "contract_address": contract_addr,
        }
    except Exception as exc:
        err_msg = str(exc).lower()
        if "not found" in err_msg or "revert" in err_msg or "execution reverted" in err_msg:
            return None
        raise BlockchainServiceError(f"Failed to query on-chain record: {exc}")


def is_hash_on_chain(investigation_hash_hex: str) -> bool:
    """Check whether an investigation hash has already been stored on-chain.

    Returns True if the hash exists, False otherwise. Does NOT require a wallet
    private key (read-only call).
    """
    try:
        rec = get_report_record(investigation_hash_hex)
        return rec is not None
    except Exception:
        return False


def _build_eip1559_tx_params(w3, account_address, fn_call, default_gas: int = 350_000) -> dict:
    """Builds EIP-1559 gas fee parameters and estimates gas limit with 20% buffer.

    - Reads baseFeePerGas from latest block
    - Reads suggested priority fee from w3.eth.max_priority_fee (fallback: 1 gwei)
    - Sets maxPriorityFeePerGas to suggested priority fee
    - Sets maxFeePerGas = (2 * baseFeePerGas) + maxPriorityFeePerGas
    - Guards: maxPriorityFeePerGas <= maxFeePerGas
    - Uses w3.eth.estimate_gas with 20% buffer for gas limit
    - Uses correct pending nonce and chainId
    """
    nonce = w3.eth.get_transaction_count(account_address, "pending")

    latest_block = w3.eth.get_block("latest")
    base_fee = latest_block.get("baseFeePerGas")
    if base_fee is None:
        base_fee = w3.eth.gas_price

    try:
        suggested_priority = w3.eth.max_priority_fee
    except Exception:
        suggested_priority = w3.to_wei(1, "gwei")
    if not suggested_priority or suggested_priority == 0:
        suggested_priority = w3.to_wei(1, "gwei")

    max_priority_fee = suggested_priority
    max_fee = (2 * base_fee) + max_priority_fee
    if max_priority_fee > max_fee:
        max_priority_fee = max_fee

    try:
        data = fn_call._encode_transaction_data() if hasattr(fn_call, "_encode_transaction_data") else None
        if data:
            estimated_gas = w3.eth.estimate_gas({
                "from": account_address,
                "to": fn_call.address,
                "data": data,
            })
        else:
            estimated_gas = fn_call.estimate_gas({"from": account_address})
    except Exception:
        try:
            estimated_gas = fn_call.estimate_gas({"from": account_address})
        except Exception:
            estimated_gas = default_gas

    gas_limit = int(estimated_gas * 1.2)

    try:
        chain_id = w3.eth.chain_id
    except Exception:
        chain_id = 11155111

    return {
        "from": account_address,
        "nonce": nonce,
        "gas": gas_limit,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": max_priority_fee,
        "chainId": chain_id,
    }


def store_record_on_chain(investigation_hash_hex: str, ipfs_cid: str) -> dict:
    """Submit a storeRecord transaction to the BlockTraceRegistry contract.

    Args:
        investigation_hash_hex: 64-character hex SHA-256 hash (from logic.compute_certificate_hash).
        ipfs_cid: The IPFS CID returned by Pinata after uploading the PDF.

    Returns:
        dict with keys:
            tx_hash      — the Sepolia transaction hash (0x-prefixed hex string)
            block_number — the block the transaction was mined in
            explorer_url — direct link to the transaction on sepolia.etherscan.io

    Raises:
        BlockchainServiceError on any failure (nonce issues, revert, timeout, etc.).
        ValueError if the hash format is invalid or env vars are missing.
    """
    w3, contract, account = _load_contract()

    hash_bytes = _hex_to_bytes32(investigation_hash_hex)

    # Check for duplicate before spending gas.
    try:
        contract.functions.getRecord(hash_bytes).call()
        # If the call did NOT revert, the record already exists.
        raise BlockchainServiceError(
            "This investigation hash is already recorded on-chain. "
            "Duplicate submissions are rejected by the smart contract."
        )
    except BlockchainServiceError:
        raise  # re-raise our own duplicate error
    except Exception:
        pass  # getRecord reverted → hash does not exist yet, proceed.

    try:
        fn_call = contract.functions.storeRecord(hash_bytes, ipfs_cid)
        tx_params = _build_eip1559_tx_params(w3, account.address, fn_call, default_gas=300_000)
        tx = fn_call.build_transaction(tx_params)

        signed = w3.eth.account.sign_transaction(tx, private_key=WALLET_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt.status != 1:
            raise BlockchainServiceError(
                f"Transaction reverted on-chain. tx_hash={tx_hash.hex()}"
            )

        tx_hash_hex = receipt.transactionHash.hex()
        if not tx_hash_hex.startswith("0x"):
            tx_hash_hex = "0x" + tx_hash_hex

        return {
            "tx_hash": tx_hash_hex,
            "block_number": receipt.blockNumber,
            "explorer_url": f"{EXPLORER_BASE}/{tx_hash_hex}",
        }

    except BlockchainServiceError:
        raise
    except Exception as exc:
        raise BlockchainServiceError(f"On-chain transaction failed: {exc}")


def _load_case_contract(require_wallet: bool = True):
    """Initialise the Web3 provider and Case Registry contract object."""
    if Web3 is None:
        raise BlockchainServiceError(f"Web3 library is unavailable: {_WEB3_IMPORT_ERROR}")

    rpc_url = os.getenv("SEPOLIA_RPC_URL") or SEPOLIA_RPC_URL
    contract_addr = os.getenv("CASE_CONTRACT_ADDRESS") or CASE_CONTRACT_ADDRESS
    priv_key = os.getenv("WALLET_PRIVATE_KEY") or WALLET_PRIVATE_KEY

    if not rpc_url:
        raise ValueError("SEPOLIA_RPC_URL is not set in .env")
    if not contract_addr:
        raise ValueError("CASE_CONTRACT_ADDRESS is not set in .env (deploy BlockTraceCaseRegistry first)")
    if require_wallet and not priv_key:
        raise ValueError("WALLET_PRIVATE_KEY is not set in .env")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise BlockchainServiceError(
            f"Cannot connect to Sepolia RPC at {rpc_url}. Check the URL and internet connection."
        )

    if not _CASE_ABI_PATH.exists():
        raise BlockchainServiceError(f"ABI file not found at {_CASE_ABI_PATH}")

    with open(_CASE_ABI_PATH, "r") as f:
        abi = json.load(f)

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_addr),
        abi=abi,
    )
    account = w3.eth.account.from_key(priv_key) if priv_key else None
    return w3, contract, account


def case_number_to_hash(case_number: str) -> bytes:
    """Computes keccak256 hash of the case number string as bytes32."""
    trimmed = case_number.strip()
    if Web3 is not None:
        return Web3.keccak(text=trimmed)
    import hashlib
    # Fallback to sha256 bytes32 if web3 unavailable
    return hashlib.sha256(trimmed.encode("utf-8")).digest()


def store_case_on_chain(case_number: str, case_data_hash_hex: str, ipfs_cid: str) -> dict:
    """Stores or updates a case record on-chain in BlockTraceCaseRegistry.

    Args:
        case_number: Plaintext case number (e.g. "BT-2026-0001"). Its keccak256 hash is computed.
        case_data_hash_hex: 64-char hex SHA-256 digest of the canonical snapshot.
        ipfs_cid: The IPFS CID returned from Pinata for the case snapshot.

    Returns:
        dict with:
            tx_hash      — 0x-prefixed transaction hash
            block_number — block height
            explorer_url — Sepolia Etherscan link
            version      — version integer (1 for new, incremented for updates)
    """
    w3, contract, account = _load_case_contract(require_wallet=True)

    case_num_hash = case_number_to_hash(case_number)
    case_data_hash_bytes = _hex_to_bytes32(case_data_hash_hex)

    try:
        fn_call = contract.functions.storeCase(
            case_num_hash,
            case_data_hash_bytes,
            ipfs_cid
        )
        tx_params = _build_eip1559_tx_params(w3, account.address, fn_call, default_gas=350_000)
        tx = fn_call.build_transaction(tx_params)

        signed = w3.eth.account.sign_transaction(tx, private_key=account.key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt.status != 1:
            raise BlockchainServiceError(f"Transaction reverted on-chain. tx_hash={tx_hash.hex()}")

        tx_hash_hex = receipt.transactionHash.hex()
        if not tx_hash_hex.startswith("0x"):
            tx_hash_hex = "0x" + tx_hash_hex

        # Query latest version from contract
        try:
            record = contract.functions.getCase(case_num_hash).call()
            version = record[5]
        except Exception:
            version = 1

        return {
            "tx_hash": tx_hash_hex,
            "block_number": receipt.blockNumber,
            "explorer_url": f"{EXPLORER_BASE}/{tx_hash_hex}",
            "version": version,
        }

    except BlockchainServiceError:
        raise
    except Exception as exc:
        raise BlockchainServiceError(f"On-chain case anchoring failed: {exc}")


def get_case_from_chain(case_number: str) -> dict:
    """Reads latest case record from BlockTraceCaseRegistry on Sepolia.

    Returns:
        dict with on-chain fields including case_data_hash, ipfs_cid, submitter, timestamp, version.
    """
    w3, contract, _ = _load_case_contract(require_wallet=False)
    case_num_hash = case_number_to_hash(case_number)

    try:
        record = contract.functions.getCase(case_num_hash).call()
    except Exception as exc:
        raise BlockchainServiceError(f"Case '{case_number}' not found on-chain: {exc}")

    # record: (caseNumberHash, caseDataHash, ipfsCid, submitter, timestamp, version)
    data_hash_bytes = record[1]
    data_hash_hex = data_hash_bytes.hex() if isinstance(data_hash_bytes, (bytes, bytearray)) else str(data_hash_bytes)
    data_hash_clean = data_hash_hex.removeprefix("0x")

    return {
        "case_number_hash": record[0].hex() if isinstance(record[0], (bytes, bytearray)) else str(record[0]),
        "case_data_hash": data_hash_clean,
        "ipfs_cid": record[2],
        "submitter": record[3],
        "timestamp": record[4],
        "version": record[5],
    }


def is_case_on_chain(case_number: str) -> bool:
    """Returns True if case_number has been anchored on-chain, False otherwise."""
    try:
        get_case_from_chain(case_number)
        return True
    except Exception:
        return False
