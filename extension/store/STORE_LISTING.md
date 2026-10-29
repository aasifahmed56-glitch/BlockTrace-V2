# Chrome Web Store & Microsoft Edge Add-ons Listing

## Extension Name
BlockTrace Verifier

## Short Summary (Max 132 characters)
Verify BlockTrace forensic PDF reports on-chain and screen Ethereum addresses against the BlockTrace sanctions list.
*(Character count: 118 characters - well within 132 limit)*

---

## Detailed Description

**BlockTrace Verifier** is the official companion browser extension for the BlockTrace blockchain crime investigation platform. It provides instant, independent cryptographic verification of BlockTrace forensic PDF reports against Ethereum Sepolia on-chain anchors, as well as fast screening of wallet addresses against known sanctions lists.

### Key Features

1. **On-Chain Report Verification**:
   - Verify any BlockTrace forensic investigation PDF against its immutable on-chain record.
   - Computes local SHA-256 digests and cross-references the registered IPFS artifact recorded on the Sepolia smart contract registry.
   - Displays clear, tamper-evident verdicts:
     - **AUTHENTIC** (green): Document matches on-chain IPFS artifact byte-for-byte.
     - **TAMPERED** (red): File contents differ from the recorded on-chain artifact.
     - **NOT FOUND** (amber): Investigation hash does not exist on Sepolia.
     - **UNAVAILABLE** (grey): Network or gateway timeout.
   - Provides direct links to Sepolia block explorer and decentralized IPFS gateways.

2. **Sanctions & Known Entity Screening**:
   - Screen any Ethereum wallet address against the built-in OFAC-based sanctions list.
   - Right-click any wallet address on any web page (Etherscan, block explorers, news articles) and select **"Check address with BlockTrace"** to inspect it instantly in a lightweight window.

3. **Privacy-Preserving & Zero-Telemetry**:
   - Plain HTML, CSS, and vanilla JavaScript only.
   - Zero remote scripts, zero CDN dependencies, zero analytics, and zero tracking.
   - Uploaded PDF reports are processed strictly in volatile memory and are never stored or logged on servers.

---

## Single-Purpose Statement

The sole purpose of BlockTrace Verifier is to verify the cryptographic authenticity of BlockTrace forensic PDF reports against public blockchain anchors and to screen Ethereum addresses against a sanctions list.

---

## Permission Justifications

| Permission | Technical Need | User Justification |
| :--- | :--- | :--- |
| **`storage`** | `chrome.storage.local` API | Caches local extension configuration (such as the verified API URL) securely inside the browser profile. |
| **`contextMenus`** | `chrome.contextMenus` API | Adds the right-click "Check address with BlockTrace" option when text is highlighted on a page to provide 1-click address screening. |
| **Host Permission (`https://blocktrace-v2.onrender.com/*`)** | `fetch()` network requests | Restricted exclusively to the official BlockTrace backend host. Needed to call `/report/verify`, `/sanctions/check`, and `/health`. No broad host permissions (e.g. `<all_urls>`) are requested. |

---

## Category
- **Primary**: Productivity
- **Secondary**: Developer Tools

---

## Store Assets & Screenshot Checklist

### Small Promotional Tile (440 x 280 px)
- Created: `extension/store/promo-tile-440x280.png`
- Features the dark brown (`#2B1D17`) and orange (`#E0621A`) network node branding.

### Required Store Screenshots (1280 x 800 px)
Capture these screenshots before submission:
1. **Screenshot 1: Report Verification (AUTHENTIC)**
   - Upload `investigation_report.pdf`
   - Shows green `AUTHENTIC` badge, matching SHA-256 digests, Sepolia submitter address, and IPFS CID.
2. **Screenshot 2: Report Verification (TAMPERED)**
   - Upload an altered PDF with a mismatched hash.
   - Shows red `TAMPERED` badge highlighting cryptographic integrity failure.
3. **Screenshot 3: Sanctions Screening**
   - Address tab with Ronin Bridge hacker address `0x098B716B8Aaf21512996dC57EB0615e2383E2f96`.
   - Shows red `SANCTIONED` badge and entity label: "Ronin Bridge Hacker (Lazarus Group)".
4. **Screenshot 4: Context Menu Inspection**
   - Right-click highlight on a webpage showing "Check address with BlockTrace".

---

## Support & Contact
- **Website**: https://blocktrace-v2.vercel.app
- **Privacy Policy**: https://blocktrace-v2.vercel.app/privacy
- **Source Repository**: https://github.com/your-org/BlockTrace
- **Support Email**: support@blocktrace.local

