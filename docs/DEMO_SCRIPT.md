# BlockTrace Live Demonstration Script (5–7 Minutes)

A step-by-step presentation script for showcasing BlockTrace's end-to-end blockchain forensic analysis, decentralized report publishing, server-side encrypted case anchoring, and public report verification on the Ethereum Sepolia testnet.

---

## Pre-Demo Checklist (Complete 10 Minutes Before Presentation)

- [ ] **Backend Running**: FastAPI backend active on `http://127.0.0.1:8000` (from `Backend`: `..\venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000`).
- [ ] **Frontend Running**: Vite dev server active on `http://localhost:5173` (`npm run dev` in `Frontend`).
- [ ] **Wallet Funded**: Submitter wallet in `.env` has at least 0.05 Sepolia testnet ETH.
- [ ] **Database Active**: Neo4j Aura database connected and responsive.
- [ ] **Workspace Cleared**: Click **Clear** (top right) so the workspace is empty before loading a case; saved cases and reports include everything currently in the workspace.
- [ ] **Files Prepared**:
  1. Have a folder ready to save `authentic_report.pdf` (which will be downloaded directly from the IPFS gateway link during Step 3).
  2. Create `tampered_report.pdf`: Any modified copy of a PDF report (e.g. opened in a text/hex editor where a character was changed, or any distinct PDF file).
- [ ] **Browser Tabs Ready**:
  - Tab 1: `http://localhost:5173/` (BlockTrace Web Interface)
  - Tab 2: `https://sepolia.etherscan.io` (Sepolia Explorer)

---

## Demonstration Timeline & Narrative

```
0:00 - 1:00  |  Part 1: The Incident & Forensic Graph Tracing
1:00 - 1:30  |  Part 2: Automated Forensic Heuristics & Sanctions Screening (30s)
1:30 - 3:00  |  Part 3: Decentralized Report Publishing (IPFS + Sepolia)
3:00 - 4:15  |  Part 4: Server-Side Encrypted Case Anchoring & Verification
4:15 - 6:15  |  Part 5: The Public "Verify Report" Experience & Tamper Defense
6:15 - 6:45  |  Part 6: Conclusion & Value Proposition
```

---

### Part 1: The Incident & Forensic Graph Tracing (1:00)

#### Actions:
1. Open the BlockTrace UI (`http://localhost:5173/`). Click **Clear** (top right) so the workspace is empty before loading a case; saved cases and reports include everything currently in the workspace.
2. In the left navigation sidebar, click **Investigate**.
3. In the left panel under **Example Investigations**, click **Ronin Bridge Hack ($600M, 2022)**.
4. Watch the directed graph populate with nodes and transaction links. Zoom in on the central cluster and hover over the primary exploit address.

#### What to Say:
> *"Welcome to BlockTrace. In March 2022, the Ronin Bridge suffered a cyberheist of roughly $600 million orchestrated by the North Korean Lazarus Group.*
>
> *Traditional investigation workflows struggle because illicit actors launder stolen capital across hundreds of burner addresses, mixers, and bridges. BlockTrace reconstructs raw EVM transaction ledgers into an intuitive forensic intelligence graph.*
>
> *By clicking 'Ronin Bridge Hack' under Example Investigations, our backend traces the exploit window itself — 23 March to 30 April 2022, oldest transactions first — and loads it into Neo4j, revealing the exploit address, rapid peeling chains, and subsequent dispersal hops across intermediate accounts. The banner above the graph states exactly that scope, and flags any wallet whose history was cut off by the per-wallet transaction cap, so nobody mistakes a sample for the full history."*

#### Fallback (If Something Fails):
- *If graph does not load immediately*: Click **Clear** (top right), then click **Ronin Bridge Hack ($600M, 2022)** again under Example Investigations.

---

### Part 2: Automated Forensic Heuristics & Sanctions Screening (0:30)

#### Actions:
1. In the left navigation sidebar, click **Findings**.
2. Briefly point out the **Sanctions Hits** table showing the Lazarus-affiliated addresses, and the **Detection Heuristics** (peeling chains, high-velocity dispersal).

#### What to Say:
> *"Next, we open Findings. BlockTrace executes automated heuristics to identify money laundering behaviors like peeling chains and fan-out dispersal.*
>
> *Simultaneously, our engine cross-references all discovered counterparties against a dated snapshot of the U.S. Treasury OFAC SDN list, instantly flagging high-risk wallets associated with designated cybercrime syndicates."*

---

### Part 3: Decentralized Report Publishing to IPFS & Sepolia (1:30)

#### Actions:
1. In the left navigation sidebar, click **Cases & Reports**.
2. Under **Investigation Dossier Report**, click the button **Publish to IPFS + Sepolia**.
3. Observe the spinner (`Publishing…`).
4. Once published, the **Published Successfully** card displays:
   - **Investigation Hash**
   - **IPFS CID** (clickable link to gateway)
   - **Sepolia Transaction** (clickable link to Etherscan)
5. **Copy the Investigation Hash** (click the copy icon).
6. **Download the Authentic PDF**: Click the **IPFS CID** link. The PDF opens via your Pinata IPFS gateway. Save it locally as `authentic_report.pdf`. *(This guarantees an exact byte-for-byte match with the decentralized record).*
7. Click the **Sepolia Transaction** link to open Etherscan in a new tab. Show the confirmed block number, that the function is **Store Record** (`storeRecord`), and that the log event emitted is **RecordStored**.

