# BlockTrace Deployment Guide

## Architecture

```
┌─────────────┐        ┌──────────────────┐        ┌───────────────┐
│   Vercel     │  HTTP  │  Render (Free)   │  Bolt  │  Neo4j Aura   │
│  (Frontend)  │ ─────> │  (FastAPI API)   │ ─────> │  (Graph DB)   │
│  React SPA   │        │  Python 3.12     │        │               │
└─────────────┘        └──────────────────┘        └───────────────┘
                              │
                              ├──> Etherscan API (on-chain data)
                              ├──> Sepolia RPC (blockchain anchoring)
                              └──> Pinata / IPFS (report & case storage)
```

- **Frontend**: `https://blocktrace-v2.vercel.app` — static React SPA
- **Backend**: `https://blocktrace-v2.onrender.com` — FastAPI on Render free tier

---

## Backend (Render)

### Service Configuration

| Setting        | Value                                             |
|----------------|---------------------------------------------------|
| Type           | Web Service                                       |
| Environment    | Python                                            |
| Build Command  | `pip install -r requirements.txt`                 |
| Start Command  | `uvicorn api:app --host 0.0.0.0 --port $PORT`    |
| Health Check   | `/health`                                         |
| Plan           | Free                                              |

### Environment Variables

Set these in Render's Environment tab (values are secrets — names only listed here):

#### Required
| Variable              | Description                                    |
|-----------------------|------------------------------------------------|
| `PUBLIC_MODE`         | Set to `true`                                  |
| `CORS_ORIGINS`        | `https://blocktrace-v2.vercel.app`             |
| `NEO4J_URI`           | Neo4j Aura connection URI                      |
| `NEO4J_USER`          | Neo4j username                                 |
| `NEO4J_PASSWORD`      | Neo4j password                                 |
| `NEO4J_DATABASE`      | Neo4j database name (usually `neo4j`)          |
| `ETHERSCAN_API_KEY`   | Etherscan API key for on-chain queries         |
| `SEPOLIA_RPC_URL`     | Sepolia RPC endpoint (e.g. Infura / Alchemy)   |
| `CONTRACT_ADDRESS`    | BlockTraceRegistry contract on Sepolia         |
| `CASE_CONTRACT_ADDRESS` | BlockTraceCaseRegistry contract on Sepolia   |
| `PINATA_GATEWAY`      | Pinata gateway URL for IPFS downloads          |

#### Optional (for full functionality on demo day)
| Variable              | Description                                    |
|-----------------------|------------------------------------------------|
| `PINATA_JWT`          | Pinata API token for IPFS uploads              |
| `WALLET_PRIVATE_KEY`  | Sepolia wallet key for on-chain transactions   |
| `CASE_ENCRYPTION_KEY` | AES-256 key for case snapshot encryption       |

> **Note**: These enable report publishing, case anchoring, and encrypted case storage.
> The API has no login, so anyone can trigger them; per-IP rate limits (below) cap how
> fast the Sepolia wallet and Pinata quota can be spent. Leave them unset for a host
> without on-chain features. `ACCESS_CODE` is no longer used and can be deleted from Render.

### Important: Ephemeral Filesystem

Render's free tier uses an **ephemeral filesystem**. The `cases/` folder where
saved investigation JSON files are stored will be **lost on every deploy or restart**.
This means:
- Saved cases are temporary on the hosted version
- Case data persists only until the next deploy or instance restart
- For permanent storage, cases are anchored on-chain (Sepolia) and on IPFS

### Python Version

Render uses `runtime.txt` to determine the Python version. The file is set to
`python-3.12.8`. Your local machine may use Python 3.14, but Render only supports
up to 3.12/3.13.

---

## Frontend (Vercel)

### Configuration

1. Connect the `stitch_universal_build_framework` directory to Vercel
2. Set the environment variable:

| Variable              | Value                                          |
|-----------------------|------------------------------------------------|
| `VITE_API_BASE_URL`   | `https://blocktrace-v2.onrender.com`           |

3. Vercel auto-detects Vite and runs `npm run build`
4. `vercel.json` provides SPA rewrites so `/privacy` and other routes work

### Routes

| Path       | Description                        |
|------------|------------------------------------|
| `/`        | Main application (SPA)             |
| `/privacy` | Static privacy policy page         |

---

## Public Mode Behavior

When `PUBLIC_MODE=true`:

All endpoints are open; there is no access code. Public mode adds:

- Rate limiting: 120 requests/minute per client IP on every endpoint except `/health`
- On-chain budget: 5 requests/hour per IP for `POST /report/publish` and
  `POST /cases/{case_number}/anchor|reanchor` (these spend Sepolia gas and Pinata storage)
- Generic error messages (no stack traces exposed)
- CORS restricted to `CORS_ORIGINS` value
- Secrets never logged or returned in any response

Limits return `429` with a `Retry-After` header.

---

## Post-Deploy Smoke Test

After deploying both services, run these from PowerShell:

```powershell
# 1. Health check (should return {"status":"ok","public_mode":true})
curl.exe https://blocktrace-v2.onrender.com/health

# 2. Sanctions check (should return {"sanctioned":true, "list_publication_date": ..., "count": ...})
curl.exe "https://blocktrace-v2.onrender.com/sanctions/check?address=0x098B716B8Aaf21512996dC57EB0615e2383E2f96"

# 3. Workspace endpoint, no login needed (should return {"chains":[...]})
curl.exe https://blocktrace-v2.onrender.com/chains

# 4. Graph endpoint (should return 200 with the current edges)
curl.exe https://blocktrace-v2.onrender.com/graph

# 5. Frontend loads
curl.exe -s -o NUL -w "%{http_code}" https://blocktrace-v2.vercel.app
# Expected: 200

# 6. Privacy page loads
curl.exe -s -o NUL -w "%{http_code}" https://blocktrace-v2.vercel.app/privacy
# Expected: 200
```

> **Note**: The first request to Render may take 30–60 seconds if the instance is
> sleeping (free tier). The frontend calls `GET /health` on load to wake it early.

## Refreshing the OFAC sanctions list

The backend screens addresses against `data/sanctions_ofac.json`, a committed snapshot of the
OFAC SDN list, so Render needs no network access to OFAC at startup. To update it:

```bash
python scripts/update_sanctions.py
```

Then commit `data/sanctions_ofac.json` and push; Render redeploys with the new snapshot.
`/sanctions/check` reports the snapshot's `list_publication_date`, `fetched_at` and `count`.
