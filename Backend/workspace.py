"""Per-visitor workspace isolation.

Each browser / desktop install generates a random workspace ID and sends it in the
X-Workspace-Id header. The ID scopes the Neo4j graph, saved cases on disk, and the
on-chain case key, so visitors never see or clear each other's investigations.
Requests without a (valid) header use the "default" workspace, which also holds
data created before workspaces existed.
"""

import re
from contextvars import ContextVar
from urllib.parse import parse_qs

DEFAULT_WORKSPACE = "default"
HEADER = b"x-workspace-id"
QUERY_PARAM = "ws"

# Also used as a directory name, so keep it strictly filesystem-safe.
_VALID = re.compile(r"^[A-Za-z0-9-]{8,64}$")

_current: ContextVar[str] = ContextVar("workspace", default=DEFAULT_WORKSPACE)


def current() -> str:
    return _current.get()


def normalize(raw) -> str:
    if raw and _VALID.match(raw):
        return raw.lower()
    return DEFAULT_WORKSPACE


class WorkspaceMiddleware:
    """Pure ASGI middleware: binds the request's workspace before any handler runs.
    Sync endpoints run in a threadpool with a copy of this context, so they see it too."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raw = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == HEADER), None)
        if raw is None:
            # Plain links (e.g. the PDF download) can't set headers, so accept ?ws= too.
            query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
            raw = (query.get(QUERY_PARAM) or [None])[0]
        token = _current.set(normalize(raw))
        try:
            await self.app(scope, receive, send)
        finally:
            _current.reset(token)
