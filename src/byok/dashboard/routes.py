"""
Dashboard routes for logs and observability.
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .. import config
from ..proxy import REQUEST_LOGS, is_authorized, unauthorized_response

TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


def _load_dashboard_html() -> str:
    """Load and render the dashboard HTML template."""
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    return html.replace("{{ title }}", config.DASHBOARD_TITLE)


def register_routes(app: FastAPI) -> None:
    """Register dashboard and logs API routes."""

    @app.get("/")
    async def dashboard():
        if config.DASHBOARD_ENABLED:
            return HTMLResponse(_load_dashboard_html())
        from fastapi.responses import JSONResponse
        return JSONResponse({"service": "NewAPI Cursor BYOK Adapter", "ok": True})

    if config.DASHBOARD_ENABLED:
        @app.get("/api/logs")
        async def get_logs(req: Request):
            if not is_authorized(req):
                return unauthorized_response()
            return {"logs": REQUEST_LOGS}

        @app.delete("/api/logs")
        async def delete_logs(req: Request):
            if not is_authorized(req):
                return unauthorized_response()
            REQUEST_LOGS.clear()
            return {"ok": True}
