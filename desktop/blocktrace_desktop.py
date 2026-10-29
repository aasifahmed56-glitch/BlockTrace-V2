"""BlockTrace desktop launcher.

Serves the bundled React UI from a local loopback server and opens it in a
native window (Edge WebView2 via pywebview). Requests to /api/* are forwarded
to the hosted BlockTrace backend, so no secrets ship inside the app and the
backend's CORS policy is never involved.

Backend URL resolution (first match wins):
  1. BLOCKTRACE_API_URL environment variable
  2. "api_url" in %LOCALAPPDATA%\\BlockTrace\\config.json
  3. DEFAULT_API_URL
"""

import json
import mimetypes
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_NAME = "BlockTrace"
DEFAULT_API_URL = "https://blocktrace-v2.onrender.com"
# Fixed port keeps the page origin stable so WebView storage persists between launches.
PREFERRED_PORT = 47815
UPSTREAM_TIMEOUT = 120  # Render free tier can take ~60s to wake up

# Headers that must not be forwarded across the proxy hop.
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "origin",
    "referer", "accept-encoding", "content-length",
}

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/manifest+json", ".webmanifest")


def resource_dir() -> Path:
    """Folder holding bundled files (PyInstaller unpack dir when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_api_url() -> str:
    url = os.environ.get("BLOCKTRACE_API_URL")
    if not url:
        config = data_dir() / "config.json"
        try:
            url = json.loads(config.read_text(encoding="utf-8")).get("api_url")
        except (OSError, ValueError):
            url = None
    return (url or DEFAULT_API_URL).rstrip("/")


WEB_ROOT = resource_dir() / "web"
API_URL = resolve_api_url()


class AppHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep the windowed app quiet
        pass

    def do_GET(self):
        self._dispatch()

    def do_HEAD(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_PUT(self):
        self._dispatch()

    def do_PATCH(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()

    def do_OPTIONS(self):
        self._dispatch()

    def _dispatch(self):
        if self.path == "/api" or self.path.startswith("/api/") or self.path.startswith("/api?"):
            self._proxy()
        elif self.command in ("GET", "HEAD"):
            self._static()
        else:
            self._send(405, b"Method Not Allowed", "text/plain")

    # ---------------------------------------------------------------- static
    def _static(self):
        rel = self.path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        # The PWA service worker caches same-origin GETs, which would include
        # proxied API calls here, so it is deliberately not served.
        if rel == "sw.js":
            self._send(404, b"Not Found", "text/plain")
            return
        target = (WEB_ROOT / rel).resolve() if rel else WEB_ROOT / "index.html"
        if not str(target).startswith(str(WEB_ROOT.resolve())) or not target.is_file():
            target = WEB_ROOT / "index.html"  # SPA fallback (e.g. /privacy)
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        cache = "no-cache" if target.name == "index.html" else "max-age=31536000, immutable"
        self._send(200, target.read_bytes(), ctype, {"Cache-Control": cache})

    # ----------------------------------------------------------------- proxy
    def _proxy(self):
        upstream = API_URL + self.path[len("/api"):]
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}
        req = urllib.request.Request(upstream, data=body, headers=headers, method=self.command)
        try:
            resp = urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT)
        except urllib.error.HTTPError as err:
            resp = err  # non-2xx responses still carry a body the UI needs
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            msg = json.dumps({"detail": f"Cannot reach BlockTrace server: {err}"}).encode()
            self._send(502, msg, "application/json")
            return
        with resp:
            data = resp.read()
            extra = {k: v for k, v in resp.headers.items()
                     if k.lower() not in HOP_HEADERS and k.lower() != "content-type"}
            self._send(resp.status, data, resp.headers.get("Content-Type", "application/octet-stream"), extra)

    def _send(self, status, data, ctype, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)


def start_server() -> ThreadingHTTPServer:
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PREFERRED_PORT), AppHandler)
    except OSError:
        server = ThreadingHTTPServer(("127.0.0.1", 0), AppHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    server = start_server()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        import webview

        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.create_window(APP_NAME, url, width=1440, height=900, min_size=(1024, 640))
        webview.start(private_mode=False, storage_path=str(data_dir() / "webview"))
    except Exception:
        # No WebView2 runtime: fall back to the default browser and keep serving.
        webbrowser.open(url)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
