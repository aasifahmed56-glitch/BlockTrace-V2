# BlockTrace Verifier - Browser Extension

**BlockTrace Verifier** is a Manifest V3 browser extension for Google Chrome and Microsoft Edge. It independently verifies BlockTrace forensic PDF reports against Ethereum Sepolia on-chain anchors and screens wallet addresses against known sanctions lists.

---

## Directory Structure

```
extension/
├── manifest.json              # Manifest V3 configuration (Chrome & Edge)
├── config.json                 # API & Web target URLs
├── background.js              # Service worker (context menu listener)
├── popup.html                 # Main popup UI (380px wide)
├── popup.css                  # Plain CSS styling (Dark Brown #2B1D17, Orange #E0621A)
├── popup.js                   # Client-side verification & sanctions check logic
├── options.html               # Extension options page
├── options.js                 # Options test connection handler
├── icons/                     # Extension icons (16, 32, 48, 128 px)
├── store/
│   ├── STORE_LISTING.md       # Chrome Web Store & Edge Add-ons metadata
│   └── promo-tile-440x280.png # Small promo store tile
├── tests/
│   └── test_validators.js     # Node unit tests for address, hash, and file checks
├── build.js                   # Packaging script (produces blocktrace-verifier.zip)
├── PRIVACY.md                 # Extension privacy policy
└── README.md                  # This file
```

---

## Features

1. **Verify Report**:
   - Drag-and-drop or select any BlockTrace PDF forensic report.
   - Client-side validation: verifies `%PDF` magic header and 25 MB max size cap.
   - Optional 64-character investigation hash input (auto-extracted from PDF if omitted).
   - Shows badge verdicts: `AUTHENTIC` (green), `TAMPERED` (red), `NOT FOUND` (amber), or `UNAVAILABLE` (grey).
   - Displays anchored submitter address, UTC timestamp, IPFS CID, and uploaded vs stored SHA-256 digests with copy buttons.
   - Provides direct links to the Sepolia block explorer and decentralized IPFS gateway.

2. **Check Address**:
   - Validate 42-character Ethereum addresses (`0x` + 40 hex).
   - Checks against a dated snapshot of the OFAC SDN list (the response includes its publication date).
   - Displays `SANCTIONED` or `NOT ON LIST` badge with identified entity labels.
   - Direct button to open the full investigation workspace on BlockTrace Web.

3. **Context Menu**:
   - Highlight any wallet address on any webpage, right-click, and choose **"Check address with BlockTrace"**.
   - Opens a compact popup window directly on the address tab with the address auto-screened.

4. **Render Free-Tier Wakeup**:
   - Pings `GET /health` in the background when the popup is opened.
   - Uses a 90-second timeout.
   - Displays a *"Waking up the server, this can take up to a minute..."* banner if a request exceeds 5 seconds.
   - Automatically retries once on network dropouts.

---

## How to Load Unpacked (Development)

### In Microsoft Edge:
1. Open Edge and navigate to `edge://extensions`.
2. Toggle **Developer mode** on (bottom-left switch).
3. Click the **Load unpacked** button.
4. Select the `d:\BlockTrace 2\extension` directory.
5. The **BlockTrace Verifier** extension icon will appear in the toolbar. Click to open.

### In Google Chrome:
1. Open Chrome and navigate to `chrome://extensions`.
2. Toggle **Developer mode** on (top-right switch).
3. Click the **Load unpacked** button.
4. Select the `d:\BlockTrace 2\extension` directory.
5. Pin the extension to your toolbar.

---

## Manual Test Plan

### Test 1: Verify Authentic Report
1. Click the BlockTrace Verifier icon to open the popup.
2. In the "Verify Report" tab, select `investigation_report.pdf` (or your published report).
3. (Optional) Provide the 64-hex investigation hash.
4. Click **Verify Report On-Chain**.
5. **Expected Outcome**:
   - Button shows "Verifying with Sepolia...".
   - Green **AUTHENTIC** badge appears.
   - Uploaded SHA-256 and On-Chain IPFS SHA-256 match identically.
   - Submitter address, UTC timestamp, and Sepolia Explorer link are displayed.

### Test 2: Verify Tampered Report
1. Make a copy of `investigation_report.pdf` as `tampered_report.pdf`.
2. Open `tampered_report.pdf` in a text editor and modify one character of text.
3. In the popup, upload `tampered_report.pdf` and enter the valid investigation hash.
4. Click **Verify Report On-Chain**.
5. **Expected Outcome**:
   - Red **TAMPERED** badge appears.
   - Explanation notes cryptographic digest mismatch.

### Test 3: Unknown Investigation Hash
1. Upload any PDF file.
2. Enter a random 64-hex hash (e.g. `0000000000000000000000000000000000000000000000000000000000000001`).
3. Click **Verify Report On-Chain**.
4. **Expected Outcome**:
   - Amber **NOT FOUND** badge appears.
   - Message indicates no on-chain record exists for that hash.

### Test 4: Sanctions Check (Sanctioned)
1. Switch to the **Check Address** tab.
2. Paste the known Lazarus Group Ronin hacker address:
   `0x098B716B8Aaf21512996dC57EB0615e2383E2f96`
3. Click **Check Sanctions List**.
4. **Expected Outcome**:
   - Red **SANCTIONED** badge appears.
   - Entity label: *"Ronin Bridge Hacker (Lazarus Group)"*.
   - Source: *"OFAC SDN list snapshot"*.

### Test 5: Sanctions Check (Clean Address)
1. In the **Check Address** tab, enter a standard clean address:
   `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045` (vitalik.eth)
2. Click **Check Sanctions List**.
3. **Expected Outcome**:
   - Green **NOT ON LIST** badge appears.

### Test 6: Context Menu Check
1. On any webpage, highlight `0x098B716B8Aaf21512996dC57EB0615e2383E2f96`.
2. Right-click and choose **Check address with BlockTrace**.
3. **Expected Outcome**:
   - A 396x560 popup window opens directly to the Address tab.
   - Address is pre-filled and automatically checked.

### Test 7: Options Page & Server Health
1. Click the gear icon in the popup header or right-click the extension icon &rarr; **Extension options**.
2. Click **Test Connection (/health)**.
3. **Expected Outcome**:
   - Displays green success message: *"Connection successful! Status: ok, Public Mode: true"*.

---

## Packaging for Store Submission

Run:
```bash
node extension/build.js
```

This creates `extension/blocktrace-verifier.zip` with `manifest.json` placed at the root of the archive, ready to be uploaded to:
- [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
- [Microsoft Edge Partner Center](https://partner.microsoft.com/dashboard/microsoftedge)

