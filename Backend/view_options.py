"""Per-request display options that change which transactions count.

Today there is one: whether 0-ETH transactions (usually contract calls) are shown.
The browser sends it as the X-Show-Zero-Value header; plain links such as the PDF
download use ?show_zero=1 instead. Like the workspace, it is bound to a ContextVar
by an ASGI middleware, so the graph, summary, Findings and PDF all read the same
value for a request without every function taking a parameter.
"""

from contextvars import ContextVar
from urllib.parse import parse_qs

HEADER = b"x-show-zero-value"
QUERY_PARAM = "show_zero"

_show_zero: ContextVar[bool] = ContextVar("show_zero", default=False)


def show_zero() -> bool:
    return _show_zero.get()


def parse_flag(raw) -> bool:
    return str(raw or "").strip().lower() in ("1", "true", "yes", "on")


class ViewOptionsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raw = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == HEADER), None)
        if raw is None:
            query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
            raw = (query.get(QUERY_PARAM) or [None])[0]
        token = _show_zero.set(parse_flag(raw))
        try:
            await self.app(scope, receive, send)
        finally:
            _show_zero.reset(token)
