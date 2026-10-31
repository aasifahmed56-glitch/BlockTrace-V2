# BlockTrace Smart Contract Deployment Guide

## 1. Contracts Overview

### A. `BlockTraceRegistry.sol` (Report Publishing)
Stores forensic report publishing records on-chain:
- **investigationHash** (bytes32) — SHA-256 digest of findings
- **ipfsCid** (string) — IPFS CID of the PDF report
- **submitter** (address) — Submitter address
- **timestamp** (uint256) — Block timestamp

### B. `BlockTraceCaseRegistry.sol` (Case Anchoring)
Anchors saved investigation cases on-chain with versioning:
- **caseNumberHash** (bytes32) — `keccak256(bytes(case_number))` (never plaintext)
- **caseDataHash** (bytes32) — SHA-256 digest of the canonical JSON snapshot
- **ipfsCid** (string) — IPFS CID of the case snapshot
- **submitter** (address) — Original investigator (only original submitter can publish new versions)
- **timestamp** (uint256) — Block timestamp
- **version** (uint256) — 1-indexed version number

> 🔒 **PRIVACY NOTICE**: Plaintext case names, case numbers, and wallet addresses are NEVER stored on-chain. Only cryptographic hashes are recorded. On-chain records and IPFS content are publicly visible.

---

## Deployment Steps (Remix IDE → Sepolia)

### 1. Open Remix IDE
Go to [https://remix.ethereum.org](https://remix.ethereum.org)

### 2. Create the contract file
- In the File Explorer panel, create a new file: `BlockTraceRegistry.sol`
- Copy the entire contents of `contracts/BlockTraceRegistry.sol` into Remix

### 3. Compile
- Go to the **Solidity Compiler** tab (left sidebar)
- Set compiler version to `0.8.19` (or any `^0.8.19`)
- Click **Compile BlockTraceRegistry.sol**
- Verify: ✅ green checkmark, no errors

### 4. Deploy to Sepolia
- Go to the **Deploy & Run Transactions** tab
- Environment: **Injected Provider - MetaMask**
- Make sure MetaMask is connected to the **Sepolia testnet**
- Make sure your wallet has **Sepolia ETH** for gas (see "Funding" below)
- Click **Deploy**
- Confirm the transaction in MetaMask
- Wait for the transaction to be mined (~15 seconds)

### 5. Copy the contract address
- After deployment, the contract will appear under **Deployed Contracts**
- Click the copy icon next to the contract address
- Paste it into your `.env` file as `CONTRACT_ADDRESS`

### 6. Copy the ABI (optional)
- The ABI is already saved in `contracts/BlockTraceRegistry.abi.json`
- If Remix shows a different ABI, click the **ABI** copy button in the compiler tab and replace the file contents

---

## Filling in `.env`

After deploying the contracts on Sepolia via Remix, update your `.env` with:

```env
SEPOLIA_RPC_URL=https://rpc.sepolia.org
CONTRACT_ADDRESS=0xYOUR_DEPLOYED_REPORT_REGISTRY_ADDRESS
CASE_CONTRACT_ADDRESS=0xYOUR_DEPLOYED_CASE_REGISTRY_ADDRESS
WALLET_PRIVATE_KEY=your_metamask_private_key_hex_without_0x
```

### Getting your MetaMask private key
1. Open MetaMask → click the three dots → Account Details
2. Click **Show Private Key** → enter your password
3. Copy the hex string (without the `0x` prefix)
4. Paste into `.env` as `WALLET_PRIVATE_KEY`

> ⚠️ **NEVER commit `.env` to git.** The `.gitignore` already excludes it.

---

## Funding your wallet with Sepolia ETH

You need testnet ETH to pay for gas. Use one of these faucets:

| Faucet | URL |
|--------|-----|
| Google Cloud Sepolia Faucet | https://cloud.google.com/application/web3/faucet/ethereum/sepolia |
| Alchemy Sepolia Faucet | https://sepoliafaucet.com |
| Infura Sepolia Faucet | https://www.infura.io/faucet/sepolia |

Request 0.1–0.5 Sepolia ETH. Each `storeRecord` call costs roughly 0.0005–0.001 ETH in gas.

---

## Verifying the deployment

After filling `Backend/.env`, run from the `Backend` folder:

```bash
python -m tests.test_publish blockchain
```

This will send a test transaction and print the Sepolia Etherscan link if successful.

To test the full flow (Pinata + Sepolia):

```bash
python -m tests.test_publish both
```
