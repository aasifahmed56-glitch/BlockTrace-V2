# BlockTrace — Frontend/Backend Integration Brief

Give this document to whichever IDE/agent (Antigravity, VS Code + Copilot, etc.) wires the
Stitch-exported UI to the FastAPI backend (`api.py`). It maps every endpoint to the screen
and UI element it feeds, with exact request/response shapes.

**Base URL (local dev):** `http://localhost:8000`
**Start the backend:** `uvicorn api:app --reload --port 8000`
**Interactive API docs:** `http://localhost:8000/docs` (test any endpoint by hand here first)

CORS is already enabled for all origins in dev — no extra backend config needed to call
this from a React dev server on a different port.

---

## Screen 2: Investigate

### Sidebar — "Example Investigations" buttons (3 buttons)
On click: `POST /curated-cases/{case_name}/load`
- Path param `case_name` must exactly match one of: `Ronin Bridge Hack ($600M, 2022)`,
  `Poly Network Hack ($611M, 2021)`, `Wormhole Bridge Hack ($321M, 2022)` (URL-encode the
  spaces/parens) — or first call `GET /curated-cases` to get the exact list dynamically
- Response: `{"wallets_visited": int, "start_wallet": str}`
- After this call succeeds, refetch `GET /graph` and `GET /summary` to update the main view

### Sidebar — "Investigate a Wallet" panel
On "Expand Graph" click: `POST /expand`
```json
{ "wallet": "0x...", "hops": 2, "tx_per_wallet": 15, "chain": "Ethereum" }
```
- `chain` must be one of the values from `GET /chains` (`Ethereum`, `BNB Smart Chain`, `Polygon`)
- Response: `{"wallets_visited": int, "start_wallet": str}`
- After success, refetch `GET /graph`

### Sidebar — "Trace a Specific Path" panel
On "Find Path" click: `POST /path`
```json
{ "source": "0x...", "destination": "0x...", "max_hops": 4, "tx_per_wallet": 15, "chain": "Ethereum" }
```
- Response: `{"found": bool, "wallets_visited": int, "paths": [{"wallets": [...], "rels": [{"from":..,"to":..,"value":..}], "hops": int}]}`
- If `found` is false, show a message like "no path found within the hop limit" — don't render an empty graph silently
- If found, render only the union of `rels` across all returned `paths` (dedupe by from+to+value) instead of the full graph — this is what "show only this route" means

### Main graph canvas
On load / after any expand or path action: `GET /graph`
- Response: `{"edges": [{"from": "0x...", "to": "0x...", "value": 1.23}, ...]}`
- For node styling, cross-reference each address against `GET /sanctions` (red dot) and
  the `label` field returned by the detection endpoints below (star icon for known entities)

### Filter input
Client-side only — filter the already-fetched edges by substring match on `from`/`to`,
no API call needed.

---

## Screen 3: Findings

Fetch all of these after the graph is loaded/updated (they all reflect current DB state,
no request body needed unless noted):

| UI section | Endpoint | Notes |
|---|---|---|
| "What This Trail Shows" | `GET /narrative?start_wallet=0x...` | `start_wallet` optional — omit to let the backend infer it from the graph. Response: `{"paragraphs": ["...", "..."]}` — render each as a paragraph in the accent box, in order |
| Sanctions Screening | `GET /sanctions` | `{"matches": [{"wallet": "0x...", "name": "...", "authority": "...", "note": "..."}]}` |
| Wallet Risk Overview | `GET /risk` | `{"results": [{"wallet": "0x...", "signals": ["Hub Activity", "Fan-Out"], "score": 2, "tier": "Medium", "label": null}]}` — `tier` is already the display label; map to badge color: Low=green, Medium=orange, High=red |
| Hub Wallets panel | `GET /detections/hub` | `{"results": [{"wallet":..., "total_txs":..., "label": null}]}` |
| High Fan-Out panel | `GET /detections/fanout` | `{"results": [{"wallet":..., "distinct_recipients":..., "label": null}]}` |
| Peel Chains panel | `GET /detections/peel-chains` | `{"results": [{"wallet":..., "main_amount":..., "peel_amount":..., "label": null}]}` |
| Round-Number panel | `GET /detections/round-number` | `{"results": [{"from":..., "to":..., "value":...}]}` |
| Circular Flows panel | `GET /detections/circular` | `{"results": [{"wallet":..., "hops":..., "label": null}]}` |

