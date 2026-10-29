# BlockTrace Desktop (Windows)

A native Windows build of the BlockTrace UI. The app bundles the React frontend,
serves it on `127.0.0.1:47815`, and shows it in an Edge WebView2 window. Calls to
`/api/*` are forwarded to the hosted backend (`https://blocktrace-v2.onrender.com`).

**No secrets ship in the app.** The `.env` (Neo4j, Pinata, wallet private key)
stays on the backend server. Never bundle `api.py` and `.env` into a public build.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File desktop\build.ps1
```

Output: `desktop\dist\BlockTrace\BlockTrace.exe`. Ship the whole `BlockTrace` folder
(the exe needs its `_internal` folder next to it).

## Point at a different backend

Either set `BLOCKTRACE_API_URL`, or create `%LOCALAPPDATA%\BlockTrace\config.json`:

```json
{ "api_url": "http://127.0.0.1:8000" }
```

## Microsoft Store

The Store takes an `.msix` package, built by `msix\pack_msix.ps1` (after `build.ps1`).

1. Reserve the app name in Partner Center and open **Product management >
   Product identity**.
2. Pack with those exact values. The script's defaults already match the reserved
   `AasifAhmedA.BlockTrace` identity, so normally only `-Version` needs passing:

   ```powershell
   powershell -ExecutionPolicy Bypass -File desktop\msix\pack_msix.ps1 `
     -IdentityName "<Package/Identity/Name>" `
     -Publisher "<Package/Identity/Publisher, starts with CN=>" `
     -PublisherDisplayName "<Package/Properties/PublisherDisplayName>" `
     -Version 1.0.0.0
   ```

3. Upload `desktop\dist\BlockTrace.msix` under **Packages**. It is unsigned on purpose:
   the Store signs it. Raise `-Version` (keeping the last part `0`) for every update.
4. The package declares `runFullTrust`, a restricted capability. When Partner Center asks
   why, explain that it's a desktop (Win32) app packaged with PyInstaller.

Files: `msix\AppxManifest.xml` is the manifest template, and `msix\make_assets.py` generates
the tile images from the PWA icon. `makeappx.exe` comes from Microsoft's
`Microsoft.Windows.SDK.BuildTools` NuGet package and is cached in `desktop\.tools`.

Requirements: a privacy policy URL (`https://blocktrace-v2.vercel.app/privacy`),
and, because the backend runs in public mode, an access code given to certification
reviewers in the "Notes for certification" field.