#### What to Say:
> *"When an investigation concludes, sharing digital PDFs creates evidentiary risks because files can be altered or contested. BlockTrace solves this by anchoring reports into Web3.*
>
> *When we click 'Publish to IPFS + Sepolia', our FastAPI backend generates the official PDF dossier and calculates its deterministic SHA-256 investigation hash. It pins the PDF to IPFS via Pinata to obtain an immutable Content Identifier, and calls our BlockTraceRegistry smart contract on Ethereum Sepolia to store the hash, CID, and timestamp.*
>
> *Let's copy this Investigation Hash. Then, we click the IPFS CID link to download the exact published document as our authentic file.*
>
> *Opening the transaction on Sepolia Etherscan, we see that the function is Store Record and the log event is RecordStored, proving this report was anchored in this exact state on-chain."*

#### Fallback (If Something Fails):
- *If Sepolia RPC experiences temporary network congestion*: The UI still displays the IPFS CID link and computed investigation hash. You can download the PDF via the CID link and use the hash for verification.

---

### Part 4: Server-Side Encrypted Case Anchoring (1:15)

#### Actions:
1. In the **Cases & Reports** screen, scroll to the **Save Current Case** form.
2. Enter:
   - **Case #**: `BT-2026-DEMO`
   - **Case Name**: `Lazarus Ronin Laundering Ring`
   - Ensure the checkbox **Anchor on Sepolia** is checked.
3. Click **Save Case**.
4. When the table refreshes, highlight the new row showing **`Anchored v1`** and the blue **`[lock] Encrypted`** badge.
5. Click the **Verify** button on that row.
6. In the modal, explain the **Triple-Check Cryptographic Match**:
   - `Local SHA-256 Digest`
   - `Sepolia On-Chain Digest`
   - `Decrypted IPFS Payload SHA-256`

#### What to Say:
> *"Public reports are great for final court exhibits, but active, ongoing cases contain sensitive intelligence and investigator notes.*
>
> *BlockTrace protects active cases using server-side encryption by the FastAPI backend before IPFS upload (AES-256-GCM, HKDF per-case key). When we save case BT-2026-DEMO with 'Anchor on Sepolia' checked:*
> - *The backend computes the plain SHA-256 hash over the canonical unencrypted snapshot, ensuring the on-chain audit trail remains transparent.*
> - *It derives a unique 256-bit encryption key using HKDF-SHA256 bound to this case number.*
> - *It encrypts the snapshot with AES-256-GCM before uploading it to IPFS as an octet-stream.*
>
> *Notice the 'Encrypted' badge. When we click 'Verify', the backend downloads the encrypted payload from IPFS, decrypts it in-memory, and confirms that the local hash, on-chain hash, and decrypted IPFS payload hash all match 100%."*

#### Fallback (If Something Fails):
- *If save encounters delay*: Click **Verify** on any existing anchored case already in the list to demonstrate the verification modal.

---

### Part 5: Public "Verify Report" Experience & Tamper Defense (2:00)

#### Actions:
1. In the left navigation sidebar, click **Verify Report**.
2. **Scenario A (Authentic Verification)**:
   - Drag and drop the downloaded `authentic_report.pdf` into the upload zone.
   - Paste the copied **Investigation Hash** into the Investigation Hash field.
   - Click **Verify Report Integrity**.
   - Show the large green **`AUTHENTIC`** badge: "Cryptographic Integrity Confirmed: The uploaded document byte-for-byte matches the immutable report archived on IPFS and anchored on Ethereum Sepolia."
3. **Scenario B (Tamper Detection)**:
   - Click **Clear**.
   - Drag and drop `tampered_report.pdf` into the upload zone.
   - Paste the same authentic **Investigation Hash**.
   - Click **Verify Report Integrity**.
   - Show the red **`TAMPERED`** badge: "Document Tampering Detected: The uploaded PDF's SHA-256 hash does NOT match the stored artifact on IPFS anchored to this on-chain investigation hash."
4. **Scenario C (Non-existent Record)**:
   - Click **Clear**.
   - Drag and drop any PDF file.
   - Paste a non-existent hash: `0x1111111111111111111111111111111111111111111111111111111111111111`.
   - Click **Verify Report Integrity**.
   - Show the amber **`NOT FOUND`** badge: "On-Chain Record Not Found: No record exists on Ethereum Sepolia for this investigation hash."

#### What to Say:
> *"Now let's step into the shoes of a judge, regulator, or defense attorney who receives this PDF.*
>
> *They don't have our database, and they don't need a Web3 wallet. They simply open this public Verify Report portal.*
>
> *First, we upload our authentic PDF downloaded from IPFS and paste the investigation hash. We click 'Verify Report Integrity'. The backend queries the Sepolia contract, pulls the canonical file from IPFS, and compares them byte-for-byte. Result: Green AUTHENTIC badge.*
>
> *Now, what if someone alters even a single dollar figure, address, or paragraph? We click Clear, upload our tampered PDF, and paste the same hash. Result: Red TAMPERED alert. The hash mismatch is instantly caught.*
>
> *Finally, what if someone invents a fake investigation hash? We click Clear, enter a dummy hash, and click Verify. Result: Amber NOT FOUND alert. The Sepolia contract confirms no such record exists.*
>
> *This provides a mathematically verifiable, tamper-evident chain of custody from initial blockchain trace to final judicial review."*

---

### Part 6: Conclusion & Value Proposition (0:30)

#### What to Say:
> *"In summary, BlockTrace bridges graph forensics with decentralized evidentiary proof on Ethereum Sepolia. Investigators can trace complex illicit flows, protect active cases with server-side AES-256-GCM encryption, and generate tamper-evident reports that anyone in the world can independently verify.*
>
> *Thank you, and I am happy to take any questions."*