All detection endpoints return **all** matches, not capped at 5 — implement the "show 5,
then Show all N" behavior client-side by slicing the array.

`label` is `null` when the address isn't a known/verified entity — only show the star icon
when it's non-null.

---

## Screen 4: Certificates

### "Generate Certificate for Current Findings" button
`POST /certificate`
```json
{ "start_wallet": "0x..." }
```
(`start_wallet` optional, same inference rule as `/narrative`)
- Response:
```json
{
  "certificate_hash": "...",
  "previous_hash": "...",
  "created_at": "2026-08-31T...",
  "payload": { "...": "..." },
  "verification_note": "..."
}
```
- Show the truncated `certificate_hash` in the result box
- The "Download Certificate" button should save the **entire response JSON** as a `.json`
  file client-side (no separate download endpoint — the POST response IS the certificate file)

### "Verify an Existing Certificate" upload
On file selected, parse the uploaded JSON, then:
`POST /certificate/verify`
```json
{ "certificate_hash": "...", "previous_hash": "...", "payload": { "...": "..." } }
```
(pass through the exact `certificate_hash`, `previous_hash`, and `payload` fields from the
uploaded file — don't rename or restructure them)
- Response: `{"valid": true}` or `{"valid": false}`
- `true` → green success card, `false` → red "may have been altered" card

---

## Screen 5: Cases & Reports

### "Generate PDF Report" / "Download Report" buttons
`GET /report?start_wallet=0x...` (optional query param, same inference rule)
- This endpoint returns the **PDF file directly** (not JSON) — `Content-Type: application/pdf`
- Simplest integration: just point a link/anchor tag's `href` at this URL, or trigger a
  `window.open()` / blob download on button click — no need to parse a response body

### "Save Current Case" button
`POST /cases`
```json
{ "name": "My Investigation", "start_wallet": "0x..." }
```
(`start_wallet` optional)
- Response: `{"status": "saved", "path": "...", "edge_count": 42}`
- Errors with 400 if the graph is currently empty — surface that message to the user

### Saved cases table
`GET /cases` returns `{"cases": [{"name":"...", "saved_at":"...", "edge_count": 42}]}`

**"Load" button per row:** `POST /cases/{name}/load`
- This clears the entire current graph before loading the saved case — warn the user with
  a confirmation dialog before calling this, since any unsaved current investigation will
  be lost
- Response: `{"status": "loaded", "name":"...", "edge_count": 42, "start_wallet": "0x..."}`
- After success, refetch `GET /graph`, `GET /summary`, and everything on the Findings screen

**Delete icon per row:** `DELETE /cases/{name}`
- Response: `{"status": "deleted"}` or 404 if not found — also worth a confirm dialog

---

## Global error handling

Every endpoint can return a FastAPI-style error on failure:
```json
{ "detail": "human-readable message" }
```
with an appropriate HTTP status code (400 for bad input, 404 for not found, 500 for
server/DB errors). Surface `detail` directly in a toast/error state — the messages are
already written to be user-facing (e.g. "Enter both a source and destination wallet.").

## One important product-level caveat to preserve in the UI

Anywhere findings are displayed, keep the tone the backend already establishes: these are
heuristic indicators, not proof. Don't let UI copy (button labels, headings) drift into
more absolute language than what the API text itself uses — this is a deliberate product
requirement, not just a wording preference.
